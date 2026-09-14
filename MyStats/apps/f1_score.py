"""
MyStats tool: F1-Score vs Ground Truth Elements

A professional, extensible version of `precision_f1_recall.py`. Same
methodology, same exact-match-with-alias-map normalization (including the
IL-1A/IL-1B distinction fix), and the same publication-quality chart style
-- but now:
  - narratives can be added/removed freely, not fixed at 5
  - each narrative's display name (what shows on the bar chart) is
    optional -- leave it blank and it defaults to "Narrative I",
    "Narrative II", "Narrative III", ... in order; renaming is only for
    when you want a more descriptive label
  - a "Known elements" master pick-list (section 1) feeds Ground truth
    and every narrative's own elements as multiselect dropdowns, instead
    of free-typed text boxes -- a name only has to be spelled correctly
    once. Typing a brand-new element directly into Ground truth or a
    narrative's box still works too, without adding it to the master
    list first. This matters because Ground truth is deliberately just
    the elements you're checking recovery of -- it is NOT the same thing
    as every element that ever shows up in a narrative (narratives
    routinely mention extra elements Ground truth was never meant to
    include, e.g. GDF-15 below); the master list is what lets you see
    and pick from the full inventory without hunting back through every
    narrative to find how a name was spelled there.
  - the ground truth list, the alias/synonym map, and every narrative's
    elements are all editable in the browser, with live recompute

Verified against the original script's validated output: loading this
page with its defaults (unchanged) reproduces narrative_precision_recall_f1.csv
exactly -- Narratives I-V: P = 0.86/0.89/1.00/0.78/1.00,
R = 0.60/0.80/0.80/0.70/0.60, F1 = 0.71/0.84/0.89/0.74/0.75.
"""

import io

import pandas as pd
import streamlit as st

from branding import inject_style, render_header
from scoring_core import parse_elements, parse_alias_map, normalize_set, prf, pooled_prf, to_roman
from chart_build import build_grouped_bar_chart

inject_style()
render_header("F1-Score vs Ground Truth Elements")

st.caption(
    "One shared ground-truth element list is compared against each narrative's own "
    "elements -- both picked from the master list in section 1 below (or typed fresh on "
    "the spot). Matching is exact string match after trimming whitespace and applying the "
    "alias map below (not case-folding by default) -- so IL-1A and IL-1B stay distinct "
    "unless you say otherwise."
)

# ---------------- defaults, taken verbatim from precision_f1_recall.py ----------------
DEFAULT_GROUND_TRUTH = [
    "IL-A", "IL-B", "MMP-8", "EGF", "PDGF", "B-cell",
    "Lactobacillus rhamnosus", "Anaeroglobus geminatus",
    "Dialister invisus", "Brevundimonas diminuta",
]

DEFAULT_ALIAS_MAP = """IL-1B -> IL-B
IL-1A -> IL-A
B-cells -> B-cell"""

DEFAULT_NARRATIVE_ELEMENTS = [
    ["IL-1B", "MMP-8", "Lactobacillus rhamnosus", "EGF", "PDGF", "GDF-15", "B-cells"],
    ["MMP-8", "IL-1B", "EGF", "PDGF", "Lactobacillus paracasei", "Lactobacillus rhamnosus",
     "Anaeroglobus geminatus", "Dialister invisus", "B-cell"],
    ["IL-1B", "MMP-8", "Lactobacillus rhamnosus", "PDGF", "B-cell",
     "Anaeroglobus geminatus", "Dialister invisus", "EGF"],
    ["B-cells", "IL-1B", "MMP-8", "Lactobacillus rhamnosus", "EGF", "PDGF", "GDF-15",
     "Brevundimonas diminuta", "Eggerthia catenaformis"],
    ["MMP-8", "IL-1B", "Lactobacillus rhamnosus", "EGF", "B-cell", "PDGF"],
]


def _default_known_elements():
    """Every element that appears anywhere in the defaults above (Ground
    truth ∪ all narratives), in first-seen order, deduplicated -- this is
    what makes the master list start out already showing the full
    inventory instead of just Ground truth's narrower subset."""
    seen = []
    for e in DEFAULT_GROUND_TRUTH:
        if e not in seen:
            seen.append(e)
    for elems in DEFAULT_NARRATIVE_ELEMENTS:
        for e in elems:
            if e not in seen:
                seen.append(e)
    return seen


DEFAULT_KNOWN_TEXT = "\n".join(_default_known_elements())

# ---------------- session state ----------------
# Each narrative gets a permanent, never-reused numeric id (separate from
# its position in the list). Widget keys below are built from this id, not
# from list position -- if keys were position-based (e.g. f"name_{i}"),
# removing a narrative from the middle would shift every later row into a
# lower-numbered key, and Streamlit would keep showing that key's OLD
# cached text instead of the row's real content. Fresh ids on every
# add/reset also mean there's never a stale leftover key to collide with.
# "f1_known" and "f1_ground_truth_select" below are each read/written
# through ONE key only -- the widget's own -- rather than a separate
# shadow variable synced via a "value=" argument. A keyed widget treats
# its own session_state entry as the single source of truth from its
# second render onward and silently ignores any "value"/"default"
# argument passed after that, so a shadow-variable-plus-value= pattern
# can't actually be reset from a callback (only the shadow variable would
# change, not what the widget displays); pre-seeding the real key here
# and never passing value=/default= once it exists avoids that trap.
if "f1_known" not in st.session_state:
    st.session_state.f1_known = DEFAULT_KNOWN_TEXT
