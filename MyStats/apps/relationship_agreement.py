"""
MyStats tool: Relationship Agreement (Jaccard / Dice)

For narratives that report individual pairwise relationships --
"IL-1beta increases MMP-8", "Lactobacillus rhamnosus reduces IL-1beta"
-- rather than a clean partition of elements into mutually-exclusive
clusters. That distinction matters: the Reproducibility (V-measure)
tool assumes every run reduces to a partition, so it runs your Groups
through union-find, and a single hub element mentioned in several
separate, otherwise-unrelated relationships (a cytokine the literature
connects to five different things that aren't connected to EACH OTHER)
gets all of its partners silently merged into one supercluster -- even
though the narrative never claimed those partners belonged together.

This tool never builds a partition. Each run's relationships are kept
as a set of edges (unordered element pairs) and compared directly with
Jaccard and Dice similarity -- no transitive closure, so a hub element
repeated across many rows never drags unrelated partners together. A
relationship either shows up in both runs' sets or it doesn't; nothing
else about that run's OTHER relationships changes that.

Enter each run's relationships below as Element A / Element B rows (one
row per relationship the narrative reports -- the citation or exact
wording doesn't matter here, just which two elements are related).
Defaults are seeded from a real 3-narrative periodontitis example.
"""

import pandas as pd
import streamlit as st

from branding import inject_style, render_header
from chart_build import build_single_series_bar_chart
from reproducibility_core import parse_element_list
from relationship_core import (
    parse_relationship_rows, pairwise_relationship_agreement, build_relationship_table,
)

inject_style()
render_header("Relationship Agreement (Jaccard / Dice)")

st.caption(
    "Enter each run's relationships below (Element A / Element B -- one row per relationship "
    "the narrative reports). Scored as Jaccard and Dice similarity of the relationship SETS -- "
    "no clustering, no transitive merging, so a hub element mentioned in many separate "
    "relationships never drags its unrelated partners together the way the Reproducibility "
    "(V-measure) tool's Groups can. \"Known elements\" is just an optional pick-list for the "
    "dropdowns -- it has no effect on the score."
)

# ---------------- defaults (a real 3-narrative periodontitis example) ----------------
_DEFAULT_KNOWN_TEXT = (
    "IL-1β, MMP-8, Lactobacillus rhamnosus, EGF, PDGF, B-cell, GDF-15, "
    "Anaeroglobus geminatus, Dialister invisus, Brevundimonas diminuta, Eggerthia catenaformis"
)

_DEFAULT_RUN_EDGES = [
    [("IL-1β", "MMP-8"), ("Lactobacillus rhamnosus", "IL-1β"), ("EGF", "PDGF"), ("B-cell", "IL-1β")],
    [("B-cell", "IL-1β"), ("MMP-8", "IL-1β"), ("Lactobacillus rhamnosus", "IL-1β"), ("EGF", "PDGF")],
    [
        ("IL-1β", "MMP-8"), ("Lactobacillus rhamnosus", "IL-1β"), ("PDGF", "IL-1β"),
        ("B-cell", "IL-1β"), ("Anaeroglobus geminatus", "Dialister invisus"), ("EGF", "IL-1β"),
    ],
]

# ---------------- session state ----------------
# Same stable-id pattern as the Reproducibility/Inter-rater tools: widget
# keys are built from permanent ids (run id + row id), not list position,
# so removing a row never leaves another row showing stale cached values.
if "ra_tracked_text" not in st.session_state:
    st.session_state.ra_tracked_text = _DEFAULT_KNOWN_TEXT
if "ra_next_run_id" not in st.session_state:
    st.session_state.ra_next_run_id = 0


def _run_from_edges(rid, edges):
    rows = [{"id": i, "element_a": a, "element_b": b} for i, (a, b) in enumerate(edges)]
    return {"id": rid, "name": "", "rows": rows, "next_row_id": len(rows)}


def _default_runs():
    runs = [_run_from_edges(i, edges) for i, edges in enumerate(_DEFAULT_RUN_EDGES)]
    st.session_state.ra_next_run_id = len(runs)
    return runs


def _blank_run(rid):
    return {"id": rid, "name": "", "rows": [{"id": 0, "element_a": None, "element_b": None}],
            "next_row_id": 1}


if "ra_runs" not in st.session_state:
    st.session_state.ra_runs = _default_runs()
if "ra_generated" not in st.session_state:
    st.session_state.ra_generated = False


def add_run():
    rid = st.session_state.ra_next_run_id
    st.session_state.ra_next_run_id += 1
    st.session_state.ra_runs.append(_blank_run(rid))


