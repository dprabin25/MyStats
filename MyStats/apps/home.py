"""
MyStats -- Home page. Lists the available tools; new tools get a new
bullet here (and a new st.Page entry in app.py) as they're added.
"""

import streamlit as st

from branding import inject_style, render_header

inject_style()
render_header("MyStats", "A growing toolkit of statistical scoring &amp; analysis apps. Pick a tool from the sidebar to get started.")

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

with st.container(border=True):
    st.markdown("### 🔁 Reproducibility (V-measure)")
    st.markdown(
        "List the elements you're tracking, then for each run enter which ones it grouped "
        "together (plus anything found alone). No group naming or matching needed -- scores "
        "pairwise run-to-run agreement with V-measure, a symmetric cluster-agreement score that "
        "needs no run to be \"ground truth,\" with CSV and chart export."
    )
    st.page_link("apps/reproducibility.py", label="Open this tool →", icon="🔁")

with st.container(border=True):
    st.markdown("### 🤝 Inter-rater Agreement (Cohen's Kappa)")
    st.markdown(
        "Each rater lists which elements they see paired together (or \"No pair\"). Scores "
        "chance-corrected agreement with Cohen's Kappa on \"same group or not,\" across every "
        "pair of elements anyone mentioned, with CSV and chart export."
    )
    st.page_link("apps/interrater_agreement.py", label="Open this tool →", icon="🤝")

with st.container(border=True):
    st.markdown("### 🕸️ Relationship Agreement (Jaccard / Dice)")
    st.markdown(
        "For narratives that report individual pairwise relationships (\"X increases Y\") "
        "rather than clean clusters. Enter each run's relationships as Element A / Element B "
        "rows and scores Jaccard/Dice similarity of the relationship sets directly -- no "
        "clustering, so a hub element mentioned in many relationships never drags its "
        "unrelated partners together, with CSV and chart export."
    )
    st.page_link("apps/relationship_agreement.py", label="Open this tool →", icon="🕸️")

st.caption("More tools will appear here, and in the sidebar, as they're added.")
