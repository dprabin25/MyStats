"""
MyStats tool: Reproducibility (V-measure)

Pure pairwise comparison -- no group naming or matching across runs.
V-measure only cares which elements land in a group together, not what
you call the group, so "Group 1" in Run 1 and "Group 1" in Run 2 don't
need to mean the same thing: if the same elements end up together, it
counts, wherever it lands.

For each run, enter:
- Groups: whatever elements this run put together, one group per row.
  Any number of groups, unnamed -- just entry order ("Group 1",
  "Group 2", ...).
- Unpaired: anything this run found completely alone, not with
  anything else.
- Unrecovered: NOT entered -- automatic. An element counts as
  unrecovered for a run if it showed up in a group or Unpaired in AT
  LEAST ONE OTHER run, but not in this one.

The scoring universe is derived entirely from what's actually entered
into Groups/Unpaired across the runs -- the union of every element any
run mentions. "Known elements" (section 1) is just an optional
autocomplete convenience for the pick-lists below; it does not affect
the score. This matters: an earlier version scored against a big
separately-maintained tracked-element list, which silently diluted the
result -- when most of that list was never mentioned by ANY run, all
those untouched elements trivially "agreed" across runs (every run
ignores them alike), and that trivial agreement swamped the real
disagreement among the handful of elements actually being compared,
pushing the score misleadingly close to 1.0 regardless of how much the
real groupings actually differed. Deriving the universe from what was
actually used removes that distortion.

Two V-measure numbers per pair of runs (a symmetric agreement score --
no run has to be "ground truth") -- only one of them is actually a
reproducibility claim:
- Grouping agreement (shared elements only): of the elements BOTH runs
  happened to mention, were they grouped the same way. This says
  NOTHING about whether the runs recovered the same elements in the
  first place -- two runs that agree on only 2 elements out of 20 used
  can still score a perfect 1.0 here, because it only ever looks at
  the overlap. Not labeled "Reproducibility" for exactly that reason;
  treat it as a secondary diagnostic, and check how many elements it's
  actually based on (shown alongside it) before trusting a high score.
- Reproducibility (recovered + unrecovered): the real headline number.
  Every element used by ANY run counts, and a run that never mentions
  one another run used is penalized for it -- this is what actually
  answers "how reproducible were these runs."
"""

import pandas as pd
import streamlit as st

from branding import inject_style, render_header
from chart_build import build_single_series_bar_chart
from reproducibility_core import parse_element_list, build_labels, mechanism_reproducibility, build_occurrence_table

inject_style()
render_header("Reproducibility (V-measure)")

st.caption(
    "Enter each run's groups below and it's scored as one pairwise comparison across runs, "
    "with no group naming or matching needed. \"Known elements\" is just an optional pick-list "
    "for the dropdowns -- it doesn't affect the score (see the note above for why)."
)

# ---------------- session state ----------------
# Same stable-id pattern as the other MyStats tools: widget keys are built
# from permanent ids (run id + group/unpaired id), not list position, so
# removing a row never leaves another row showing stale cached values.
if "rep_tracked_text" not in st.session_state:
    st.session_state.rep_tracked_text = ""
if "rep_next_run_id" not in st.session_state:
    st.session_state.rep_next_run_id = 0


def _blank_run(rid):
    return {"id": rid, "name": "", "groups": [{"id": 0, "elements": []}],
            "unpaired": [], "next_group_id": 1, "next_unpaired_id": 0}


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
    run["groups"].append({"id": gid, "elements": []})


def remove_group(run, gid):
    run["groups"] = [g for g in run["groups"] if g["id"] != gid]


def add_unpaired(run):
    uid = run["next_unpaired_id"]
    run["next_unpaired_id"] += 1
    run["unpaired"].append({"id": uid, "element": None})


def remove_unpaired(run, uid):
    run["unpaired"] = [u for u in run["unpaired"] if u["id"] != uid]


def reset_all():
    st.session_state.rep_tracked_text = ""
    st.session_state.rep_runs = _blank_runs(3)
    st.session_state.rep_generated = False


st.subheader("1. Known elements (optional)")
st.session_state.rep_tracked_text = st.text_area(
    "Known elements", value=st.session_state.rep_tracked_text, height=100,
    key="rep_tracked", label_visibility="collapsed",
    placeholder="One per line, or comma/semicolon-separated -- e.g. IL-1B, IL-17, GDF-15",
    help="Just a pick-list for the dropdowns below, so you don't have to retype names you use "
         "often -- typing a brand-new element directly into a Group/Unpaired box works too, "
         "without adding it here first. This list has NO effect on the score -- the score's "
         "universe is whatever elements actually get used in Groups/Unpaired across the runs "
         "below, nothing more.",
)
tracked = parse_element_list(st.session_state.rep_tracked_text)

