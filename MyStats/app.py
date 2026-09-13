"""
Streamlit app: Narrative Precision / Recall / F1

A professional, extensible version of `precision_f1_recall.py`. Same
methodology, same exact-match-with-alias-map normalization (including the
IL-1A/IL-1B distinction fix), and the same publication-quality chart style
-- but now:
  - narratives can be added/removed freely, not fixed at 5
  - each narrative's display name (what shows on the bar chart) is
    optional -- leave it blank and it defaults to "Narrative I",
    "Narrative II", "Narrative III", ... in order; renaming is only for
    when you want a more descriptive label
  - the ground truth list, the alias/synonym map, and every narrative's
    predictions are all editable in the browser, with live recompute

Verified against the original script's validated output: loading this app
with its defaults (unchanged) reproduces narrative_precision_recall_f1.csv
exactly -- Narratives I-V: P = 0.86/0.89/1.00/0.78/1.00,
R = 0.60/0.80/0.80/0.70/0.60, F1 = 0.71/0.84/0.89/0.74/0.75.

Run it (from your `bioshift` conda environment, or any env with the
packages in requirements_accuracy_app.txt installed):

    conda activate bioshift
    pip install streamlit   # if not already installed
    cd /Users/prabin/Claude/Projects/BioShift_0729/fix
    streamlit run precision_recall_f1_app.py

It opens in your browser at http://localhost:8501 -- nothing is sent
anywhere; it all runs locally on your Mac.
"""

import io

import pandas as pd
import streamlit as st

from scoring_core import parse_elements, parse_alias_map, normalize_set, prf, pooled_prf, to_roman
from chart_build import build_grouped_bar_chart

st.set_page_config(page_title="Narrative Precision / Recall / F1", layout="wide")

st.title("Narrative Precision / Recall / F1")
st.caption(
    "One shared ground-truth element list is compared against each narrative's own "
    "predicted elements. Matching is exact string match after trimming whitespace and "
    "applying the alias map below (not case-folding by default) -- so IL-1A and IL-1B "
    "stay distinct unless you say otherwise."
)

# ---------------- defaults, taken verbatim from precision_f1_recall.py ----------------
DEFAULT_GROUND_TRUTH = """IL-A
IL-B
MMP-8
EGF
PDGF
B-cell
Lactobacillus rhamnosus
Anaeroglobus geminatus
Dialister invisus
Brevundimonas diminuta"""

DEFAULT_ALIAS_MAP = """IL-1B -> IL-B
IL-1A -> IL-A
B-cells -> B-cell"""

DEFAULT_NARRATIVE_PREDICTIONS = [
    """IL-1B
MMP-8
Lactobacillus rhamnosus
EGF
PDGF
GDF-15
B-cells""",
    """MMP-8
IL-1B
EGF
PDGF
Lactobacillus paracasei
Lactobacillus rhamnosus
Anaeroglobus geminatus
Dialister invisus
B-cell""",
    """IL-1B
MMP-8
Lactobacillus rhamnosus
PDGF
B-cell
Anaeroglobus geminatus
Dialister invisus
EGF""",
    """B-cells
IL-1B
MMP-8
Lactobacillus rhamnosus
EGF
PDGF
GDF-15
Brevundimonas diminuta
Eggerthia catenaformis""",
    """MMP-8
IL-1B
Lactobacillus rhamnosus
EGF
B-cell
PDGF""",
]

# ---------------- session state ----------------
# Each narrative gets a permanent, never-reused numeric id (separate from
# its position in the list). Widget keys below are built from this id, not
# from list position -- if keys were position-based (e.g. f"name_{i}"),
# removing a narrative from the middle would shift every later row into a
# lower-numbered key, and Streamlit would keep showing that key's OLD
# cached text instead of the row's real content (a real bug, not just a
# display quirk -- this is what "deleting elements not working" was).
# Fresh ids on every add/reset also mean there's never a stale leftover
# key to collide with.
if "ground_truth_text" not in st.session_state:
    st.session_state.ground_truth_text = DEFAULT_GROUND_TRUTH
if "alias_map_text" not in st.session_state:
    st.session_state.alias_map_text = DEFAULT_ALIAS_MAP
if "case_insensitive" not in st.session_state:
    st.session_state.case_insensitive = False
if "next_id" not in st.session_state:
    st.session_state.next_id = 0
if "narratives" not in st.session_state:
    st.session_state.narratives = []
    for pred in DEFAULT_NARRATIVE_PREDICTIONS:
        nid = st.session_state.next_id
        st.session_state.next_id += 1
        st.session_state.narratives.append({"id": nid, "name": "", "predictions": pred})
if "generated" not in st.session_state:
    st.session_state.generated = True  # show the validated defaults immediately on first load


def add_narrative():
    nid = st.session_state.next_id
    st.session_state.next_id += 1
    st.session_state.narratives.append({"id": nid, "name": "", "predictions": ""})


def remove_narrative(nid):
    st.session_state.narratives = [n for n in st.session_state.narratives if n["id"] != nid]


def reset_all():
    st.session_state.ground_truth_text = DEFAULT_GROUND_TRUTH
    st.session_state.alias_map_text = DEFAULT_ALIAS_MAP
    st.session_state.case_insensitive = False
    st.session_state.narratives = []
    for pred in DEFAULT_NARRATIVE_PREDICTIONS:
        nid = st.session_state.next_id
        st.session_state.next_id += 1
        st.session_state.narratives.append({"id": nid, "name": "", "predictions": pred})
    st.session_state.generated = True


# ---------------- 1. ground truth ----------------
st.subheader("1. Ground truth elements (shared across all narratives)")
st.session_state.ground_truth_text = st.text_area(
    "Ground truth elements", value=st.session_state.ground_truth_text,
    height=160, label_visibility="collapsed",
)

