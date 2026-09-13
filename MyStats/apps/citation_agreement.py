"""
MyStats tool: Citation Agreement

Paste each narrative's text (as many as you want); the app detects every
citation of each configured type -- PMID and UniProt accessions are
preloaded, and more types (e.g. Immunoxpresso) can be added once their
format is known -- and builds a unified Citation ID x Narrative
agreement table: one row per distinct (type, ID) pair (no duplicates),
Yes/No for whether each narrative cites it, and a "Runs citing" count.

Citation types are user-editable (name + regex pattern with one
capturing group for the ID), because sources don't all cite the same
way -- the label can come before or after the ID, and the separator can
be ":", ",", or nothing at all.
"""

import pandas as pd
import streamlit as st

from branding import inject_style, render_header
from citation_extract import DEFAULT_CITATION_TYPES, extract_citations, build_agreement_table

inject_style()
render_header("Citation Agreement")

st.caption(
    "Paste each narrative's text below. The app detects every citation of each configured "
    "type and builds a Citation ID × narrative agreement table -- one row per distinct "
    "citation, no duplicates -- plus how many narratives cite each one."
)

# ---------------- session state ----------------
# Same stable-id pattern as the other MyStats tools: widget keys are
# built from a permanent id, not list position, so removing a row never
# leaves another row showing stale cached text.
if "cite_types" not in st.session_state:
    st.session_state.cite_types = [dict(ct) for ct in DEFAULT_CITATION_TYPES]
if "cite_next_id" not in st.session_state:
    st.session_state.cite_next_id = 0
if "cite_narratives" not in st.session_state:
    st.session_state.cite_narratives = []
    for _ in range(2):
        nid = st.session_state.cite_next_id
        st.session_state.cite_next_id += 1
        st.session_state.cite_narratives.append({"id": nid, "name": "", "text": ""})
if "cite_generated" not in st.session_state:
    st.session_state.cite_generated = False


def add_narrative():
    nid = st.session_state.cite_next_id
    st.session_state.cite_next_id += 1
    st.session_state.cite_narratives.append({"id": nid, "name": "", "text": ""})


def remove_narrative(nid):
    st.session_state.cite_narratives = [n for n in st.session_state.cite_narratives if n["id"] != nid]


def reset_all():
    st.session_state.cite_types = [dict(ct) for ct in DEFAULT_CITATION_TYPES]
    st.session_state.cite_narratives = []
    for _ in range(2):
        nid = st.session_state.cite_next_id
        st.session_state.cite_next_id += 1
        st.session_state.cite_narratives.append({"id": nid, "name": "", "text": ""})
    st.session_state.cite_generated = False


def add_citation_type():
    st.session_state.cite_types.append({"name": "", "pattern": ""})


def remove_citation_type(idx):
    del st.session_state.cite_types[idx]


def _to_roman(n):
    numerals = [(1000, "M"), (900, "CM"), (500, "D"), (400, "CD"), (100, "C"), (90, "XC"),
                (50, "L"), (40, "XL"), (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I")]
    result, remainder = [], n
    for value, symbol in numerals:
        count, remainder = divmod(remainder, value)
        result.append(symbol * count)
    return "".join(result)


with st.expander("Advanced: citation types", expanded=False):
    st.markdown(
        "Each row is one citation type: a name and a regex pattern with exactly one capturing "
        "group for the ID. PMID and UniProt are preloaded. Add a row for any other source (e.g. "
        "**Immunoxpresso**) once you know how it's formatted in your narratives -- label/ID order "
        "and separator (`:`, `,`, or none) don't matter as long as the pattern captures the ID."
    )
    for i, ct in enumerate(st.session_state.cite_types):
        cols = st.columns([2, 5, 1])
        ct["name"] = cols[0].text_input("Type name", value=ct["name"], key=f"cite_type_name_{i}")
        ct["pattern"] = cols[1].text_input("Regex pattern", value=ct["pattern"], key=f"cite_type_pattern_{i}")
        cols[2].button("🗑", key=f"cite_type_remove_{i}", on_click=remove_citation_type, args=(i,))
    st.button("➕ Add citation type", on_click=add_citation_type, key="cite_type_add")

st.subheader("1. Narratives")
top_cols = st.columns([1, 1, 5])
top_cols[0].button("➕ Add narrative", on_click=add_narrative, width="stretch", key="cite_add_top")
top_cols[1].button("↺ Reset all", on_click=reset_all, width="stretch", key="cite_reset")

for i, n in enumerate(st.session_state.cite_narratives):
    nid = n["id"]
    default_label = f"Narrative {_to_roman(i + 1)}"
    with st.container(border=True):
        header_cols = st.columns([5, 1])
        n["name"] = header_cols[0].text_input(
            "Display name (optional)", value=n["name"], key=f"cite_name_{nid}",
            placeholder=f"{default_label} (leave blank to use this default)",
        )
        header_cols[1].button(
            "🗑 Remove", key=f"cite_remove_{nid}", on_click=remove_narrative, args=(nid,),
            width="stretch",
        )
        n["text"] = st.text_area(
            "Narrative text", value=n["text"], key=f"cite_text_{nid}", height=160,
            placeholder=(
                "Paste the narrative text here, e.g.\n"
                "...supported by prior work (PMID: 35578115) and (A0A246K8E8, UniProt)..."
            ),
        )

st.button("➕ Add narrative", on_click=add_narrative, key="cite_add_bottom")

st.divider()
if st.button("🔄 Generate agreement table", type="primary", width="stretch", key="cite_generate"):
    st.session_state.cite_generated = True

if not st.session_state.cite_generated:
    st.info("Click **Generate agreement table** above to detect citations from what you've pasted.")
    st.stop()

# ---------------- compute ----------------
active_types = [ct for ct in st.session_state.cite_types if ct["name"].strip() and ct["pattern"].strip()]
if not active_types:
    st.warning("No citation types are configured -- add at least one (name + regex pattern) in Advanced above.")
    st.stop()

narrative_citations = []
for i, n in enumerate(st.session_state.cite_narratives):
    display_name = n["name"].strip() or f"Narrative {_to_roman(i + 1)}"
    citations = extract_citations(n["text"], active_types)
    narrative_citations.append((display_name, citations))

if not any(citations for _, citations in narrative_citations):
    st.info("No citations detected yet -- paste narrative text containing citations like \"(PMID: 12345678)\" above.")
    st.stop()

rows, names = build_agreement_table(narrative_citations)
agreement_df = pd.DataFrame(rows)[["Type", "Citation ID"] + names + ["Runs citing"]]

st.subheader("2. Citation × Narrative agreement table")

type_counts = agreement_df["Type"].value_counts()
metric_cols = st.columns(len(type_counts) + 1)
metric_cols[0].metric("Total citations", len(agreement_df))
for col, (type_name, count) in zip(metric_cols[1:], type_counts.items()):
    col.metric(type_name, int(count))

st.dataframe(agreement_df, width="stretch", hide_index=True)

st.subheader("3. Download")
st.download_button(
    "⬇ CSV (citation_agreement_across_runs.csv)", data=agreement_df.to_csv(index=False),
    file_name="citation_agreement_across_runs.csv", mime="text/csv", width="stretch",
)
