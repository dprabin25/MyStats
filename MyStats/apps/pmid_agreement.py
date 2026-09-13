"""
MyStats tool: PMIDs Across Runs

Paste each narrative's text (as many as you want); the app detects every
PMID cited in it (matching "PMID" followed by digits, in any common
format -- "(PMID: 12345678)", "PMID 12345678", "pmid:12345678", etc.),
and builds a PMID x Narrative agreement table: one row per distinct PMID
(no duplicates), Yes/No for whether each narrative cites it, and a
"Runs citing" count -- plus a frequency summary (how many PMIDs were
cited by exactly N narratives).

Verified against a real validated table (pmid_agreement_across_runs.csv /
pmid_agreement_frequency.csv): reproduces both exactly, row for row.
"""

import io

import pandas as pd
import streamlit as st

from branding import inject_style, render_header
from pmid_extract import DEFAULT_PMID_PATTERN, extract_pmids, build_agreement_table, build_frequency_table
from chart_build import build_single_series_bar_chart

inject_style()
render_header("PMIDs Across Runs")

st.caption(
    "Paste each narrative's text below. The app detects every PMID cited in it and builds "
    "a PMID × narrative agreement table -- one row per distinct PMID, no duplicates -- "
    "plus a count of how many narratives cite each one."
)

DEFAULT_PATTERN_HELP = (
    "Elements are detected with the regular expression `{}` (case-insensitive) -- matches "
    "\"PMID\", an optional colon/space, then 4-9 digits. Covers \"(PMID: 12345678)\", "
    "\"PMID 12345678\", \"pmid:12345678\", etc. Override it below only if your narratives "
    "cite PMIDs in a different format."
).format(DEFAULT_PMID_PATTERN)

# ---------------- session state ----------------
# Same stable-id pattern as the F1-Score tool: widget keys are built from
# a permanent id, not list position, so removing a narrative never leaves
# another row showing stale cached text.
if "pmid_pattern" not in st.session_state:
    st.session_state.pmid_pattern = DEFAULT_PMID_PATTERN
if "pmid_next_id" not in st.session_state:
    st.session_state.pmid_next_id = 0
if "pmid_narratives" not in st.session_state:
    st.session_state.pmid_narratives = []
    for _ in range(2):
        nid = st.session_state.pmid_next_id
        st.session_state.pmid_next_id += 1
        st.session_state.pmid_narratives.append({"id": nid, "name": "", "text": ""})
if "pmid_generated" not in st.session_state:
    st.session_state.pmid_generated = False


def add_narrative():
    nid = st.session_state.pmid_next_id
    st.session_state.pmid_next_id += 1
    st.session_state.pmid_narratives.append({"id": nid, "name": "", "text": ""})


def remove_narrative(nid):
    st.session_state.pmid_narratives = [n for n in st.session_state.pmid_narratives if n["id"] != nid]


def reset_all():
    st.session_state.pmid_pattern = DEFAULT_PMID_PATTERN
    st.session_state.pmid_narratives = []
    for _ in range(2):
        nid = st.session_state.pmid_next_id
        st.session_state.pmid_next_id += 1
        st.session_state.pmid_narratives.append({"id": nid, "name": "", "text": ""})
    st.session_state.pmid_generated = False