def remove_run(rid):
    st.session_state.ra_runs = [r for r in st.session_state.ra_runs if r["id"] != rid]


def add_row(run):
    rowid = run["next_row_id"]
    run["next_row_id"] += 1
    run["rows"].append({"id": rowid, "element_a": None, "element_b": None})


def remove_row(run, rowid):
    run["rows"] = [row for row in run["rows"] if row["id"] != rowid]


def reset_all():
    # Every widget below is keyed (ra_tracked, ra_run_name_*, ra_elem_a_*,
    # ra_elem_b_*, ...), and a keyed widget treats its own
    # st.session_state entry as sole source of truth once it exists --
    # just reassigning the shadow dicts/text below would leave every
    # already-rendered widget showing its last edited value instead of
    # resetting. Wiping every "ra_"-prefixed key except the four this
    # function itself controls forces each widget to re-seed fresh from
    # the value/index its next render provides.
    keep = {"ra_tracked_text", "ra_next_run_id", "ra_runs", "ra_generated"}
    for k in list(st.session_state.keys()):
        if k.startswith("ra_") and k not in keep:
            del st.session_state[k]
    st.session_state.ra_tracked_text = _DEFAULT_KNOWN_TEXT
    st.session_state.ra_runs = _default_runs()
    st.session_state.ra_generated = False


st.subheader("1. Known elements (optional)")
st.session_state.ra_tracked_text = st.text_area(
    "Known elements", value=st.session_state.ra_tracked_text, height=80,
    key="ra_tracked", label_visibility="collapsed",
    placeholder="One per line, or comma/semicolon-separated -- e.g. IL-1β, MMP-8, GDF-15",
    help="Just a pick-list for the dropdowns below, so you don't have to retype names you use "
         "often -- typing a brand-new element directly into a row works too. This list has NO "
         "effect on the score.",
)
tracked = parse_element_list(st.session_state.ra_tracked_text)

st.subheader("2. Runs")
top_cols = st.columns([1, 1, 5])
top_cols[0].button("➕ Add run", on_click=add_run, width="stretch", key="ra_add_run_top")
top_cols[1].button("↺ Reset all", on_click=reset_all, width="stretch", key="ra_reset")

for run in st.session_state.ra_runs:
    rid = run["id"]
    with st.container(border=True):
        run_cols = st.columns([3, 1])
        run["name"] = run_cols[0].text_input(
            "Run name", value=run["name"], key=f"ra_run_name_{rid}", placeholder=f"Run {rid + 1}",
        )
        run_cols[1].button(
            "🗑 Remove run", key=f"ra_run_remove_{rid}", on_click=remove_run, args=(rid,),
            width="stretch",
        )

        if run["rows"]:
            head_cols = st.columns([4, 4, 1])
            head_cols[0].caption("Element A")
            head_cols[1].caption("Element B")

        for row in run["rows"]:
            rowid = row["id"]
            row_cols = st.columns([4, 4, 1])
            a_key, b_key = f"ra_elem_a_{rid}_{rowid}", f"ra_elem_b_{rid}_{rowid}"
            # A selectbox with an explicit key treats st.session_state[key]
            # as sole source of truth from its very first render -- passing
            # a value via `index=` only works if that key doesn't already
            # exist AND index actually points at the value's position.
            # Since these rows can ship pre-seeded defaults (see
            # _DEFAULT_RUN_EDGES above), the key has to be pre-seeded here,
            # once, before the widget call -- the same fix as the F1-Score
            # tool's Reset-all bug from earlier in this app's history.
            if a_key not in st.session_state and row["element_a"]:
                st.session_state[a_key] = row["element_a"]
            if b_key not in st.session_state and row["element_b"]:
                st.session_state[b_key] = row["element_b"]
            a_options = list(dict.fromkeys(tracked + ([row["element_a"]] if row["element_a"] else [])))
            row["element_a"] = row_cols[0].selectbox(
                "Element A", options=a_options, index=None, key=a_key,
                accept_new_options=True, placeholder="Pick or type an element",
                label_visibility="collapsed",
            )
            b_options = list(dict.fromkeys(tracked + ([row["element_b"]] if row["element_b"] else [])))
            row["element_b"] = row_cols[1].selectbox(
                "Element B", options=b_options, index=None, key=b_key,
                accept_new_options=True, placeholder="Pick or type an element",
                label_visibility="collapsed",
            )
            row_cols[2].button(
                "🗑", key=f"ra_row_remove_{rid}_{rowid}", on_click=remove_row, args=(run, rowid),
                width="stretch",
            )
        st.button("➕ Add relationship", on_click=add_row, args=(run,), key=f"ra_add_row_{rid}")

