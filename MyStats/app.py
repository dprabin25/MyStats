"""
MyStats -- MasterApp.

Owns page config and navigation only. Each actual tool lives in its own
file under apps/, so adding a new tool later means: write apps/new_tool.py,
add one st.Page(...) line below, done -- this file never has to grow past
that.

Run it locally:
    pip install -r requirements.txt
    streamlit run app.py
It opens in your browser at http://localhost:8501.
"""

import streamlit as st

st.set_page_config(
    page_title="MyStats",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

home_page = st.Page("apps/home.py", title="Home", icon="🏠", default=True)
f1_score_page = st.Page("apps/f1_score.py", title="F1-Score vs Ground Truth Elements", icon="📈")

# New tools get appended to this list as they're built -- nothing else in
# this file needs to change.
pg = st.navigation([home_page, f1_score_page])
pg.run()
