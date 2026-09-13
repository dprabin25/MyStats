"""
MyStats tool: Known vs Unknown (Biological-Meaning Concordance)

A Streamlit port of the standalone "BioShift Known-vs-Unknown"
desktop script -- same relationship-table parser, same direction
classification (Increase/Decrease/Associative/Contradictory, with the
depletion/knockdown exclusion rule), same pairwise concordance math and
Known/Unknown roll-up. The one real change: a "run" comes from an
uploaded .txt file plus a Known/Unknown tag you pick here, instead of
being auto-discovered from a folder structure on disk -- a hosted app
has no access to your computer's filesystem, so upload replaces that.

What it measures: for every pair of runs, DIRECTION CONCORDANCE = of
the element-pairs BOTH runs discuss, what fraction do they agree on
the direction of (does X increase or decrease Y). This is a
biology-level agreement measure -- it asks whether two runs assert the
same mechanism, not whether their wording is similar. Comparisons are
rolled up into within-Known, within-Unknown, and Known-vs-Unknown
means.
"""

import io

import pandas as pd
import streamlit as st

from branding import inject_style, render_header
from chart_build import build_mean_std_bar_chart
from scoring_core import parse_alias_map
from known_vs_unknown_core import (
    parse_relationship_table, pairs_with_direction, pairwise_concordance,
    DEFAULT_ALIAS_MAP_TEXT,
)

inject_style()
render_header("Known vs Unknown (Biological-Meaning Concordance)")

st.caption(
    "Upload each run's CaseStudy_Prompt3_output.txt (or paste its relationship-table text "
    "below), tag it Known or Unknown, and this scores DIRECTION CONCORDANCE for every pair of "
    "runs -- of the element-pairs both discuss, what fraction do they agree increases vs. "
    "decreases the other -- then rolls that up into within-Known / within-Unknown / "
    "Known-vs-Unknown means."
)

# ---------------- session state ----------------
if "kvu_alias_text" not in st.session_state:
    st.session_state.kvu_alias_text = DEFAULT_ALIAS_MAP_TEXT
if "kvu_next_id" not in st.session_state:
    st.session_state.kvu_next_id = 0
if "kvu_runs" not in st.session_state:
    st.session_state.kvu_runs = []
if "kvu_generated" not in st.session_state:
    st.session_state.kvu_generated = False


def _guess_condition(filename):
    return "Unknown" if "unknown" in filename.lower() else "Known"


def add_run():
    rid = st.session_state.kvu_next_id
    st.session_state.kvu_next_id += 1
    st.session_state.kvu_runs.append({"id": rid, "name": "", "condition": "Known", "text": ""})


def remove_run(rid):
    st.session_state.kvu_runs = [r for r in st.session_state.kvu_runs if r["id"] != rid]


def reset_all():
    st.session_state.kvu_alias_text = DEFAULT_ALIAS_MAP_TEXT
    st.session_state.kvu_runs = []
    st.session_state.kvu_generated = False


with st.expander("Advanced: element name normalization (optional)", expanded=False):
    st.markdown(
        "Elements are matched exactly as written in each file's \"List of elements\" column "
        "unless mapped here. One mapping per line, as `raw -> canonical` (same syntax as the "
        "F1-Score tool's alias map)."
    )
    st.session_state.kvu_alias_text = st.text_area(
        "Alias / synonym map", value=st.session_state.kvu_alias_text, height=80,
        label_visibility="collapsed",
    )
alias_map = parse_alias_map(st.session_state.kvu_alias_text)

st.subheader("1. Upload runs")
uploaded_files = st.file_uploader(
    "Upload CaseStudy_Prompt3_output.txt files (one per run)",
    type=["txt"], accept_multiple_files=True, key="kvu_uploader",
)
if uploaded_files:
    for f in uploaded_files:
        if f.name not in {r.get("_source") for r in st.session_state.kvu_runs}:
            rid = st.session_state.kvu_next_id
            st.session_state.kvu_next_id += 1
            st.session_state.kvu_runs.append({
                "id": rid, "name": f.name.rsplit(".", 1)[0], "condition": _guess_condition(f.name),
                "text": f.getvalue().decode("utf-8", errors="replace"),
                "_from_upload": True, "_source": f.name,
            })

st.caption(
    "Uploaded files are added as runs below (auto-tagged Known/Unknown by filename -- check "
    "and fix the tag). You can also add a run by hand and paste its text directly."
)
st.button("➕ Add run manually (paste text)", on_click=add_run, key="kvu_add_manual")

st.subheader("2. Runs")
top_cols = st.columns([1, 5])
top_cols[0].button("↺ Reset all", on_click=reset_all, width="stretch", key="kvu_reset")

for r in st.session_state.kvu_runs:
    rid = r["id"]
    with st.container(border=True):
        header_cols = st.columns([3, 2, 1])
        r["name"] = header_cols[0].text_input(
            "Run name", value=r["name"], key=f"kvu_name_{rid}", placeholder=f"Run {rid + 1}",
        )
        r["condition"] = header_cols[1].selectbox(
            "Condition", options=["Known", "Unknown"],
            index=["Known", "Unknown"].index(r["condition"]), key=f"kvu_cond_{rid}",
        )
        header_cols[2].button(
            "🗑 Remove", key=f"kvu_remove_{rid}", on_click=remove_run, args=(rid,), width="stretch",
        )
        if r.get("_from_upload"):
            st.caption(f"From uploaded file: {r['_source']}")
        else:
            r["text"] = st.text_area(
                "Relationship-table text", value=r["text"], key=f"kvu_text_{rid}", height=150,
                placeholder="Paste the file's content here (must include a '| Group Name | ... "
                            "| List of elements | ... | Evidence Summary | ...' table).",
            )