# ---------------- 2. normalization / alias map ----------------
with st.expander("Advanced: normalization / synonym map (optional)", expanded=False):
    st.markdown(
        "Elements are matched **exactly** (after trimming whitespace) unless you map one "
        "spelling to another below. One mapping per line, as `raw -> canonical`. "
        "\n\n**Note:** IL-1A and IL-1B are *not* biologically equivalent -- they are distinct "
        "interleukin-1 family cytokines. Map each to its own canonical form; never map one "
        "to the other, or every real IL-1B detection would be silently credited as IL-1A "
        "(and vice versa)."
    )
    st.session_state.alias_map_text = st.text_area(
        "Alias / synonym map", value=st.session_state.alias_map_text, height=100,
        label_visibility="collapsed",
    )
    st.session_state.case_insensitive = st.checkbox(
        "Case-insensitive matching (lowercase everything before comparing)",
        value=st.session_state.case_insensitive,
    )

# ---------------- 3. narratives ----------------
st.subheader("2. Narratives")
top_cols = st.columns([1, 1, 5])
top_cols[0].button("➕ Add narrative", on_click=add_narrative, width="stretch", key="add_top")
top_cols[1].button("↺ Reset all", on_click=reset_all, width="stretch")

for i, n in enumerate(st.session_state.narratives):
    nid = n["id"]
    default_label = f"Narrative {to_roman(i + 1)}"
    with st.container(border=True):
        header_cols = st.columns([5, 1])
        n["name"] = header_cols[0].text_input(
            "Display name (optional)", value=n["name"], key=f"name_{nid}",
            placeholder=f"{default_label} (leave blank to use this default)",
        )
        header_cols[1].button(
            "🗑 Remove", key=f"remove_{nid}", on_click=remove_narrative, args=(nid,),
            width="stretch",
        )
        n["predictions"] = st.text_area(
            "Predicted elements", value=n["predictions"], key=f"pred_{nid}", height=130,
            placeholder="e.g.\nIL-1B\nMMP-8\nEGF",
        )

st.button("➕ Add narrative", on_click=add_narrative, key="add_bottom")

st.divider()
if st.button("🔄 Generate results & chart", type="primary", width="stretch"):
    st.session_state.generated = True

if not st.session_state.generated:
    st.info("Click **Generate results & chart** above to compute scores from what you've entered.")
    st.stop()

# ---------------- compute ----------------
alias_map = parse_alias_map(st.session_state.alias_map_text)
case_insensitive = st.session_state.case_insensitive
ground_truth_set = normalize_set(
    parse_elements(st.session_state.ground_truth_text), alias_map, case_insensitive
)

rows = []
for i, n in enumerate(st.session_state.narratives):
    predicted_set = normalize_set(parse_elements(n["predictions"]), alias_map, case_insensitive)
    if not predicted_set and not n["predictions"].strip():
        continue
    display_name = n["name"].strip() or f"Narrative {to_roman(i + 1)}"
    result = prf(ground_truth_set, predicted_set)
    result["narrative"] = display_name
    rows.append(result)

if not ground_truth_set:
    st.warning("Enter at least one ground-truth element above to compute scores.")
    st.stop()
if not rows:
    st.info("Enter predicted elements for at least one narrative above to see scores.")
    st.stop()

results_df = pd.DataFrame([
    {
        "Narrative": r["narrative"], "TP": r["tp"], "FP": r["fp"], "FN": r["fn"],
        "Precision": round(r["precision"], 2), "Recall": round(r["recall"], 2),
        "F1": round(r["f1"], 2),
        "TP_elements": ", ".join(r["matched"]),
        "FP_elements": ", ".join(r["extra"]),
        "FN_elements": ", ".join(r["missed"]),
    }
    for r in rows
])

st.subheader("3. Results")
st.dataframe(
    results_df.style.format({"Precision": "{:.2f}", "Recall": "{:.2f}", "F1": "{:.2f}"}),
    width="stretch",
)

# ---------------- chart ----------------
st.subheader("4. Chart")
include_pooled = st.checkbox(
    "Include a pooled (overall, micro-averaged) bar in the chart -- not part of the CSV export",
    value=False,
)
chart_title = st.text_input("Chart title", value="Precision, Recall, and F1 by Narrative")

chart_df = results_df[["Narrative", "Precision", "Recall", "F1"]].copy()
if include_pooled and len(rows) > 1:
    pooled = pooled_prf(rows)
    chart_df.loc[len(chart_df)] = [
        "Pooled", round(pooled["precision"], 2), round(pooled["recall"], 2), round(pooled["f1"], 2)
    ]

fig = build_grouped_bar_chart(chart_df, title=chart_title)
st.pyplot(fig)

png_buf = io.BytesIO()
fig.savefig(png_buf, format="png", dpi=300, bbox_inches="tight", facecolor="white")
pdf_buf = io.BytesIO()
fig.savefig(pdf_buf, format="pdf", bbox_inches="tight", facecolor="white")

st.subheader("5. Downloads")
dl_cols = st.columns(3)
dl_cols[0].download_button(
    "⬇ CSV (narrative_precision_recall_f1.csv)", data=results_df.to_csv(index=False),
    file_name="narrative_precision_recall_f1.csv", mime="text/csv", width="stretch",
)
dl_cols[1].download_button(
    "⬇ Chart PNG (300 dpi)", data=png_buf.getvalue(),
    file_name="narrative_precision_recall_f1_barchart.png", mime="image/png",
    width="stretch",
)
dl_cols[2].download_button(
    "⬇ Chart PDF (vector)", data=pdf_buf.getvalue(),
    file_name="narrative_precision_recall_f1_barchart.pdf", mime="application/pdf",
    width="stretch",
)
