"""
MyStats tool: Reproducibility (V-measure)

There is no separate "mechanism" container to fill in -- a mechanism
IS a named group. Add runs, and within each run add groups (rename a
group to identify which mechanism it is, e.g. "MMP-8/MIP-1D cascade";
leave it blank and it's matched across runs by position -- "Group 1" in
every run -- so keep the same order, or name them, if you want them
compared correctly). The app automatically finds every distinct group
name used anywhere, and for each one scores reproducibility using ONLY
that group's own elements across runs -- never the elements of a
different group, and never anything from an unrelated mechanism. That
was the bug in the old design: one shared "Elements to track" list
meant every mechanism's score was diluted by every OTHER mechanism's
untouched elements (usually showing up as a huge, meaningless "common
not recovered" count). Now each mechanism's universe is exactly the
elements someone actually put in it.

For each mechanism, the app reports two versions of V-measure, a
symmetric cluster-agreement score (no run has to be "ground truth"):
- "Recovered elements only": scores agreement using only elements each
  run actually placed somewhere (grouped or "Ungrouped") for THIS
  mechanism -- an element neither run mentions for this mechanism at
  all doesn't enter this one.
- "Recovered + not recovered": the stricter version -- every element in
  this mechanism's universe gets a label in every run, and a run that
  never mentions one gets it as its own singleton, which counts against
  the score.

A "Detected mechanisms" table shows exactly which runs contributed to
each mechanism's universe, so a naming/ordering mismatch between runs
is visible before trusting any score.
"""

import pandas as pd
import streamlit as st

from branding import inject_style, render_header
from chart_build import build_single_series_bar_chart
from reproducibility_core import parse_element_list, build_labels, mechanism_reproducibility, build_occurrence_table

inject_style()
render_header("Reproducibility (V-measure)")

# Default tracked-elements list -- pre-fills every group/ungrouped
# pick-list so it doesn't need retyping; purely a UI convenience (it
# doesn't restrict scoring -- each mechanism's universe is whatever was
# actually picked for it, see module docstring). Still fully editable,
# and typing something not on it works too (accept_new_options).
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
    "Add runs below. Within each run, add groups -- each distinct group name (or position, if "
    "left blank) is automatically treated as its own mechanism and scored separately, using only "
    "that mechanism's own elements. No shared tracked-element list to dilute the score."
)

# ---------------- session state ----------------
# Same stable-id pattern as the other MyStats tools: widget keys are
# built from permanent ids (run id + group id), not list position, so
# removing a row never leaves another row showing stale cached values.
if "rep_tracked_text" not in st.session_state:
    st.session_state.rep_tracked_text = DEFAULT_TRACKED_TEXT
if "rep_next_run_id" not in st.session_state:
    st.session_state.rep_next_run_id = 0


def _blank_run(rid):
    return {"id": rid, "name": "", "groups": [{"id": 0, "name": "", "elements": []}],
            "ungrouped": [], "next_group_id": 1, "next_ungrouped_id": 0}


def _blank_runs(n=3):
    runs = [_blank_run(i) for i in range(n)]
    st.session_state.rep_next_run_id = n
    return runs


if "rep_runs" not in st.session_state:
    st.session_state.rep_runs = _blank_runs(3)
if "rep_generated" not in st.session_state:
    st.session_state.rep_generated = False


def add_run():
    rid = st.session_state.rep_next_run_id
    st.session_state.rep_next_run_id += 1
    st.session_state.rep_runs.append(_blank_run(rid))


def remove_run(rid):
    st.session_state.rep_runs = [r for r in st.session_state.rep_runs if r["id"] != rid]


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
    st.session_state.rep_tracked_text = DEFAULT_TRACKED_TEXT
    st.session_state.rep_runs = _blank_runs(3)
    st.session_state.rep_generated = False


st.subheader("1. Elements to track")
st.session_state.rep_tracked_text = st.text_area(
    "Elements to track", value=st.session_state.rep_tracked_text, height=100,
    key="rep_tracked", label_visibility="collapsed",
    help="One per line, or comma/semicolon-separated. This is only the default pick-list for "
         "every group/ungrouped selector below -- it doesn't restrict scoring. Type something "
         "not on this list into any picker and it's added right in.",
)
tracked = parse_element_list(st.session_state.rep_tracked_text)

st.subheader("2. Runs")
top_cols = st.columns([1, 1, 5])
top_cols[0].button("➕ Add run", on_click=add_run, width="stretch", key="rep_add_run_top")
top_cols[1].button("↺ Reset all", on_click=reset_all, width="stretch", key="rep_reset")

