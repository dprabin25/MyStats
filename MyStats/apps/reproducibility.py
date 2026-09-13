"""
MyStats tool: Reproducibility (V-measure)

For each mechanism, list the elements you're tracking, then paste each
run's groups directly -- e.g. what BioShift's own output already says
shifts together, as explicit lists:

    Group 1: MMP-8, EGF, PDGF
    Group 2: IL-1a, IL-1b, GDF-15
    Group 3: B-cell

(groups can go one per line, or all on one line separated by ";" --
either way works, and the "Group N:" label is optional and never
treated as an element). The app scores how well every pair of runs'
groupings agree using V-measure, a symmetric cluster-agreement score --
no run has to be "ground truth." A tracked element a run's groups never
mention at all still counts, as its own singleton group -- that's a
real disagreement ("not recovered by this run"), not something to
quietly drop from the score. Averaging over all run pairs gives one
reproducibility number per mechanism; averaging across mechanisms gives
one overall number.
"""

import pandas as pd
import streamlit as st

from branding import inject_style, render_header
from chart_build import build_single_series_bar_chart
from reproducibility_core import (
    parse_element_list,
    parse_groups,
    build_labels,
    mechanism_reproducibility,
    build_occurrence_table,
)

inject_style()
render_header("Reproducibility (V-measure)")

st.caption(
    "For each mechanism: list the elements you're tracking, then paste each run's groups of "
    "elements that shift together. The app compares the groups across runs -- and flags "
    "elements that didn't get grouped in every run -- with V-measure."
)

# ---------------- session state ----------------
# Same stable-id pattern as the other MyStats tools: widget keys are
# built from permanent ids (mechanism id + run id), not list position,
# so removing a row never leaves another row showing stale cached text.
if "rep_next_mech_id" not in st.session_state:
    st.session_state.rep_next_mech_id = 0


def _blank_mechanism(n_runs=3):
    mid = st.session_state.rep_next_mech_id
    st.session_state.rep_next_mech_id += 1
    runs = [{"id": i, "name": "", "text": "", "mentioned_text": ""} for i in range(n_runs)]
    return {"id": mid, "name": "", "tracked_text": "", "runs": runs, "next_run_id": n_runs}


if "rep_mechanisms" not in st.session_state:
    st.session_state.rep_mechanisms = [_blank_mechanism(n_runs=3)]
if "rep_generated" not in st.session_state:
    st.session_state.rep_generated = False


def add_mechanism():
    st.session_state.rep_mechanisms.append(_blank_mechanism(n_runs=3))


def remove_mechanism(mid):
    st.session_state.rep_mechanisms = [m for m in st.session_state.rep_mechanisms if m["id"] != mid]


def add_run(mechanism):
    rid = mechanism["next_run_id"]
    mechanism["next_run_id"] += 1
    mechanism["runs"].append({"id": rid, "name": "", "text": "", "mentioned_text": ""})


def remove_run(mechanism, rid):
    mechanism["runs"] = [r for r in mechanism["runs"] if r["id"] != rid]


def reset_all():
    st.session_state.rep_mechanisms = [_blank_mechanism(n_runs=3)]
    st.session_state.rep_generated = False


st.subheader("1. Mechanisms")
top_cols = st.columns([1, 1, 5])
top_cols[0].button("➕ Add mechanism", on_click=add_mechanism, width="stretch", key="rep_add_mech")
top_cols[1].button("↺ Reset all", on_click=reset_all, width="stretch", key="rep_reset")

for m in st.session_state.rep_mechanisms:
    mid = m["id"]
    with st.container(border=True):
        header_cols = st.columns([5, 1])
        m["name"] = header_cols[0].text_input(
            "Mechanism name", value=m["name"], key=f"rep_mech_name_{mid}",
            placeholder="e.g. IL-1/TNF-driven inflammatory cascade",
        )
        header_cols[1].button(
            "🗑 Remove mechanism", key=f"rep_mech_remove_{mid}",
            on_click=remove_mechanism, args=(mid,), width="stretch",
        )
        m["tracked_text"] = st.text_area(
            "Elements to track", value=m["tracked_text"], key=f"rep_tracked_{mid}", height=100,
            placeholder="MMP-8, EGF, PDGF, IL-1a, IL-1b, GDF-15, B-cell,\nAnaeroglobus geminatus, Dialister invisus, Lactobacillus rhamnosus",
            help="One per line, or comma/semicolon-separated (multi-word names like species are "
                 "fine -- just don't split them across a comma). Every element listed here gets "
                 "scored in every run -- if a run's groups never mention one, it still counts, as "
                 "that run's own ungrouped ('not recovered') element.",
        )

        st.markdown("**Runs**")
        for r in m["runs"]:
            rid = r["id"]
            run_cols = st.columns([3, 1])
            r["name"] = run_cols[0].text_input(
                "Run name", value=r["name"], key=f"rep_run_name_{mid}_{rid}",
                placeholder=f"Run {rid + 1}", label_visibility="collapsed",
            )
            run_cols[1].button(
                "🗑 Remove run", key=f"rep_run_remove_{mid}_{rid}",
                on_click=remove_run, args=(m, rid), width="stretch",
            )
            r["text"] = st.text_area(
                "Run groups", value=r["text"], key=f"rep_run_text_{mid}_{rid}", height=140,
                placeholder=(
                    "Group 1: MMP-8, EGF, PDGF\n"
                    "Group 2: IL-1a, IL-1b, GDF-15\n"
                    "(one group per line, or separate groups with \";\" -- \"Group N:\" labels are optional)"
                ),
                label_visibility="collapsed",
            )
            r["mentioned_text"] = st.text_input(
                "Mentioned but not in a group (optional)", value=r["mentioned_text"],
                key=f"rep_run_mentioned_{mid}_{rid}",
                placeholder="Mentioned but not in a group (optional), e.g. B-cell, MIP-1D",
                help="Elements this run's output mentions on their own, not as part of any "
                     "co-shifting group -- each one is scored as its own group of one, same as "
                     "if you'd written it as \"Group N: <element>\" above, just without cluttering "
                     "the group numbering.",
            )
        st.button("➕ Add run", on_click=add_run, args=(m,), key=f"rep_add_run_{mid}")