if "f1_ground_truth_select" not in st.session_state:
    st.session_state.f1_ground_truth_select = list(DEFAULT_GROUND_TRUTH)
if "alias_map_text" not in st.session_state:
    st.session_state.alias_map_text = DEFAULT_ALIAS_MAP
if "case_insensitive" not in st.session_state:
    st.session_state.case_insensitive = False
if "next_id" not in st.session_state:
    st.session_state.next_id = 0
if "narratives" not in st.session_state:
    st.session_state.narratives = []
    for elems in DEFAULT_NARRATIVE_ELEMENTS:
        nid = st.session_state.next_id
        st.session_state.next_id += 1
        st.session_state.narratives.append({"id": nid, "name": "", "elements": list(elems)})
if "generated" not in st.session_state:
    st.session_state.generated = True  # show the validated defaults immediately on first load


def add_narrative():
    nid = st.session_state.next_id
    st.session_state.next_id += 1
    st.session_state.narratives.append({"id": nid, "name": "", "elements": []})


def remove_narrative(nid):
    st.session_state.narratives = [n for n in st.session_state.narratives if n["id"] != nid]


def reset_all():
    # Overwrite each widget's OWN key directly (see the note above) --
    # this callback runs before the next rerun re-creates the widgets, so
    # they'll pick up these values as their current state, not just as an
    # ignored initial default.
    st.session_state.f1_known = DEFAULT_KNOWN_TEXT
    st.session_state.f1_ground_truth_select = list(DEFAULT_GROUND_TRUTH)
    st.session_state.alias_map_text = DEFAULT_ALIAS_MAP
    st.session_state.case_insensitive = False
    st.session_state.narratives = []
    for elems in DEFAULT_NARRATIVE_ELEMENTS:
        nid = st.session_state.next_id
        st.session_state.next_id += 1
        st.session_state.narratives.append({"id": nid, "name": "", "elements": list(elems)})
    st.session_state.generated = True


# ---------------- 1. known elements (master pick-list) ----------------
st.subheader("1. Known elements (optional)")
st.text_area(
    "Known elements", height=100, key="f1_known", label_visibility="collapsed",
    placeholder="One per line, or comma/semicolon-separated -- e.g. IL-1B, IL-17, GDF-15",
    help="An optional master list of every element in play across Ground truth and the "
         "narratives -- populates the pick-lists below so a name only has to be spelled "
         "correctly once, and every box can pick from the same full inventory rather than "
         "just its own subset. Typing a brand-new element directly into Ground truth or a "
         "narrative's box works too, without adding it here first. This list itself has no "
         "effect on the score -- only what's actually picked in Ground truth and each "
         "narrative below does.",
)
known_elements = parse_elements(st.session_state.f1_known)

# ---------------- 2. ground truth ----------------
st.subheader("2. Ground truth elements (shared across all narratives)")
gt_options = list(dict.fromkeys(known_elements + st.session_state.f1_ground_truth_select))
st.multiselect(
    "Ground truth elements", options=gt_options, key="f1_ground_truth_select",
    accept_new_options=True,
    placeholder="Pick known elements, or type a new one and press Enter",
    label_visibility="collapsed",
)

# ---------------- 3. normalization / alias map ----------------
with st.expander("Advanced: normalization / synonym map (optional)", expanded=False):
    st.markdown(
        "Elements are matched **exactly** (after trimming whitespace) unless you map one "
        "spelling to another below. One mapping per line, as `raw -> canonical`. "
        "\n\n**Note:** IL-1A and IL-1B are *not* biologically equivalent -- they are distinct "
        "interleukin-1 family cytokines. Map each to its own canonical form; never map one "
        "to the other, or every real IL-1B detection would be silently credited as IL-1A "
        "(and vice versa)."
    )
    st.text_area(
        "Alias / synonym map", height=100, key="alias_map_text",
        label_visibility="collapsed",
    )
    st.checkbox(
        "Case-insensitive matching (lowercase everything before comparing)",
        key="case_insensitive",
    )

# ---------------- 4. narratives ----------------
st.subheader("3. Narratives")
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
        elem_options = list(dict.fromkeys(known_elements + n["elements"]))
        n["elements"] = st.multiselect(
            "Elements", options=elem_options, default=n["elements"], key=f"elems_{nid}",
            accept_new_options=True,
            placeholder="Pick known elements, or type a new one and press Enter",
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
    st.session_state.f1_ground_truth_select, alias_map, case_insensitive
)

rows = []
for i, n in enumerate(st.session_state.narratives):
    if not n["elements"]:
        continue
    predicted_set = normalize_set(n["elements"], alias_map, case_insensitive)
    display_name = n["name"].strip() or f"Narrative {to_roman(i + 1)}"
    result = prf(ground_truth_set, predicted_set)
    result["narrative"] = display_name
    rows.append(result)

if not ground_truth_set:
    st.warning("Pick at least one ground-truth element above to compute scores.")
    st.stop()
if not rows:
    st.info("Pick elements for at least one narrative above to see scores.")
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

st.subheader("4. Results")
st.dataframe(
    results_df.style.format({"Precision": "{:.2f}", "Recall": "{:.2f}", "F1": "{:.2f}"}),
    width="stretch",
)

# ---------------- chart ----------------
st.subheader("5. Chart")
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

st.subheader("6. Downloads")
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