st.button("➕ Add run", on_click=add_run, key="ra_add_run_bottom")

st.divider()
if st.button("🔄 Generate agreement scores", type="primary", width="stretch", key="ra_generate"):
    st.session_state.ra_generated = True

if not st.session_state.ra_generated:
    st.info("Click **Generate agreement scores** above once at least 2 runs have filled-in rows.")
    st.stop()

# ---------------- compute ----------------
runs = st.session_state.ra_runs
run_names = [r["name"].strip() or f"Run {j + 1}" for j, r in enumerate(runs)]

if len(runs) < 2:
    st.warning("Need at least 2 runs to compute agreement.")
    st.stop()

rows_per_run = [
    [(row["element_a"], row["element_b"]) for row in r["rows"] if row["element_a"] and row["element_b"]]
    for r in runs
]

if not any(rows_per_run):
    st.info("Nothing to score yet -- fill in at least one complete row (Element A + Element B) for a run above.")
    st.stop()

run_edge_sets = [parse_relationship_rows(rows) for rows in rows_per_run]
result = pairwise_relationship_agreement(run_names, run_edge_sets)
relationship_rows = build_relationship_table(run_names, run_edge_sets)
relationship_df = pd.DataFrame(relationship_rows)[["Element A", "Element B"] + run_names + ["Runs reporting"]]

pairs_df = pd.DataFrame(result["pairs"])

st.subheader("3. Agreement summary")
avg_jaccard = result["average_jaccard"]
n_pairs = result["n_valid_pairs"]
metric_cols = st.columns(3)
metric_cols[0].metric(
    "Jaccard" if n_pairs == 1 else "Average Jaccard",
    f"{avg_jaccard:.4f}" if avg_jaccard is not None else "N/A",
)
avg_dice = (sum(p["Dice"] for p in result["pairs"] if p["Dice"] is not None) / n_pairs) if n_pairs else None
metric_cols[1].metric(
    "Dice" if n_pairs == 1 else "Average Dice",
    f"{avg_dice:.4f}" if avg_dice is not None else "N/A",
)
metric_cols[2].metric("Distinct relationships (any run)", len(relationship_rows))
st.caption(
    "Jaccard = shared relationships / total distinct relationships either run reported. "
    "Dice = 2 x shared / (Run A's count + Run B's count) -- always >= Jaccard for the same "
    "two sets; a big gap between them means the two runs reported very different numbers of "
    "relationships overall, which either number alone would hide."
)

if len(pairs_df) > 1:
    chart_labels = [f"{row['Run A']} vs {row['Run B']}" for _, row in pairs_df.iterrows()]
    chart_values = [v if v is not None else 0.0 for v in pairs_df["Jaccard"].tolist()]
    fig = build_single_series_bar_chart(
        labels=chart_labels, values=chart_values,
        title="Relationship Agreement (Jaccard), by Run Pair",
        xlabel="Run pair", ylabel="Jaccard", value_format="{:.2f}",
    )
    st.pyplot(fig)

st.subheader("4. Relationship x Run agreement table")
st.caption(
    "One row per distinct relationship reported by ANY run (no duplicates) -- Yes/No per run, "
    "and how many runs reported it."
)
st.dataframe(relationship_df, width="stretch", hide_index=True)

st.subheader("5. Pairwise breakdown")
st.dataframe(pairs_df, width="stretch", hide_index=True)

st.subheader("6. Downloads")
dl_cols = st.columns(2)
dl_cols[0].download_button(
    "⬇ CSV (relationship_agreement_table.csv)", data=relationship_df.to_csv(index=False),
    file_name="relationship_agreement_table.csv", mime="text/csv", width="stretch",
)
dl_cols[1].download_button(
    "⬇ CSV (relationship_agreement_pairwise.csv)", data=pairs_df.to_csv(index=False),
    file_name="relationship_agreement_pairwise.csv", mime="text/csv", width="stretch",
)
if len(pairs_df) > 1:
    import io
    png_buf = io.BytesIO()
    fig.savefig(png_buf, format="png", dpi=300, bbox_inches="tight", facecolor="white")
    st.download_button(
        "⬇ Chart PNG (300 dpi)", data=png_buf.getvalue(),
        file_name="relationship_agreement_chart.png", mime="image/png", width="stretch",
    )