st.divider()
if st.button("🔄 Generate concordance results", type="primary", width="stretch", key="kvu_generate"):
    st.session_state.kvu_generated = True

if not st.session_state.kvu_generated:
    st.info("Click **Generate concordance results** above once you've added at least 2 runs.")
    st.stop()

# ---------------- compute ----------------
runs = st.session_state.kvu_runs
if len(runs) < 2:
    st.warning("Need at least 2 runs to compute concordance.")
    st.stop()

run_names = [r["name"].strip() or f"Run {j + 1}" for j, r in enumerate(runs)]
conditions = [r["condition"] for r in runs]

parsed_rows_by_run = []
parse_errors = []
for name, r in zip(run_names, runs):
    try:
        parsed_rows_by_run.append(parse_relationship_table(r["text"], alias_map))
    except ValueError as e:
        parse_errors.append(f"**{name}**: {e}")
        parsed_rows_by_run.append([])

if parse_errors:
    st.error(
        "Couldn't parse a relationship table from these runs (they're excluded below until "
        "fixed):\n\n" + "\n\n".join(parse_errors)
    )

if not any(parsed_rows_by_run):
    st.info("No relationship-table rows found in any run yet.")
    st.stop()

diagnostic_rows = []
for name, rows in zip(run_names, parsed_rows_by_run):
    for row in rows:
        diagnostic_rows.append({
            "Run": name, "Group Name": row["group_name"],
            "Elements": "; ".join(row["elements"]), "Direction": row["direction"],
        })
diagnostic_df = pd.DataFrame(diagnostic_rows)

pair_directions = [pairs_with_direction(rows) for rows in parsed_rows_by_run]
concord_records = pairwise_concordance(run_names, conditions, pair_directions)
concord_df = pd.DataFrame(concord_records)
# concordance_rate is None (not NaN) for a pair sharing zero element-pairs --
# coerce to NaN first so .round() doesn't choke on a plain None.
concord_df["concordance_rate"] = pd.to_numeric(concord_df["concordance_rate"], errors="coerce").round(4)

ORDER = ["within-Known", "within-Unknown", "Known-vs-Unknown"]
summary_rows = []
for comp in ORDER:
    subset = concord_df[(concord_df["comparison"] == comp) & concord_df["concordance_rate"].notna()]
    if len(subset) == 0:
        summary_rows.append({"comparison": comp, "mean": None, "std": None, "count": 0})
    else:
        summary_rows.append({
            "comparison": comp,
            "mean": round(subset["concordance_rate"].mean(), 4),
            "std": round(subset["concordance_rate"].std(), 4) if len(subset) > 1 else None,
            "count": len(subset),
        })
summary_df = pd.DataFrame(summary_rows)

st.subheader("3. Direction classification (per run)")
st.caption(
    "How each row's Group Name + Evidence Summary was classified -- check this before trusting "
    "the concordance numbers below, since classification is keyword-based."
)
st.dataframe(diagnostic_df, width="stretch", hide_index=True)

st.subheader("4. Pairwise direction concordance")
st.dataframe(concord_df.rename(columns={
    "pair": "Run pair", "comparison": "Comparison", "n_shared_relationships": "Shared element-pairs",
    "n_concordant": "Concordant", "concordance_rate": "Concordance rate",
}), width="stretch", hide_index=True)

st.subheader("5. Summary by comparison type")
st.dataframe(summary_df.rename(columns={
    "comparison": "Comparison", "mean": "Mean concordance", "std": "Std dev", "count": "Run pairs",
}), width="stretch", hide_index=True)

has_any_mean = summary_df["mean"].notna().any()
if has_any_mean:
    fig = build_mean_std_bar_chart(
        labels=ORDER,
        means=summary_df["mean"].tolist(),
        stds=summary_df["std"].tolist(),
        counts=summary_df["count"].tolist(),
        title="Biological-meaning concordance by comparison type",
        ylabel="Mean direction concordance",
    )
    st.pyplot(fig)

st.subheader("6. Downloads")
dl_cols = st.columns(4 if has_any_mean else 3)
dl_cols[0].download_button(
    "⬇ CSV (biological_meaning_concordance.csv)", data=concord_df.to_csv(index=False),
    file_name="biological_meaning_concordance.csv", mime="text/csv", width="stretch",
)
dl_cols[1].download_button(
    "⬇ CSV (biological_meaning_summary.csv)", data=summary_df.to_csv(index=False),
    file_name="biological_meaning_summary.csv", mime="text/csv", width="stretch",
)
dl_cols[2].download_button(
    "⬇ CSV (direction_classification.csv)", data=diagnostic_df.to_csv(index=False),
    file_name="direction_classification.csv", mime="text/csv", width="stretch",
)
if has_any_mean:
    png_buf = io.BytesIO()
    fig.savefig(png_buf, format="png", dpi=300, bbox_inches="tight", facecolor="white")
    pdf_buf = io.BytesIO()
    fig.savefig(pdf_buf, format="pdf", bbox_inches="tight", facecolor="white")
    dl_cols[3].download_button(
        "⬇ Chart PNG (300 dpi)", data=png_buf.getvalue(),
        file_name="biological_meaning_barplot.png", mime="image/png", width="stretch",
    )
    st.download_button(
        "⬇ Chart PDF (vector)", data=pdf_buf.getvalue(),
        file_name="biological_meaning_barplot.pdf", mime="application/pdf", width="stretch",
    )
