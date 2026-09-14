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
    slightly rounded, consistent controls with subtle depth (hover states,
    soft shadows, a quieter surface behind metrics) rather than flat,
    default Streamlit chrome. Safe to call once per page script; unlike
    st.set_page_config, st.markdown-based CSS has no once-per-app
    restriction."""
    st.markdown(
        """
        <style>
            html, body, [class*="css"]  {
                font-family: -apple-system, "Segoe UI", Helvetica, Arial, sans-serif;
            }
            .block-container { padding-top: 2.1rem; padding-bottom: 3rem; max-width: 1180px; }

            /* ---- page header: a small brand eyebrow, then the page's own
               name as the real, prominent heading -- not the other way
               around, so every page reads as a distinct tool rather than
               six pages that all just say "MyStats" in large type. ---- */
            .mystats-eyebrow { display: flex; align-items: center; gap: 0.55rem; margin-bottom: 0.7rem; }
            .mystats-wordmark {
                font-size: 0.76rem; font-weight: 800; color: #2a78d6; letter-spacing: 0.15em;
                text-transform: uppercase;
            }
            .mystats-badge {
                background: #eaf1fb; color: #2a78d6; font-size: 0.62rem; font-weight: 700;
                padding: 2px 9px; border-radius: 999px; letter-spacing: 0.05em;
                text-transform: uppercase; border: 1px solid #cfe0f7;
            }
            .mystats-title {
                font-size: 2.0rem; font-weight: 800; color: #14213d; margin: 0 0 0.3rem 0;
                letter-spacing: -0.015em; line-height: 1.2;
            }
            .mystats-subtitle { color: #5b6472; font-size: 1.02rem; margin: 0 0 1.1rem 0; max-width: 62ch; }
            .mystats-divider {
                height: 1px; border: none; margin: 0 0 1.9rem 0;
                background: linear-gradient(to right, #e2e5ea, rgba(226,229,234,0));
            }

            /* ---- controls: a visible hover/active state instead of a
               static button, and a primary action that reads as the one
               thing to click on the page. ---- */
            .stButton>button, .stDownloadButton>button {
                border-radius: 8px; font-weight: 600; border: 1px solid #d8dce3;
                transition: border-color 0.15s ease, color 0.15s ease, box-shadow 0.15s ease;
            }
            .stButton>button:hover, .stDownloadButton>button:hover {
                border-color: #2a78d6; color: #2a78d6;
            }
            .stButton>button[kind="primary"] {
                background-color: #2a78d6; border-color: #2a78d6;
                box-shadow: 0 2px 10px rgba(42, 120, 214, 0.28);
            }
            .stButton>button[kind="primary"]:hover {
                background-color: #1f63b8; border-color: #1f63b8;
            }

            section[data-testid="stExpander"] {
                border-radius: 10px; border: 1px solid #e6e8ec;
            }
            div[data-testid="stDataFrame"] {
                border-radius: 8px; overflow: hidden; border: 1px solid #e6e8ec;
            }
            div[data-testid="stVerticalBlockBorderWrapper"] {
                border-radius: 10px; border-color: #e6e8ec !important;
            }
            div[data-testid="stMetric"] {
                background: #f8fafc; border: 1px solid #eef0f3; border-radius: 10px;
                padding: 0.9rem 1.1rem;
            }
            div[data-testid="stMetricLabel"] { color: #5b6472; }

            [data-testid="stSidebarNav"] { padding-top: 0.5rem; }
            [data-testid="stSidebar"] { border-right: 1px solid #ebedf0; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_header(title, subtitle=None):
    """title: the page's own name, e.g. "F1-Score vs Ground Truth
    Elements" -- rendered as the prominent page heading (this is the
    thing that actually tells you which tool you're on; a small "MyStats"
    eyebrow above it carries the brand instead of competing for the same
    visual weight). subtitle: an optional one-line description shown
    beneath it in muted text -- most tool pages rely on their own
    st.caption() for that instead and don't pass one; Home does."""
    st.markdown(
        f"""
        <div class="mystats-eyebrow">
            <span class="mystats-wordmark">MyStats</span>
            <span class="mystats-badge">Beta</span>
        </div>
        <div class="mystats-title">{title}</div>
        {f'<div class="mystats-subtitle">{subtitle}</div>' if subtitle else ''}
        <hr class="mystats-divider" />
        """,
        unsafe_allow_html=True,
    )
