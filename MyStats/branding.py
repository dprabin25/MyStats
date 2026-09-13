"""
Shared visual branding for MyStats, imported by app.py (the MasterApp
entry point) and by every individual tool page under apps/. Kept in one
place so every tool looks like part of the same product, and so a new
tool only needs two lines (inject_style() + render_header()) to match.
"""

import streamlit as st


def inject_style():
    """CSS overrides for a clean, professional look -- a single accent
    color (matching chart_build.py's own palette), a branded header, and
    slightly rounded, consistent controls. Safe to call once per page
    script; unlike st.set_page_config, st.markdown-based CSS has no
    once-per-app restriction."""
    st.markdown(
        """
        <style>
            html, body, [class*="css"]  {
                font-family: -apple-system, "Segoe UI", Helvetica, Arial, sans-serif;
            }
            .block-container { padding-top: 2.2rem; padding-bottom: 3rem; max-width: 1180px; }

            .mystats-header { display: flex; align-items: baseline; gap: 0.6rem; }
            .mystats-title {
                font-size: 2.05rem; font-weight: 800; color: #14213d; margin: 0;
                letter-spacing: -0.01em;
            }
            .mystats-badge {
                background: #2a78d6; color: #ffffff; font-size: 0.68rem; font-weight: 700;
                padding: 3px 10px; border-radius: 999px; letter-spacing: 0.04em;
                text-transform: uppercase; position: relative; top: -2px;
            }
            .mystats-subtitle { color: #5b6472; font-size: 1.0rem; margin: 0.3rem 0 1.6rem 0; }

            .stButton>button, .stDownloadButton>button {
                border-radius: 8px; font-weight: 600;
            }
            .stButton>button[kind="primary"] { background-color: #2a78d6; border-color: #2a78d6; }

            section[data-testid="stExpander"] {
                border-radius: 10px; border: 1px solid #e6e8ec;
            }
            div[data-testid="stDataFrame"] {
                border-radius: 8px; overflow: hidden; border: 1px solid #e6e8ec;
            }
            div[data-testid="stVerticalBlockBorderWrapper"] { border-radius: 10px; }

            [data-testid="stSidebarNav"] { padding-top: 0.5rem; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_header(subtitle="A growing toolkit of statistical scoring &amp; analysis apps."):
    st.markdown(
        f"""
        <div class="mystats-header">
            <span class="mystats-title">MyStats</span>
            <span class="mystats-badge">Beta</span>
        </div>
        <div class="mystats-subtitle">{subtitle}</div>
        """,
        unsafe_allow_html=True,
    )
