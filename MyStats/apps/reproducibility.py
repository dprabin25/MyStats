"""
MyStats tool: Reproducibility (V-measure)

For each mechanism, list the elements you're tracking, then for each
run build its groups by picking from that same tracked list (type a
name not on the list and it's added too) -- one multiselect per group,
plus as many numbered "Ungrouped" rows as needed for elements mentioned
on their own (one element each). Groups and ungrouped rows can be
added, removed, and (for groups) renamed freely per run.

The app scores how well every pair of runs' groupings agree using
V-measure, a symmetric cluster-agreement score -- no run has to be
"ground truth." It reports TWO versions of that score, side by side,
since they answer different questions:

- "Recovered elements only": scores agreement using only elements each
  run actually placed somewhere (grouped or "Ungrouped") -- an element
  neither run mentions at all doesn't enter this one. Answers "when
  both runs talk about the same things, do they group them the same
  way?"
- "Recovered + not recovered": the stricter version -- every tracked
  element gets a label in every run, and one a run never mentions at
  all still counts, as its own singleton. Answers the same question
  PLUS "did both runs even recover the same elements?" -- an omission
  counts against the score here, not just a different grouping choice.

Averaging over all run pairs gives one reproducibility number per
mechanism (for each version); averaging across mechanisms gives one
overall number.
"""

import pandas as pd
import streamlit as st

from branding import inject_style, render_header
from chart_build import build_single_series_bar_chart
from reproducibility_core import parse_element_list, build_labels, mechanism_reproducibility, build_occurrence_table

inject_style()
render_header("Reproducibility (V-measure)")

# Default tracked-elements list -- pre-fills every new mechanism's
# "Elements to track" box so it doesn't need retyping; still fully
# editable per mechanism.
DEFAULT_TRACKED_ELEMENTS = [
    "MMP-8", "MIP-1D", "EGF", "PDGF", "IL-1α", "IL-1β", "GDF-15", "B-cell",
    "Anaeroglobus geminatus", "Bacteroidetes bacterium oral taxon 272",
    "Brevundimonas diminuta", "Dialister invisus", "Dialister micraerophilus",
    "Eggerthia catenaformis", "Fusobacteria bacterium oral taxon 220",
    "Fusobacterium naviforme", "Lactobacillus paracasei", "Lactobacillus rhamnosus",
    "Leptotrichia wadei", "Streptococcus constellatus", "Streptococcus mitis",
    "Streptococcus salivarius", "Streptococcus sanguinis",
    "Streptococcus sp. oral taxon 064", "Veillonella atypica",
    "Xanthomonas sp. oral taxon 037", "Lactobacillus panis",
]
DEFAULT_TRACKED_TEXT = ", ".join(DEFAULT_TRACKED_ELEMENTS)

st.caption(
    "For each mechanism: list the elements you're tracking, then for each run pick which "
    "tracked elements belong in each group (add groups freely, rename them, or leave elements "
    "in \"Ungrouped\"). The app scores run-to-run agreement two ways: on recovered elements "
    "only, and on recovered + not-recovered elements together -- see the summary below."
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
            "ungrouped": [], "next_group_id": 1, "next_ungrouped_id": 0}


def _blank_mechanism(n_runs=3):
    mid = st.session_state.rep_next_mech_id
    st.session_state.rep_next_mech_id += 1
    runs = [_blank_run(i) for i in range(n_runs)]
    return {"id": mid, "name": "", "tracked_text": DEFAULT_TRACKED_TEXT, "runs": runs, "next_run_id": n_runs}


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


def add_ungrouped(run):
    uid = run["next_ungrouped_id"]
    run["next_ungrouped_id"] += 1
    run["ungrouped"].append({"id": uid, "element": None})


