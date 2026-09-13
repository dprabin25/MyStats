"""
MyStats tool: Reproducibility (V-measure)

For each mechanism, paste the narrative text from each run (e.g.
BioShift's prompt-3 output) plus the list of elements you're tracking
for that mechanism. The app finds which tracked elements each run
mentions together in the same sentence -- that implies a grouping
("these elements shift together") for that run -- then scores how well
every pair of runs' groupings agree using V-measure, a symmetric
cluster-agreement score (no run has to be "ground truth"). An element a
run never mentions at all still counts, as its own singleton group --
that's a real disagreement ("not recovered by this run"), not something
to quietly drop from the score. Averaging over all run pairs gives one
reproducibility number per mechanism; averaging across mechanisms gives
one overall number.

Caveat worth knowing: grouping is same-sentence co-occurrence, so a
sentence that lists several elements while saying they're NOT related
("X, Y, and Z were each discussed independently") will still group them
-- it isn't reading the negation, just proximity. Keep tracked-element
lists focused and check the pairwise breakdown if a score looks off.
"""

import pandas as pd
import streamlit as st

from branding import inject_style, render_header
from chart_build import build_single_series_bar_chart
from reproducibility_core import (
    parse_element_list,
    build_labels_from_narrative,
    mechanism_reproducibility,
)

inject_style()
render_header("Reproducibility (V-measure)")

st.caption(
    "For each mechanism: list the elements you're tracking, then paste each run's narrative. "
    "The app detects which tracked elements are mentioned together in the same sentence, "
    "treats that as one run's grouping, and scores run-to-run agreement with V-measure."
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
    runs = [{"id": i, "name": "", "text": ""} for i in range(n_runs)]
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
    mechanism["runs"].append({"id": rid, "name": "", "text": ""})


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
            "Elements to track", value=m["tracked_text"], key=f"rep_tracked_{mid}", height=80,
            placeholder="IL-1, TNF, IL-6, MMP-8, MMP-9",
            help="One per line, or comma/semicolon-separated. Every element listed here gets "
                 "scored in every run -- if a run's narrative never mentions one, it still counts, "
                 "as that run's own ungrouped element.",
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
                "Run narrative", value=r["text"], key=f"rep_run_text_{mid}_{rid}", height=140,
                placeholder="Paste this run's narrative text for this mechanism...",
                label_visibility="collapsed",
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

    run_labels = [build_labels_from_narrative(r["text"], tracked) for r in runs_with_text]
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
    if avg is not None:
        chart_labels.append(mech_name)
        chart_values.append(avg)

if not mech_summary_rows:
    st.info("Nothing to score yet -- add tracked elements and at least 2 runs to a mechanism above.")
    st.stop()

summary_df = pd.DataFrame(mech_summary_rows)
pairs_df = pd.DataFrame(all_pair_rows)

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

st.subheader("3. Pairwise breakdown")
st.dataframe(pairs_df, width="stretch", hide_index=True)

st.subheader("4. Downloads")
dl_cols = st.columns(2)
dl_cols[0].download_button(
    "⬇ CSV (reproducibility_summary.csv)", data=summary_df.to_csv(index=False),
    file_name="reproducibility_summary.csv", mime="text/csv", width="stretch",
)
dl_cols[1].download_button(
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