for r in st.session_state.rep_runs:
    rid = r["id"]
    with st.container(border=True):
        run_cols = st.columns([3, 1])
        r["name"] = run_cols[0].text_input(
            "Run name", value=r["name"], key=f"rep_run_name_{rid}", placeholder=f"Run {rid + 1}",
        )
        run_cols[1].button(
            "🗑 Remove run", key=f"rep_run_remove_{rid}", on_click=remove_run, args=(rid,), width="stretch",
        )

        for gi, g in enumerate(r["groups"]):
            gid = g["id"]
            group_cols = st.columns([2, 6, 1])
            g["name"] = group_cols[0].text_input(
                "Group name", value=g["name"], key=f"rep_group_name_{rid}_{gid}",
                placeholder=f"Group {gi + 1}", label_visibility="collapsed",
                help="Matched across runs by this name -- leave every run's corresponding group "
                     "blank (same position) or give them the exact same name to compare them as "
                     "one mechanism.",
            )
            group_options = list(dict.fromkeys(tracked + g["elements"]))
            g["elements"] = group_cols[1].multiselect(
                "Elements", options=group_options, default=g["elements"],
                key=f"rep_group_elems_{rid}_{gid}", accept_new_options=True,
                placeholder="Pick tracked elements, or type a new one and press Enter",
                label_visibility="collapsed",
            )
            group_cols[2].button(
                "🗑", key=f"rep_group_remove_{rid}_{gid}", on_click=remove_group, args=(r, gid), width="stretch",
            )
        st.button("➕ Add group", on_click=add_group, args=(r,), key=f"rep_add_group_{rid}")

        for ui, u in enumerate(r["ungrouped"]):
            uid = u["id"]
            ungrouped_cols = st.columns([2, 6, 1])
            ungrouped_cols[0].markdown(f"Ungrouped {ui + 1}")
            ungrouped_options = list(dict.fromkeys(tracked + ([u["element"]] if u["element"] else [])))
            u["element"] = ungrouped_cols[1].selectbox(
                "Element", options=ungrouped_options, index=None, key=f"rep_ungrouped_elem_{rid}_{uid}",
                accept_new_options=True, placeholder="Pick one tracked element, or type a new one",
                label_visibility="collapsed",
            )
            ungrouped_cols[2].button(
                "🗑", key=f"rep_ungrouped_remove_{rid}_{uid}", on_click=remove_ungrouped, args=(r, uid), width="stretch",
            )
        st.button("➕ Add ungrouped", on_click=add_ungrouped, args=(r,), key=f"rep_add_ungrouped_{rid}")

st.button("➕ Add run", on_click=add_run, key="rep_add_run_bottom")

st.divider()
if st.button("🔄 Generate reproducibility scores", type="primary", width="stretch", key="rep_generate"):
    st.session_state.rep_generated = True

if not st.session_state.rep_generated:
    st.info("Click **Generate reproducibility scores** above once you've added groups to at least 2 runs.")
    st.stop()

# ---------------- compute ----------------
runs = st.session_state.rep_runs
run_names = [r["name"].strip() or f"Run {j + 1}" for j, r in enumerate(runs)]

if len(runs) < 2:
    st.warning("Need at least 2 runs to compute reproducibility.")
    st.stop()

groups_per_run = [
    [g["elements"] for g in r["groups"]] + [[u["element"]] for u in r["ungrouped"] if u["element"]]
    for r in runs
]
# Unrestricted labels per run -- each run's real group structure, no
# filtering, no completion. Restricting this to one mechanism's universe
# (by dropping keys outside it) gives the "recovered only" labels for
# that mechanism while preserving whether elements landed in the SAME
# real group or different ones.
raw_full_labels = [build_labels(g, tracked_elements=None) for g in groups_per_run]

# Discover mechanisms: every distinct group name (or, if blank, its
# position) used in ANY run's groups. Track which runs contributed to
# each one's universe, for the diagnostic table below.
mechanism_keys = []
key_elements = {}
key_runs_present = {}
for run_idx, r in enumerate(runs):
    for gi, g in enumerate(r["groups"]):
        key = g["name"].strip() or f"Group {gi + 1}"
        if key not in key_elements:
            mechanism_keys.append(key)
            key_elements[key] = set()
            key_runs_present[key] = set()
        key_elements[key].update(g["elements"])
        if g["elements"]:
            key_runs_present[key].add(run_names[run_idx])

if not mechanism_keys:
    st.info("Nothing to score yet -- add at least one group with elements to a run above.")
    st.stop()

detected_rows = [
    {
        "Mechanism": key,
        "Present in runs": ", ".join(sorted(key_runs_present[key])) or "(none -- empty group)",
        "Universe size": len(key_elements[key]),
    }
    for key in mechanism_keys
]

