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
- Unrecovered: NOT entered -- automatic. Anything in "Elements to
  track" that this run never put in a group or Unpaired is
  unrecovered for that run; nothing to fill in for it.

Two versions of V-measure per pair of runs (a symmetric agreement
score -- no run has to be "ground truth"):
- Recovered only: scores agreement using only elements BOTH runs
  mentioned somewhere.
- Recovered + unrecovered (stricter): every tracked element counts,
  and a run that never mentions one is penalized for it.

Keep "Elements to track" scoped to whatever you're comparing right now
(e.g. one real mechanism's elements) rather than a big master list --
the score is computed over that whole list, so anything irrelevant
left in it just shows up as noisy "unrecovered" clutter.
"""

import pandas as pd
import streamlit as st

from branding import inject_style, render_header
from chart_build import build_single_series_bar_chart
from reproducibility_core import parse_element_list, build_labels, mechanism_reproducibility, build_occurrence_table

inject_style()
render_header("Reproducibility (V-measure)")

st.caption(
    "List only the elements relevant to what you're comparing right now -- this is scored as "
    "one pairwise comparison across runs, with no group naming or matching needed."
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


st.subheader("1. Elements to track")
st.session_state.rep_tracked_text = st.text_area(
    "Elements to track", value=st.session_state.rep_tracked_text, height=100,
    key="rep_tracked", label_visibility="collapsed",
    placeholder="One per line, or comma/semicolon-separated -- e.g. IL-1B, IL-17, GDF-15",
    help="The full universe for this comparison. Anything a run doesn't put in a group or "
         "Unpaired is automatically \"Unrecovered\" for that run -- nothing to enter for that.",
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

        # Live, read-only preview -- computed, never entered.
        if tracked:
            mentioned = set()
            for g in r["groups"]:
                mentioned.update(g["elements"])
            for u in r["unpaired"]:
                if u["element"]:
                    mentioned.add(u["element"])
            unrecovered_here = [e for e in tracked if e not in mentioned]
            if unrecovered_here:
                st.caption(f"Unrecovered here: {', '.join(unrecovered_here)}")

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
    [g["elements"] for g in r["groups"]] + [[u["element"]] for u in r["unpaired"] if u["element"]]
    for r in runs
]

if not any(any(g) for g in groups_per_run):
    st.info("Nothing to score yet -- add at least one group or Unpaired element to a run above.")
    st.stop()

# "Recovered only": no tracked-element completion -- an element only
# counts if a run actually mentioned it, and pairwise comparison then
# further restricts to elements BOTH runs in a given pair mentioned.
raw_labels = [build_labels(g, tracked_elements=None) for g in groups_per_run]
# "Recovered + unrecovered": every tracked element gets a label in every
# run -- a run that never mentions one gets it as its own singleton,
# which counts against the score.
completed_labels = [build_labels(g, tracked_elements=tracked) for g in groups_per_run] if tracked else raw_labels

result_recovered = mechanism_reproducibility(run_names, raw_labels)
result_completed = mechanism_reproducibility(run_names, completed_labels)

occ_rows = build_occurrence_table(tracked, groups_per_run, run_names) if tracked else []
n_runs = len(run_names)
n_unrecovered = sum(1 for row in occ_rows if row["Runs occurring in"] < n_runs)
pct_unrecovered = round(100 * n_unrecovered / len(tracked), 1) if tracked else None

pairs_rows = []
pair_chart_labels, pair_chart_recovered, pair_chart_completed = [], [], []
for pair_recovered, pair_completed in zip(result_recovered["pairs"], result_completed["pairs"]):
    pairs_rows.append({
        "Run A": pair_completed["Run A"],
        "Run B": pair_completed["Run B"],
        "V-measure (recovered only)": pair_recovered["V-measure"],
        "V-measure (recovered + unrecovered)": pair_completed["V-measure"],
        "Common elements": pair_completed["Common elements"],
        "Common not recovered elements": pair_completed["Common not recovered elements"],
        "Mismatched elements": pair_completed["Ungrouped elements"],
    })
    pair_chart_labels.append(f"{pair_completed['Run A']} vs {pair_completed['Run B']}")
    pair_chart_recovered.append(pair_recovered["V-measure"] if pair_recovered["V-measure"] is not None else 0.0)
    pair_chart_completed.append(pair_completed["V-measure"] if pair_completed["V-measure"] is not None else 0.0)

pairs_df = pd.DataFrame(pairs_rows)
occurrence_df = pd.DataFrame(occ_rows)

st.subheader("3. Reproducibility summary")
st.caption(
    "**Recovered only** looks purely at whether elements both runs mentioned got grouped the "
    "same way; **recovered + unrecovered** also counts it against the score when a run never "
    "mentions one of the tracked elements at all."
)
avg_recovered = result_recovered["average_v_measure"]
avg_completed = result_completed["average_v_measure"]
metric_cols = st.columns(3)
metric_cols[0].metric(
    "Reproducibility -- recovered only",
    f"{avg_recovered:.4f}" if avg_recovered is not None else "N/A",
)
metric_cols[1].metric(
    "Reproducibility -- recovered + unrecovered",
    f"{avg_completed:.4f}" if avg_completed is not None else "N/A",
)
metric_cols[2].metric(
    "% Unrecovered (not in every run)",
    f"{pct_unrecovered:.1f}%" if pct_unrecovered is not None else "N/A",
)

if pair_chart_labels:
    fig_recovered = build_single_series_bar_chart(
        labels=pair_chart_labels, values=pair_chart_recovered,
        title="Reproducibility -- Recovered Elements Only, by Run Pair",
        xlabel="Run pair", ylabel="V-measure", value_format="{:.2f}",
    )
    st.pyplot(fig_recovered)
    fig_completed = build_single_series_bar_chart(
        labels=pair_chart_labels, values=pair_chart_completed,
        title="Reproducibility -- Recovered + Unrecovered, by Run Pair",
        xlabel="Run pair", ylabel="V-measure", value_format="{:.2f}",
    )
    st.pyplot(fig_completed)

st.subheader("4. Element occurrence across runs")
st.caption(
    "Did each tracked element show up at all in each run (grouped or Unpaired) -- separate from "
    "whether it was grouped the same way. A count below the number of runs means that element "
    "wasn't recovered consistently."
)
if occurrence_df.empty:
    st.caption("Add elements to \"Elements to track\" (section 1) to see this table.")
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
    fig_recovered.savefig(png_buf, format="png", dpi=300, bbox_inches="tight", facecolor="white")
    dl_cols[2].download_button(
        "⬇ Chart PNG (300 dpi) -- recovered only", data=png_buf.getvalue(),
        file_name="reproducibility_chart_recovered_only.png", mime="image/png", width="stretch",
    )
    png_buf2 = io.BytesIO()
    fig_completed.savefig(png_buf2, format="png", dpi=300, bbox_inches="tight", facecolor="white")
    st.download_button(
        "⬇ Chart PNG (300 dpi) -- recovered + unrecovered", data=png_buf2.getvalue(),
        file_name="reproducibility_chart_recovered_plus_unrecovered.png", mime="image/png", width="stretch",
    )
