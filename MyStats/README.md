# MyStats

## Narrative Precision / Recall / F1

A Streamlit app for scoring how well a narrative (e.g. a BioShift output, or
any tool's output) recovers a set of ground-truth elements. One shared
ground-truth list is compared against any number of narratives' own
predicted-element lists; precision, recall, and F1 are computed per
narrative and shown as a publication-style grouped bar chart.

**Run locally:**

```
pip install -r requirements.txt
streamlit run app.py
```

**Files:**
- `app.py` — the Streamlit UI (ground truth input, narrative add/remove/rename, results table, chart, downloads)
- `scoring_core.py` — matching/normalization and precision/recall/F1 math (no Streamlit dependency, unit-testable on its own)
- `chart_build.py` — the grouped bar chart (publication-quality styling, CVD-checked palette)
- `requirements.txt` — Python dependencies