st.button("➕ Add mechanism", on_click=add_mechanism, key="rep_add_mech_bottom")

st.divider()
if st.button("🔄 Generate reproducibility scores", type="primary", width="stretch", key="rep_generate"):
    st.session_state.rep_generated = True

if not st.session_state.rep_generated:
    st.info("Click **Generate reproducibility scores** above once you've entered tracked elements and at least 2 runs per mechanism.")
    st.stop()

# ---------------- compute ----------------
mech_summary_rows = []
all_pair_rows = []
all_occurrence_rows = []
chart_labels, chart_values = [], []

for i, m in enumerate(st.session_state.rep_mechanisms):
    mech_name = m["name"].strip() or f"Mechanism {i + 1}"
    tracked = parse_element_list(m["tracked_text"])
    runs_with_text = m["runs"]
    run_names = [r["name"].strip() or f"Run {j + 1}" for j, r in enumerate(runs_with_text)]

    if not tracked:
        st.warning(f"**{mech_name}**: no tracked elements listed -- skipped.")
        continue
    if len(runs_with_text) < 2:
        st.warning(f"**{mech_name}**: need at least 2 runs to compute reproducibility -- skipped.")
        continue

    groups_per_run = [
        parse_groups(r["text"]) + [[e] for e in parse_element_list(r.get("mentioned_text", ""))]
        for r in runs_with_text
    ]
    run_labels = [build_labels(g, tracked_elements=tracked) for g in groups_per_run]
    result = mechanism_reproducibility(run_names, run_labels)

    avg = result["average_v_measure"]
    mech_summary_rows.append({
        "Mechanism": mech_name,
        "Average V-measure": round(avg, 4) if avg is not None else None,
        "Valid pairs": result["n_valid_pairs"],
        "Runs": len(run_names),
        "Tracked elements": len(tracked),
    })
    for pair in result["pairs"]:
        all_pair_rows.append({"Mechanism": mech_name, **pair})
    for occ_row in build_occurrence_table(tracked, groups_per_run, run_names):
        all_occurrence_rows.append({"Mechanism": mech_name, **occ_row})
    if avg is not None:
        chart_labels.append(mech_name)
        chart_values.append(avg)

if not mech_summary_rows:
    st.info("Nothing to score yet -- add tracked elements and at least 2 runs to a mechanism above.")
    st.stop()

summary_df = pd.DataFrame(mech_summary_rows)
pairs_df = pd.DataFrame(all_pair_rows)
occurrence_df = pd.DataFrame(all_occurrence_rows)

st.subheader("2. Reproducibility summary")
valid_scores = [r["Average V-measure"] for r in mech_summary_rows if r["Average V-measure"] is not None]
overall = sum(valid_scores) / len(valid_scores) if valid_scores else None
st.metric("Overall reproducibility (mean across mechanisms)", f"{overall:.4f}" if overall is not None else "N/A")
st.dataframe(summary_df, width="stretch", hide_index=True)

if chart_values:
    fig = build_single_series_bar_chart(
        labels=chart_labels, values=chart_values,
        title="Reproducibility (Average V-measure) by Mechanism",
        xlabel="Mechanism", ylabel="V-measure", value_format="{:.2f}",
    )
    st.pyplot(fig)

st.subheader("3. Element occurrence across runs")
st.caption(
    "Did each tracked element show up at all in each run's groups -- separate from whether it "
    "was grouped the same way. A count below the number of runs means that element wasn't "
    "recovered consistently."
)
st.dataframe(occurrence_df, width="stretch", hide_index=True)

st.subheader("4. Pairwise breakdown")
st.dataframe(pairs_df, width="stretch", hide_index=True)

st.subheader("5. Downloads")
dl_cols = st.columns(3)
dl_cols[0].download_button(
    "⬇ CSV (reproducibility_summary.csv)", data=summary_df.to_csv(index=False),
    file_name="reproducibility_summary.csv", mime="text/csv", width="stretch",
)
dl_cols[1].download_button(
    "⬇ CSV (reproducibility_occurrence.csv)", data=occurrence_df.to_csv(index=False),
    file_name="reproducibility_occurrence.csv", mime="text/csv", width="stretch",
)
dl_cols[2].download_button(
    "⬇ CSV (reproducibility_pairwise.csv)", data=pairs_df.to_csv(index=False),
    file_name="reproducibility_pairwise.csv", mime="text/csv", width="stretch",
)
if chart_values:
    import io
    png_buf = io.BytesIO()
    fig.savefig(png_buf, format="png", dpi=300, bbox_inches="tight", facecolor="white")
    st.download_button(
        "⬇ Chart PNG (300 dpi)", data=png_buf.getvalue(),
        file_name="reproducibility_chart.png", mime="image/png", width="stretch",
    )