st.subheader("2. Runs")
top_cols = st.columns([1, 1, 5])
top_cols[0].button("➕ Add run", on_click=add_run, width="stretch", key="rep_add_run_top")
top_cols[1].button("↺ Reset all", on_click=reset_all, width="stretch", key="rep_reset")

_preview_slots = []  # (run, placeholder) -- filled in after the loop, once every
                     # run's current elements are known (see below: the "used
                     # universe" a run's Unrecovered list is measured against
                     # has to include every OTHER run's elements too, and those
                     # aren't all known yet partway through this loop).

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
            group_cols = st.columns([2, 7, 1])
            group_cols[0].markdown(f"**Group {gi + 1}**")
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

        for ui, u in enumerate(r["unpaired"]):
            uid = u["id"]
            unpaired_cols = st.columns([2, 7, 1])
            unpaired_cols[0].markdown(f"Unpaired {ui + 1}")
            unpaired_options = list(dict.fromkeys(tracked + ([u["element"]] if u["element"] else [])))
            u["element"] = unpaired_cols[1].selectbox(
                "Element", options=unpaired_options, index=None, key=f"rep_unpaired_elem_{rid}_{uid}",
                accept_new_options=True, placeholder="Pick one tracked element, or type a new one",
                label_visibility="collapsed",
            )
            unpaired_cols[2].button(
                "🗑", key=f"rep_unpaired_remove_{rid}_{uid}", on_click=remove_unpaired, args=(r, uid), width="stretch",
            )
        st.button("➕ Add unpaired", on_click=add_unpaired, args=(r,), key=f"rep_add_unpaired_{rid}")

        # Live, read-only preview -- computed, never entered. Filled in below,
        # once every run's elements are known (this run's own placeholder).
        _preview_slots.append((r, st.empty()))

st.button("➕ Add run", on_click=add_run, key="rep_add_run_bottom")

# The "used universe" for the live preview -- and for scoring further down --
# is the union of every element ANY run actually put in a group or Unpaired.
# An element only counts as "unrecovered" for a run if some OTHER run used it;
# an element no run ever mentions isn't part of the comparison at all.


def _mentioned(run):
    mentioned = set()
    for g in run["groups"]:
        mentioned.update(g["elements"])
    for u in run["unpaired"]:
        if u["element"]:
            mentioned.add(u["element"])
    return mentioned


_mentioned_per_run = [_mentioned(r) for r in st.session_state.rep_runs]
_used_universe = sorted(set().union(*_mentioned_per_run)) if _mentioned_per_run else []

for (r, slot), mentioned in zip(_preview_slots, _mentioned_per_run):
    unrecovered_here = [e for e in _used_universe if e not in mentioned]
    if unrecovered_here:
        slot.caption(f"Unrecovered here: {', '.join(unrecovered_here)}")

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
    [g["elements"] for g in r["groups"]] + [[u["element"]] for u in r["unpaired"] if u["element"]]
    for r in runs
]

if not any(any(g) for g in groups_per_run):
    st.info("Nothing to score yet -- add at least one group or Unpaired element to a run above.")
    st.stop()

# "Grouping agreement": no tracked-element completion -- an element only
# counts if a run actually mentioned it, and pairwise comparison then
# further restricts to elements BOTH runs in a given pair mentioned.
raw_labels = [build_labels(g, tracked_elements=None) for g in groups_per_run]
# "Reproducibility": every element ANY run used gets a label in every
# run -- a run that never mentions one gets it as its own singleton,
# which counts against the score. The universe here is derived from
# actual usage (_used_universe, from the live preview above), never
# from the "Known elements" pick-list -- that's what keeps an untouched
# pick-list from diluting the score (see module docstring).
completed_labels = (
    [build_labels(g, tracked_elements=_used_universe) for g in groups_per_run]
    if _used_universe else raw_labels
)

result_agreement = mechanism_reproducibility(run_names, raw_labels)
result_repro = mechanism_reproducibility(run_names, completed_labels)

occ_rows = build_occurrence_table(_used_universe, groups_per_run, run_names) if _used_universe else []
n_runs = len(run_names)
n_unrecovered = sum(1 for row in occ_rows if row["Runs occurring in"] < n_runs)
pct_unrecovered = round(100 * n_unrecovered / len(_used_universe), 1) if _used_universe else None

pairs_rows = []
pair_chart_labels, pair_chart_agreement, pair_chart_repro = [], [], []
for pair_agreement, pair_repro in zip(result_agreement["pairs"], result_repro["pairs"]):
    pairs_rows.append({
        "Run A": pair_repro["Run A"],
        "Run B": pair_repro["Run B"],
        "Grouping agreement (V-measure)": pair_agreement["V-measure"],
        "Elements compared (grouping agreement)": pair_agreement["n_common"],
        "Reproducibility (V-measure)": pair_repro["V-measure"],
        "Elements compared (reproducibility)": pair_repro["n_common"],
        "Common elements": pair_repro["Common elements"],
        "Common not recovered elements": pair_repro["Common not recovered elements"],
        "Mismatched elements": pair_repro["Ungrouped elements"],
    })
    pair_chart_labels.append(f"{pair_repro['Run A']} vs {pair_repro['Run B']}")
    pair_chart_agreement.append(pair_agreement["V-measure"] if pair_agreement["V-measure"] is not None else 0.0)
    pair_chart_repro.append(pair_repro["V-measure"] if pair_repro["V-measure"] is not None else 0.0)

