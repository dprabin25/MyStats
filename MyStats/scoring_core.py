"""
Core scoring logic for the narrative Precision/Recall/F1 app, kept separate
from the Streamlit UI so it can be unit-tested without launching the app.

Matches the methodology and normalization behavior of the original
`precision_f1_recall.py` exactly (verified against its ground truth,
narrative predictions, and its `narrative_precision_recall_f1.csv` output --
every TP/FP/FN and rounded P/R/F1 value reproduces to the hundredth):

  - ONE shared ground-truth element list is compared against EACH
    narrative's own predicted-element list (not a separate ground truth
    per narrative).
  - Matching is EXACT STRING match after stripping whitespace, with an
    explicit alias/synonym map applied first (e.g. "IL-1B" -> "IL-B",
    "B-cells" -> "B-cell") -- NOT case-folding by default. This preserves
    the original script's important distinction that IL-1A and IL-1B are
    NOT the same cytokine and must never be folded into each other; only
    an explicit, intentional alias does that collapsing, never a generic
    lowercase pass.
  - Precision/Recall/F1 are computed from the FULL-PRECISION TP/FP/FN
    counts, and only rounded to 2 decimals afterward for display/CSV/chart
    (matching the original script's own rounding order).
"""

import re

ROMAN_NUMERALS = [
    (1000, "M"), (900, "CM"), (500, "D"), (400, "CD"),
    (100, "C"), (90, "XC"), (50, "L"), (40, "XL"),
    (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I"),
]


def to_roman(n):
    """1 -> 'I', 2 -> 'II', ... used for the default 'Narrative <roman>'
    display name when the user leaves a narrative unrenamed, so adding a
    6th, 7th, ... narrative keeps following the same I, II, III, ... style
    the original script used for the first five."""
    if n <= 0:
        return str(n)
    result = []
    remainder = n
    for value, symbol in ROMAN_NUMERALS:
        count, remainder = divmod(remainder, value)
        result.append(symbol * count)
    return "".join(result)


def parse_elements(text):
    """Split a block of text into a list of element strings (whitespace-
    trimmed), accepting newline, comma, or semicolon separators. Order and
    exact casing are preserved -- normalization/deduping happens later via
    normalize_name, not here."""
    if not isinstance(text, str) or not text.strip():
        return []
    parts = re.split(r"[\n,;]", text)
    return [p.strip() for p in parts if p.strip()]


def parse_alias_map(text):
    """Parse an alias/synonym map from lines like:
        IL-1B -> IL-B
        IL-1A => IL-A
        B-cells : B-cell
    Accepts '->', '=>', or ':' as the separator (first match wins per
    line). Blank lines and lines without a recognized separator are
    skipped. Returns {raw_name: canonical_name}, exact case preserved."""
    alias_map = {}
    if not isinstance(text, str):
        return alias_map
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        for sep in ("->", "=>", ":"):
            if sep in line:
                raw, canonical = line.split(sep, 1)
                raw, canonical = raw.strip(), canonical.strip()
                if raw and canonical:
                    alias_map[raw] = canonical
                break
    return alias_map


def normalize_name(name, alias_map=None, case_insensitive=False):
    """Apply the alias map (exact match) after stripping whitespace, then
    optionally case-fold. Defaults (no alias map, case-sensitive) reproduce
    plain exact-string matching, same as the original script when
    normalize_name's replacements dict is empty."""
    name = name.strip()
    if alias_map:
        name = alias_map.get(name, name)
    if case_insensitive:
        name = name.lower()
    return name


def normalize_set(elements, alias_map=None, case_insensitive=False):
    return {normalize_name(e, alias_map, case_insensitive) for e in elements}


def prf(ground_truth_set, predicted_set):
    """Precision/recall/F1 for one narrative against the shared ground
    truth, plus raw TP/FP/FN counts and the actual matched/extra/missed
    elements (matches the original script's TP_elements/FP_elements/
    FN_elements CSV columns) -- always show your work, not just a number."""
    tp_set = ground_truth_set & predicted_set
    fp_set = predicted_set - ground_truth_set
    fn_set = ground_truth_set - predicted_set

    tp, fp, fn = len(tp_set), len(fp_set), len(fn_set)
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = (2 * precision * recall / (precision + recall)
          if (precision + recall) > 0 else 0.0)

    return {
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "matched": sorted(tp_set),
        "extra": sorted(fp_set),
        "missed": sorted(fn_set),
    }


def pooled_prf(rows):
    """Micro-averaged (pooled) precision/recall/F1: sum TP/FP/FN across all
    narratives first, then compute one overall P/R/F1 (not an average of
    each narrative's own P/R/F1)."""
    tp = sum(r["tp"] for r in rows)
    fp = sum(r["fp"] for r in rows)
    fn = sum(r["fn"] for r in rows)
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = (2 * precision * recall / (precision + recall)
          if (precision + recall) > 0 else 0.0)
    return {"precision": precision, "recall": recall, "f1": f1,
            "tp": tp, "fp": fp, "fn": fn}
