"""
MyStats tool: Inter-rater Agreement (Cohen's Kappa)

Each rater (expert) lists the pairs they see -- one row per
relationship, Element A next to whatever it goes with (Element B), or
"No pair" if it doesn't belong with anything. Chains merge
transitively: if a rater writes IL-1/IL-6 and B-cell/IL-1, that rater
is treated as grouping all three together, exactly like the
Reproducibility tool's Groups -- this is just a different, row-at-a-
time way of entering the same kind of judgment.

Cohen's Kappa needs a fixed set of items every rater classifies into
the same categories. Here, the item is EVERY unique pair of elements
across everything any rater mentioned, and the category is binary: did
this rater group these two together, or not. Unlike a raw agreement
percentage, Kappa corrects for chance -- two raters who both correctly
say "these two random elements aren't paired" don't get rewarded for
that the way raw agreement would reward them, which matters a lot here
since most element pairs in any real list are NOT paired.

With more than 2 raters, Kappa is computed pairwise between every pair
of raters (Kappa itself is inherently a two-rater statistic), and
averaged (a simple mean across pairs).
"""

import pandas as pd
import streamlit as st

from branding import inject_style, render_header
from chart_build import build_single_series_bar_chart
from reproducibility_core import parse_element_list
from interrater_core import (
    build_labels_from_rows, elements_used, pairwise_kappa_for_raters,
    build_group_table, kappa_interpretation,
)

NO_PAIR = "No pair"

inject_style()
render_header("Inter-rater Agreement (Cohen's Kappa)")

st.caption(
    "Enter each rater's pairs below (Element A / Element B, or \"No pair\"). Scored as Cohen's "
    "Kappa on \"same group or not\" across every pair of elements anyone mentioned -- chance-"
    "corrected, so trivially agreeing two elements AREN'T paired doesn't inflate the score. "
    "\"Known elements\" is just an optional pick-list for the dropdowns -- it has no effect on "
    "the score."
)

# ---------------- session state ----------------
# Same stable-id pattern as the Reproducibility tool: widget keys are built
# from permanent ids (rater id + row id), not list position, so removing a
# row never leaves another row showing stale cached values.
if "ir_tracked_text" not in st.session_state:
    st.session_state.ir_tracked_text = ""
if "ir_next_rater_id" not in st.session_state:
    st.session_state.ir_next_rater_id = 0


def _blank_rater(rid):
    return {"id": rid, "name": "", "rows": [{"id": 0, "element_a": None, "element_b": None}],
            "next_row_id": 1}


def _blank_raters(n=2):
    raters = [_blank_rater(i) for i in range(n)]
    st.session_state.ir_next_rater_id = n
    return raters


if "ir_raters" not in st.session_state:
    st.session_state.ir_raters = _blank_raters(2)
if "ir_generated" not in st.session_state:
    st.session_state.ir_generated = False


def add_rater():
    rid = st.session_state.ir_next_rater_id
    st.session_state.ir_next_rater_id += 1
    st.session_state.ir_raters.append(_blank_rater(rid))


def remove_rater(rid):
    st.session_state.ir_raters = [r for r in st.session_state.ir_raters if r["id"] != rid]


def add_row(rater):
    rowid = rater["next_row_id"]
    rater["next_row_id"] += 1
    rater["rows"].append({"id": rowid, "element_a": None, "element_b": None})


def remove_row(rater, rowid):
    rater["rows"] = [row for row in rater["rows"] if row["id"] != rowid]


def reset_all():
    st.session_state.ir_tracked_text = ""
    st.session_state.ir_raters = _blank_raters(2)
    st.session_state.ir_generated = False


st.subheader("1. Known elements (optional)")
st.session_state.ir_tracked_text = st.text_area(
    "Known elements", value=st.session_state.ir_tracked_text, height=100,
    key="ir_tracked", label_visibility="collapsed",
    placeholder="One per line, or comma/semicolon-separated -- e.g. IL-1, IL-6, GDF-15",
    help="Just a pick-list for the dropdowns below, so you don't have to retype names you use "
         "often -- typing a brand-new element directly into a row works too. This list has NO "
         "effect on the score.",
)
tracked = parse_element_list(st.session_state.ir_tracked_text)

st.subheader("2. Raters")
top_cols = st.columns([1, 1, 5])
top_cols[0].button("➕ Add rater", on_click=add_rater, width="stretch", key="ir_add_rater_top")
top_cols[1].button("↺ Reset all", on_click=reset_all, width="stretch", key="ir_reset")

for rater in st.session_state.ir_raters:
    rid = rater["id"]
    with st.container(border=True):
        rater_cols = st.columns([3, 1])
        rater["name"] = rater_cols[0].text_input(
            "Rater name", value=rater["name"], key=f"ir_rater_name_{rid}",
            placeholder=f"Expert {rid + 1}",
        )
        rater_cols[1].button(
            "🗑 Remove rater", key=f"ir_rater_remove_{rid}", on_click=remove_rater, args=(rid,),
            width="stretch",
        )

        if rater["rows"]:
            head_cols = st.columns([4, 4, 1])
            head_cols[0].caption("Element A")
            head_cols[1].caption("Element B")

        for row in rater["rows"]:
            rowid = row["id"]
            row_cols = st.columns([4, 4, 1])
            a_options = list(dict.fromkeys(tracked + ([row["element_a"]] if row["element_a"] else [])))
            row["element_a"] = row_cols[0].selectbox(
                "Element A", options=a_options, index=None, key=f"ir_elem_a_{rid}_{rowid}",
                accept_new_options=True, placeholder="Pick or type an element",
                label_visibility="collapsed",
            )
            b_options = [NO_PAIR] + list(dict.fromkeys(tracked + ([row["element_b"]] if row["element_b"] else [])))
            row["element_b"] = row_cols[1].selectbox(
                "Element B", options=b_options, index=None, key=f"ir_elem_b_{rid}_{rowid}",
                accept_new_options=True, placeholder="Pick an element, type one, or \"No pair\"",
                label_visibility="collapsed",
            )
            row_cols[2].button(
                "🗑", key=f"ir_row_remove_{rid}_{rowid}", on_click=remove_row, args=(rater, rowid),
                width="stretch",
            )
        st.button("➕ Add row", on_click=add_row, args=(rater,), key=f"ir_add_row_{rid}")