def _to_roman(n):
    numerals = [(1000, "M"), (900, "CM"), (500, "D"), (400, "CD"), (100, "C"), (90, "XC"),
                (50, "L"), (40, "XL"), (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I")]
    result, remainder = [], n
    for value, symbol in numerals:
        count, remainder = divmod(remainder, value)
        result.append(symbol * count)
    return "".join(result)


with st.expander("Advanced: PMID detection pattern (optional)", expanded=False):
    st.markdown(DEFAULT_PATTERN_HELP)
    st.session_state.pmid_pattern = st.text_input(
        "PMID regex pattern", value=st.session_state.pmid_pattern,
    )

st.subheader("1. Narratives")
top_cols = st.columns([1, 1, 5])
top_cols[0].button("➕ Add narrative", on_click=add_narrative, width="stretch", key="pmid_add_top")
top_cols[1].button("↺ Reset all", on_click=reset_all, width="stretch", key="pmid_reset")

for i, n in enumerate(st.session_state.pmid_narratives):
    nid = n["id"]
    default_label = f"Narrative {_to_roman(i + 1)}"
    with st.container(border=True):
        header_cols = st.columns([5, 1])
        n["name"] = header_cols[0].text_input(
            "Display name (optional)", value=n["name"], key=f"pmid_name_{nid}",
            placeholder=f"{default_label} (leave blank to use this default)",
        )
        header_cols[1].button(
            "🗑 Remove", key=f"pmid_remove_{nid}", on_click=remove_narrative, args=(nid,),
            width="stretch",
        )
        n["text"] = st.text_area(
            "Narrative text", value=n["text"], key=f"pmid_text_{nid}", height=160,
            placeholder="Paste the narrative text here, e.g.\n...supported by prior work (PMID: 35578115) and (PMID: 41282272)...",
        )

st.button("➕ Add narrative", on_click=add_narrative, key="pmid_add_bottom")

st.divider()
if st.button("🔄 Generate table & chart", type="primary", width="stretch", key="pmid_generate"):
    st.session_state.pmid_generated = True

if not st.session_state.pmid_generated:
    st.info("Click **Generate table & chart** above to detect PMIDs from what you've pasted.")
    st.stop()

# ---------------- compute ----------------
narrative_pmids = []
for i, n in enumerate(st.session_state.pmid_narratives):
    display_name = n["name"].strip() or f"Narrative {_to_roman(i + 1)}"
    pmids = extract_pmids(n["text"], st.session_state.pmid_pattern)
    narrative_pmids.append((display_name, pmids))

if not any(pmids for _, pmids in narrative_pmids):
    st.info("No PMIDs detected yet -- paste narrative text containing citations like \"(PMID: 12345678)\" above.")
    st.stop()

rows, names = build_agreement_table(narrative_pmids)
agreement_df = pd.DataFrame(rows)[["PMID"] + names + ["Runs citing"]]

st.subheader("2. PMID × Narrative agreement table")
st.dataframe(agreement_df, width="stretch", hide_index=True)

freq_rows = build_frequency_table(rows)
freq_df = pd.DataFrame(freq_rows)

st.subheader("3. Frequency summary")
freq_cols = st.columns([1, 2])
freq_cols[0].dataframe(freq_df, width="stretch", hide_index=True)

fig = build_single_series_bar_chart(
    labels=[str(r["Runs citing"]) for r in freq_rows],
    values=[r["Number of PMIDs"] for r in freq_rows],
    title="PMIDs by Number of Narratives Citing",
    xlabel="Runs citing", ylabel="Number of PMIDs",
)
with freq_cols[1]:
    st.pyplot(fig)

png_buf = io.BytesIO()
fig.savefig(png_buf, format="png", dpi=300, bbox_inches="tight", facecolor="white")

st.subheader("4. Downloads")
dl_cols = st.columns(3)
dl_cols[0].download_button(
    "⬇ CSV (pmid_agreement_across_runs.csv)", data=agreement_df.to_csv(index=False),
    file_name="pmid_agreement_across_runs.csv", mime="text/csv", width="stretch",
)
dl_cols[1].download_button(
    "⬇ CSV (pmid_agreement_frequency.csv)", data=freq_df.to_csv(index=False),
    file_name="pmid_agreement_frequency.csv", mime="text/csv", width="stretch",
)
dl_cols[2].download_button(
    "⬇ Chart PNG (300 dpi)", data=png_buf.getvalue(),
    file_name="pmid_agreement_frequency_chart.png", mime="image/png", width="stretch",
)