mech_summary_rows = []
all_pair_rows = []
all_occurrence_rows = []
chart_labels = []
chart_values_recovered, chart_values_completed = [], []

for key in mechanism_keys:
    universe = sorted(key_elements[key])
    if not universe:
        continue

    raw_restricted = [{e: lab for e, lab in labels.items() if e in key_elements[key]} for labels in raw_full_labels]
    completed_labels = [build_labels(g, tracked_elements=universe) for g in groups_per_run]

    result_recovered = mechanism_reproducibility(run_names, raw_restricted)
    result_completed = mechanism_reproducibility(run_names, completed_labels)

    occ_rows = build_occurrence_table(universe, groups_per_run, run_names)
    n_runs = len(run_names)
    n_unrecovered = sum(1 for row in occ_rows if row["Runs occurring in"] < n_runs)
    pct_unrecovered = round(100 * n_unrecovered / len(universe), 1) if universe else None

    avg_recovered = result_recovered["average_v_measure"]
    avg_completed = result_completed["average_v_measure"]
    mech_summary_rows.append({
        "Mechanism": key,
        "Average V-measure (recovered only)": round(avg_recovered, 4) if avg_recovered is not None else None,
        "Average V-measure (recovered + not recovered)": round(avg_completed, 4) if avg_completed is not None else None,
        "% Unrecovered (not in every run)": pct_unrecovered,
        "Valid pairs": result_completed["n_valid_pairs"],
        "Runs": n_runs,
        "Universe size": len(universe),
    })
    for pair_recovered, pair_completed in zip(result_recovered["pairs"], result_completed["pairs"]):
        all_pair_rows.append({
            "Mechanism": key,
            "Run A": pair_completed["Run A"],
            "Run B": pair_completed["Run B"],
            "V-measure (recovered only)": pair_recovered["V-measure"],
            "V-measure (recovered + not recovered)": pair_completed["V-measure"],
            "Common elements": pair_completed["Common elements"],
            "Common not recovered elements": pair_completed["Common not recovered elements"],
            "Ungrouped elements": pair_completed["Ungrouped elements"],
        })
    for occ_row in occ_rows:
        all_occurrence_rows.append({"Mechanism": key, **occ_row})
    if avg_recovered is not None or avg_completed is not None:
        chart_labels.append(key)
        chart_values_recovered.append(avg_recovered if avg_recovered is not None else 0.0)
        chart_values_completed.append(avg_completed if avg_completed is not None else 0.0)

if not mech_summary_rows:
    st.info("Nothing to score yet -- every detected group is empty.")
    st.stop()

summary_df = pd.DataFrame(mech_summary_rows)
pairs_df = pd.DataFrame(all_pair_rows)
occurrence_df = pd.DataFrame(all_occurrence_rows)
detected_df = pd.DataFrame(detected_rows)

st.subheader("3. Detected mechanisms")
st.caption(
    "One row per distinct group name/position found across your runs. Check \"Present in runs\" "
    "matches what you expect -- a mechanism missing a run you know defined it usually means that "
    "run's group has a different name, or is in a different position, than the others."
)
st.dataframe(detected_df, width="stretch", hide_index=True)

st.subheader("4. Reproducibility summary")
st.caption(
    "Two versions of the same score, per mechanism: **recovered only** looks purely at whether "
    "elements both runs mentioned for this mechanism got grouped the same way; **recovered + not "
    "recovered** also counts it against the score when a run never mentions one of this "
    "mechanism's elements at all."
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

st.subheader("5. Element occurrence across runs")
st.caption(
    "Per mechanism: did each of its elements show up at all in each run (grouped or in "
    "\"Ungrouped\") -- separate from whether it was grouped the same way. A count below the "
    "number of runs means that element wasn't recovered consistently."
)
st.dataframe(occurrence_df, width="stretch", hide_index=True)

st.subheader("6. Pairwise breakdown")
st.dataframe(pairs_df, width="stretch", hide_index=True)

st.subheader("7. Downloads")
dl_cols = st.columns(4)
dl_cols[0].download_button(
    "⬇ CSV (reproducibility_detected_mechanisms.csv)", data=detected_df.to_csv(index=False),
    file_name="reproducibility_detected_mechanisms.csv", mime="text/csv", width="stretch",
)
dl_cols[1].download_button(
    "⬇ CSV (reproducibility_summary.csv)", data=summary_df.to_csv(index=False),
    file_name="reproducibility_summary.csv", mime="text/csv", width="stretch",
)
dl_cols[2].download_button(
    "⬇ CSV (reproducibility_occurrence.csv)", data=occurrence_df.to_csv(index=False),
    file_name="reproducibility_occurrence.csv", mime="text/csv", width="stretch",
)
dl_cols[3].download_button(
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
