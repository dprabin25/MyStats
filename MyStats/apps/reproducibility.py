"""
MyStats tool: Reproducibility (V-measure)

For each mechanism, list the elements you're tracking, then for each
run build its groups by picking from that same tracked list (type a
name not on the list and it's added too) -- one multiselect per group,
plus a "Not grouped" multiselect for anything mentioned on its own.
Groups can be renamed, added, and removed freely per run.

The app scores how well every pair of runs' groupings agree using
V-measure, a symmetric cluster-agreement score -- no run has to be
"ground truth." A tracked element a run never places in any group (or
in "Not grouped") still counts, as its own singleton -- that's a real
disagreement ("not recovered by this run"), not something to quietly
drop from the score. Averaging over all run pairs gives one
reproducibility number per mechanism; averaging across mechanisms gives
one overall number.
"""

import pandas as pd
import streamlit as st

from branding import inject_style, render_header
from chart_build import build_single_series_bar_chart
from reproducibility_core import parse_element_list, build_labels, mechanism_reproducibility, build_occurrence_table

inject_style()
render_header("Reproducibility (V-measure)")

st.caption(
    "For each mechanism: list the elements you're tracking, then for each run pick which "
    "tracked elements belong in each group (add groups freely, rename them, or leave elements "
    "in \"Not grouped\"). The app compares the groups across runs -- and flags elements that "
    "didn't get grouped in every run -- with V-measure."
)

# ---------------- session state ----------------
# Same stable-id pattern as the other MyStats tools: widget keys are
# built from permanent ids (mechanism id + run id + group id), not list
# position, so removing a row never leaves another row showing stale
# cached values.
if "rep_next_mech_id" not in st.session_state:
    st.session_state.rep_next_mech_id = 0


def _blank_run(rid):
    return {"id": rid, "name": "", "groups": [{"id": 0, "name": "", "elements": []}],
            "not_grouped": [], "next_group_id": 1}


def _blank_mechanism(n_runs=3):
    mid = st.session_state.rep_next_mech_id
    st.session_state.rep_next_mech_id += 1
    runs = [_blank_run(i) for i in range(n_runs)]
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
    mechanism["runs"].append(_blank_run(rid))


def remove_run(mechanism, rid):
    mechanism["runs"] = [r for r in mechanism["runs"] if r["id"] != rid]


def add_group(run):
    gid = run["next_group_id"]
    run["next_group_id"] += 1
    run["groups"].append({"id": gid, "name": "", "elements": []})


def remove_group(run, gid):
    run["groups"] = [g for g in run["groups"] if g["id"] != gid]


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
            help="One per line, or comma/semicolon-separated. This becomes the default pick-list "
                 "for every group below -- you can still type something not on this list into any "
                 "group and it's added too.",
        )
        tracked = parse_element_list(m["tracked_text"])

        st.markdown("**Runs**")
        for r in m["runs"]:
            rid = r["id"]
            with st.container(border=True):
                run_cols = st.columns([3, 1])
                r["name"] = run_cols[0].text_input(
                    "Run name", value=r["name"], key=f"rep_run_name_{mid}_{rid}",
                    placeholder=f"Run {rid + 1}",
                )
                run_cols[1].button(
                    "🗑 Remove run", key=f"rep_run_remove_{mid}_{rid}",
                    on_click=remove_run, args=(m, rid), width="stretch",
                )

                for g in r["groups"]:
                    gid = g["id"]
                    group_cols = st.columns([2, 6, 1])
                    g["name"] = group_cols[0].text_input(
                        "Group name", value=g["name"], key=f"rep_group_name_{mid}_{rid}_{gid}",
                        placeholder=f"Group {gid + 1}", label_visibility="collapsed",
                    )
                    group_options = list(dict.fromkeys(tracked + g["elements"]))
                    g["elements"] = group_cols[1].multiselect(
                        "Elements", options=group_options, default=g["elements"],
                        key=f"rep_group_elems_{mid}_{rid}_{gid}", accept_new_options=True,
                        placeholder="Pick tracked elements, or type a new one and press Enter",
                        label_visibility="collapsed",
                    )
                    group_cols[2].button(
                        "🗑", key=f"rep_group_remove_{mid}_{rid}_{gid}",
                        on_click=remove_group, args=(r, gid), width="stretch",
                    )
                st.button("➕ Add group", on_click=add_group, args=(r,), key=f"rep_add_group_{mid}_{rid}")

                not_grouped_options = list(dict.fromkeys(tracked + r["not_grouped"]))
                r["not_grouped"] = st.multiselect(
                    "Not grouped (mentioned on their own)", options=not_grouped_options,
                    default=r["not_grouped"], key=f"rep_not_grouped_{mid}_{rid}",
                    accept_new_options=True,
                    placeholder="Elements this run mentions but doesn't group with anything else",
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
    declared_tracked = parse_element_list(m["tracked_text"])
    runs_with_text = m["runs"]
    run_names = [r["name"].strip() or f"Run {j + 1}" for j, r in enumerate(runs_with_text)]

    if not declared_tracked:
        st.warning(f"**{mech_name}**: no tracked elements listed -- skipped.")
        continue
    if len(runs_with_text) < 2:
        st.warning(f"**{mech_name}**: need at least 2 runs to compute reproducibility -- skipped.")
        continue

    groups_per_run = [
        [g["elements"] for g in r["groups"]] + [[e] for e in r["not_grouped"]]
        for r in runs_with_text
    ]

    # Effective tracked set: the declared list, plus anything actually
    # picked/typed anywhere for this mechanism (accept_new_options lets
    # a run add an element that was never on the declared list) -- this
    # keeps every such element in the "not recovered" completion logic
    # instead of silently dropping it.
    used = set(declared_tracked)
    for groups in groups_per_run:
        for g in groups:
            used.update(g)
    tracked = declared_tracked + sorted(used - set(declared_tracked))

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
    "Did each tracked element show up at all in each run (grouped or in \"Not grouped\") -- "
    "separate from whether it was grouped the same way. A count below the number of runs means "
    "that element wasn't recovered consistently."
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