def remove_ungrouped(run, uid):
    run["ungrouped"] = [u for u in run["ungrouped"] if u["id"] != uid]


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

                for gi, g in enumerate(r["groups"]):
                    gid = g["id"]
                    group_cols = st.columns([2, 6, 1])
                    g["name"] = group_cols[0].text_input(
                        "Group name", value=g["name"], key=f"rep_group_name_{mid}_{rid}_{gid}",
                        placeholder=f"Group {gi + 1}", label_visibility="collapsed",
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

                for ui, u in enumerate(r["ungrouped"]):
                    uid = u["id"]
                    ungrouped_cols = st.columns([2, 6, 1])
                    ungrouped_cols[0].markdown(f"Ungrouped {ui + 1}")
                    ungrouped_options = list(dict.fromkeys(tracked + ([u["element"]] if u["element"] else [])))
                    u["element"] = ungrouped_cols[1].selectbox(
                        "Element", options=ungrouped_options, index=None, key=f"rep_ungrouped_elem_{mid}_{rid}_{uid}",
                        accept_new_options=True, placeholder="Pick one tracked element, or type a new one",
                        label_visibility="collapsed",
                    )
                    ungrouped_cols[2].button(
                        "🗑", key=f"rep_ungrouped_remove_{mid}_{rid}_{uid}",
                        on_click=remove_ungrouped, args=(r, uid), width="stretch",
                    )
                st.button("➕ Add ungrouped", on_click=add_ungrouped, args=(r,), key=f"rep_add_ungrouped_{mid}_{rid}")
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
chart_labels = []
chart_values_recovered, chart_values_completed = [], []

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
        [g["elements"] for g in r["groups"]] + [[u["element"]] for u in r["ungrouped"] if u["element"]]
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

    # Two scoring modes, computed from the same groups:
    # - "recovered only": no completion -- an element neither run
    #   mentions at all simply isn't part of the comparison.
    # - "recovered + not recovered": today's default -- every tracked
    #   element gets a label in every run, so a run that never mentions
    #   one gets it as its own singleton, and that omission counts.
    recovered_labels = [build_labels(g, tracked_elements=None) for g in groups_per_run]
    completed_labels = [build_labels(g, tracked_elements=tracked) for g in groups_per_run]
    result_recovered = mechanism_reproducibility(run_names, recovered_labels)
    result_completed = mechanism_reproducibility(run_names, completed_labels)

    occ_rows = build_occurrence_table(tracked, groups_per_run, run_names)
    n_runs = len(run_names)
    n_unrecovered = sum(1 for row in occ_rows if row["Runs occurring in"] < n_runs)
    pct_unrecovered = round(100 * n_unrecovered / len(tracked), 1) if tracked else None

    avg_recovered = result_recovered["average_v_measure"]
    avg_completed = result_completed["average_v_measure"]
    mech_summary_rows.append({
        "Mechanism": mech_name,
        "Average V-measure (recovered only)": round(avg_recovered, 4) if avg_recovered is not None else None,
        "Average V-measure (recovered + not recovered)": round(avg_completed, 4) if avg_completed is not None else None,
        "% Unrecovered (not in every run)": pct_unrecovered,
        "Valid pairs": result_completed["n_valid_pairs"],
        "Runs": n_runs,
        "Tracked elements": len(tracked),
    })
    # One pairwise row per run pair: both V-measure versions, plus the
    # element-level breakdown (Common / Common not recovered / Ungrouped)
    # -- that breakdown is inherently about recovery, so it comes from
    # the "recovered + not recovered" pass. Both mechanism_reproducibility
    # calls walk run pairs in the same (i, j) order, so zipping is safe.
    for pair_recovered, pair_completed in zip(result_recovered["pairs"], result_completed["pairs"]):
        all_pair_rows.append({
            "Mechanism": mech_name,
            "Run A": pair_completed["Run A"],
            "Run B": pair_completed["Run B"],
            "V-measure (recovered only)": pair_recovered["V-measure"],
            "V-measure (recovered + not recovered)": pair_completed["V-measure"],
            "Common elements": pair_completed["Common elements"],
            "Common not recovered elements": pair_completed["Common not recovered elements"],
            "Ungrouped elements": pair_completed["Ungrouped elements"],
        })
    for occ_row in occ_rows:
        all_occurrence_rows.append({"Mechanism": mech_name, **occ_row})
    if avg_recovered is not None or avg_completed is not None:
        chart_labels.append(mech_name)
        chart_values_recovered.append(avg_recovered if avg_recovered is not None else 0.0)
        chart_values_completed.append(avg_completed if avg_completed is not None else 0.0)

if not mech_summary_rows:
    st.info("Nothing to score yet -- add tracked elements and at least 2 runs to a mechanism above.")
    st.stop()

summary_df = pd.DataFrame(mech_summary_rows)
pairs_df = pd.DataFrame(all_pair_rows)
occurrence_df = pd.DataFrame(all_occurrence_rows)

st.subheader("2. Reproducibility summary")
st.caption(
    "Two versions of the same score: **recovered only** looks purely at whether elements both "
    "runs mentioned got grouped the same way; **recovered + not recovered** also counts it "
    "against the score when a run never mentions a tracked element at all."
)
valid_recovered = [r["Average V-measure (recovered only)"] for r in mech_summary_rows if r["Average V-measure (recovered only)"] is not None]
overall_recovered = sum(valid_recovered) / len(valid_recovered) if valid_recovered else None
valid_completed = [r["Average V-measure (recovered + not recovered)"] for r in mech_summary_rows if r["Average V-measure (recovered + not recovered)"] is not None]
overall_completed = sum(valid_completed) / len(valid_completed) if valid_completed else None
valid_pcts = [r["% Unrecovered (not in every run)"] for r in mech_summary_rows if r["% Unrecovered (not in every run)"] is not None]
overall_pct_unrecovered = sum(valid_pcts) / len(valid_pcts) if valid_pcts else None

metric_cols = st.columns(3)
metric_cols[0].metric(
    "Overall reproducibility -- recovered only",
    f"{overall_recovered:.4f}" if overall_recovered is not None else "N/A",
)
metric_cols[1].metric(
    "Overall reproducibility -- recovered + not recovered",
    f"{overall_completed:.4f}" if overall_completed is not None else "N/A",
)
metric_cols[2].metric(
    "Overall % unrecovered (mean across mechanisms)",
    f"{overall_pct_unrecovered:.1f}%" if overall_pct_unrecovered is not None else "N/A",
)
st.dataframe(summary_df, width="stretch", hide_index=True)

if chart_labels:
    fig_recovered = build_single_series_bar_chart(
        labels=chart_labels, values=chart_values_recovered,
        title="Reproducibility -- Recovered Elements Only, by Mechanism",
        xlabel="Mechanism", ylabel="V-measure", value_format="{:.2f}",
    )
    st.pyplot(fig_recovered)
    fig_completed = build_single_series_bar_chart(
        labels=chart_labels, values=chart_values_completed,
        title="Reproducibility -- Recovered + Not Recovered, by Mechanism",
        xlabel="Mechanism", ylabel="V-measure", value_format="{:.2f}",
    )
    st.pyplot(fig_completed)

st.subheader("3. Element occurrence across runs")
st.caption(
    "Did each tracked element show up at all in each run (grouped or in \"Ungrouped\") -- "
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
if chart_labels:
    import io
    chart_dl_cols = st.columns(2)
    for col, fig, label, name in (
        (chart_dl_cols[0], fig_recovered, "Recovered only", "reproducibility_chart_recovered_only.png"),
        (chart_dl_cols[1], fig_completed, "Recovered + not recovered", "reproducibility_chart_recovered_plus_not_recovered.png"),
    ):
        png_buf = io.BytesIO()
        fig.savefig(png_buf, format="png", dpi=300, bbox_inches="tight", facecolor="white")
        col.download_button(
            f"⬇ Chart PNG (300 dpi) -- {label}", data=png_buf.getvalue(),
            file_name=name, mime="image/png", width="stretch",
        )