st.button("➕ Add rater", on_click=add_rater, key="ir_add_rater_bottom")

st.divider()
if st.button("🔄 Generate agreement scores", type="primary", width="stretch", key="ir_generate"):
    st.session_state.ir_generated = True

if not st.session_state.ir_generated:
    st.info("Click **Generate agreement scores** above once at least 2 raters have filled-in rows.")
    st.stop()

# ---------------- compute ----------------
raters = st.session_state.ir_raters
rater_names = [r["name"].strip() or f"Rater {j + 1}" for j, r in enumerate(raters)]

if len(raters) < 2:
    st.warning("Need at least 2 raters to compute agreement.")
    st.stop()

rows_per_rater = [
    [(row["element_a"], row["element_b"]) for row in r["rows"] if row["element_a"] and row["element_b"]]
    for r in raters
]

if not any(rows_per_rater):
    st.info("Nothing to score yet -- fill in at least one complete row (Element A + Element B) for a rater above.")
    st.stop()

universe = sorted(set().union(*(elements_used(rows) for rows in rows_per_rater)))
if len(universe) < 2:
    st.warning("Need at least 2 distinct elements across all raters to compute pairwise agreement.")
    st.stop()

labels_by_rater = [build_labels_from_rows(rows, universe) for rows in rows_per_rater]
result = pairwise_kappa_for_raters(labels_by_rater, universe)

pairs_df = pd.DataFrame([
    {
        "Rater A": rater_names[p["Rater A"]],
        "Rater B": rater_names[p["Rater B"]],
        "Kappa": p["Kappa"],
        "Interpretation": p["Interpretation"],
        "Observed agreement": p["Observed agreement"],
        "Expected agreement (chance)": p["Expected agreement (chance)"],
        "Both: paired": p["Both: paired"],
        "Both: not paired": p["Both: not paired"],
        "Only Rater A: paired": p["Only Rater A: paired"],
        "Only Rater B: paired": p["Only Rater B: paired"],
        "Element pairs compared": p["Element pairs compared"],
    }
    for p in result["pairs"]
])

group_tables = [build_group_table(labels, universe) for labels in labels_by_rater]
combined_groups_df = pd.DataFrame({"Element": universe})
for name, table in zip(rater_names, group_tables):
    lookup = {row["Element"]: row["Group"] for row in table}
    combined_groups_df[name] = [lookup[e] for e in universe]

st.subheader("3. Agreement summary")
avg_kappa = result["average_kappa"]
n_pairs = len(result["pairs"])
metric_cols = st.columns(3 if n_pairs == 1 else 2)
metric_cols[0].metric(
    "Cohen's Kappa" if n_pairs == 1 else "Average Cohen's Kappa",
    f"{avg_kappa:.4f}" if avg_kappa is not None else "N/A",
)
metric_cols[1].metric("Interpretation", kappa_interpretation(avg_kappa))
if n_pairs == 1:
    only_pair = result["pairs"][0]
    metric_cols[2].metric("Observed vs. chance agreement",
                           f"{only_pair['Observed agreement']:.1%} vs {only_pair['Expected agreement (chance)']:.1%}")
st.caption(
    "Kappa = (observed agreement − chance agreement) / (1 − chance agreement). Standard "
    "Landis & Koch (1977) bands: ≤0 poor, .01–.20 slight, .21–.40 fair, .41–.60 moderate, "
    ".61–.80 substantial, .81–1.00 almost perfect."
)

if n_pairs > 1:
    chart_labels = [f"{row['Rater A']} vs {row['Rater B']}" for _, row in pairs_df.iterrows()]
    fig = build_single_series_bar_chart(
        labels=chart_labels, values=pairs_df["Kappa"].tolist(),
        title="Cohen's Kappa, by Rater Pair", xlabel="Rater pair", ylabel="Kappa",
        value_format="{:.2f}",
    )
    st.pyplot(fig)

st.subheader("4. Detected groups by rater")
st.caption(
    "How each rater's rows resolved into groups (via chains -- A/B and B/C means A, B, C are "
    "all one group) -- check this matches what you meant before trusting the kappa above."
)
st.dataframe(combined_groups_df, width="stretch", hide_index=True)

st.subheader("5. Pairwise breakdown")
st.dataframe(pairs_df, width="stretch", hide_index=True)

st.subheader("6. Downloads")
dl_cols = st.columns(2)
dl_cols[0].download_button(
    "⬇ CSV (interrater_kappa_pairwise.csv)", data=pairs_df.to_csv(index=False),
    file_name="interrater_kappa_pairwise.csv", mime="text/csv", width="stretch",
)
dl_cols[1].download_button(
    "⬇ CSV (interrater_detected_groups.csv)", data=combined_groups_df.to_csv(index=False),
    file_name="interrater_detected_groups.csv", mime="text/csv", width="stretch",
)
if n_pairs > 1:
    import io
    png_buf = io.BytesIO()
    fig.savefig(png_buf, format="png", dpi=300, bbox_inches="tight", facecolor="white")
    st.download_button(
        "⬇ Chart PNG (300 dpi)", data=png_buf.getvalue(),
        file_name="interrater_kappa_chart.png", mime="image/png", width="stretch",
    )