pairs_df = pd.DataFrame(pairs_rows)
occurrence_df = pd.DataFrame(occ_rows)

st.subheader("3. Summary")
st.caption(
    "**Grouping agreement** looks purely at whether elements both runs mentioned got grouped "
    "the same way -- it says nothing about whether the runs recovered the same elements at all, "
    "so it isn't labeled \"Reproducibility.\" **Reproducibility** is the real headline number: it "
    "also counts it against the score when a run never mentions an element some OTHER run used."
)
avg_agreement = result_agreement["average_v_measure"]
avg_repro = result_repro["average_v_measure"]
metric_cols = st.columns(3)
metric_cols[0].metric(
    "Grouping agreement -- shared elements only",
    f"{avg_agreement:.4f}" if avg_agreement is not None else "N/A",
)
metric_cols[1].metric(
    "Reproducibility (V-measure)",
    f"{avg_repro:.4f}" if avg_repro is not None else "N/A",
)
metric_cols[2].metric(
    "% Unrecovered (not in every run)",
    f"{pct_unrecovered:.1f}%" if pct_unrecovered is not None else "N/A",
)

_agreement_ns = [p["n_common"] for p in result_agreement["pairs"] if p["V-measure"] is not None]
if _agreement_ns and _used_universe and min(_agreement_ns) < len(_used_universe):
    st.warning(
        f"**Grouping agreement** can look artificially high (or low) when it's based on very "
        f"few shared elements -- as few as {min(_agreement_ns)} here, out of {len(_used_universe)} "
        f"elements used anywhere. A perfect 1.0 from 2 elements both runs happened to group "
        f"together isn't the same claim as a 1.0 from 20 -- it is NOT a reproducibility score on "
        f"its own. Check \"Elements compared (grouping agreement)\" in the pairwise breakdown "
        f"(section 5), and rely on **Reproducibility** above for the real headline number."
    )

if pair_chart_labels:
    fig_agreement = build_single_series_bar_chart(
        labels=pair_chart_labels, values=pair_chart_agreement,
        title="Grouping Agreement -- Shared Elements Only, by Run Pair",
        xlabel="Run pair", ylabel="V-measure", value_format="{:.2f}",
    )
    st.pyplot(fig_agreement)
    fig_repro = build_single_series_bar_chart(
        labels=pair_chart_labels, values=pair_chart_repro,
        title="Reproducibility, by Run Pair",
        xlabel="Run pair", ylabel="V-measure", value_format="{:.2f}",
    )
    st.pyplot(fig_repro)

st.subheader("4. Element occurrence across runs")
st.caption(
    "Every element used by at least one run -- did it show up at all in each OTHER run "
    "(grouped or Unpaired), separate from whether it was grouped the same way. A count below "
    "the number of runs means that element wasn't recovered consistently."
)
if occurrence_df.empty:
    st.caption("Add elements to a run's Groups/Unpaired (section 2) to see this table.")
else:
    st.dataframe(occurrence_df, width="stretch", hide_index=True)

st.subheader("5. Pairwise breakdown")
st.dataframe(pairs_df, width="stretch", hide_index=True)

st.subheader("6. Downloads")
dl_cols = st.columns(3)
dl_cols[0].download_button(
    "⬇ CSV (reproducibility_pairwise.csv)", data=pairs_df.to_csv(index=False),
    file_name="reproducibility_pairwise.csv", mime="text/csv", width="stretch",
)
dl_cols[1].download_button(
    "⬇ CSV (reproducibility_occurrence.csv)", data=occurrence_df.to_csv(index=False),
    file_name="reproducibility_occurrence.csv", mime="text/csv", width="stretch",
    disabled=occurrence_df.empty,
)
if pair_chart_labels:
    import io
    png_buf = io.BytesIO()
    fig_agreement.savefig(png_buf, format="png", dpi=300, bbox_inches="tight", facecolor="white")
    dl_cols[2].download_button(
        "⬇ Chart PNG (300 dpi) -- grouping agreement", data=png_buf.getvalue(),
        file_name="reproducibility_chart_grouping_agreement.png", mime="image/png", width="stretch",
    )
    png_buf2 = io.BytesIO()
    fig_repro.savefig(png_buf2, format="png", dpi=300, bbox_inches="tight", facecolor="white")
    st.download_button(
        "⬇ Chart PNG (300 dpi) -- reproducibility", data=png_buf2.getvalue(),
        file_name="reproducibility_chart_reproducibility.png", mime="image/png", width="stretch",
    )
