"""
MyStats -- Home page. Lists the available tools; new tools get a new
bullet here (and a new st.Page entry in app.py) as they're added.
"""

import streamlit as st

from branding import inject_style, render_header

inject_style()
render_header("Pick a tool from the sidebar to get started.")

st.subheader("Available tools")

with st.container(border=True):
    st.markdown("### 📈 F1-Score vs Ground Truth Elements")
    st.markdown(
        "Score how well any number of narratives recover a shared ground-truth "
        "element list. Computes precision, recall, and F1 per narrative, with an "
        "editable normalization/alias map and a publication-quality grouped bar "
        "chart (PNG/PDF export)."
    )
    st.page_link("apps/f1_score.py", label="Open this tool →", icon="📈")

with st.container(border=True):
    st.markdown("### 🔗 Citation Agreement")
    st.markdown(
        "Paste any number of narratives; detects every citation of each configured type "
        "(PMID, UniProt accessions, and ImmuneXpresso mentions are preloaded -- add more "
        "sources once you know their format) and builds a Citation ID × narrative agreement "
        "table (no duplicates), with CSV export."
    )
    st.page_link("apps/citation_agreement.py", label="Open this tool →", icon="🔗")

st.caption("More tools will appear here, and in the sidebar, as they're added.")
