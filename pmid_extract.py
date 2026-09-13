"""
PMID extraction + cross-run agreement table, for the "PMIDs Across Runs"
MyStats tool. Kept separate from the Streamlit UI so it's testable without
launching the app.
"""

import re
from collections import Counter

# Matches "PMID" (any case), an optional colon/space, then 4-9 digits --
# covers "(PMID: 12345678)", "PMID 12345678", "pmid:12345678", etc. If your
# narratives cite PMIDs in a different format, override this pattern in
# the app's advanced section.
DEFAULT_PMID_PATTERN = r"PMID\s*:?\s*(\d{4,9})"


def extract_pmids(text, pattern=DEFAULT_PMID_PATTERN):
    """Return the set of distinct PMIDs found in text (case-insensitive).
    Duplicates within the same narrative collapse to one -- a narrative
    either cites a PMID or it doesn't, it isn't a count of mentions."""
    if not isinstance(text, str) or not text.strip():
        return set()
    try:
        return set(re.findall(pattern, text, flags=re.IGNORECASE))
    except re.error:
        return set()


def build_agreement_table(narrative_pmids):
    """narrative_pmids: list of (display_name, set_of_pmids) in narrative
    order. Returns (rows, names) where rows is a list of dicts:
    {"PMID": pmid, <narrative name>: "Yes"/"No", ..., "Runs citing": n},
    one row per distinct PMID (no duplicates), sorted by Runs citing
    descending then PMID ascending (numeric) -- matches the validated
    pmid_agreement_across_runs.csv ordering exactly."""
    names = [name for name, _ in narrative_pmids]
    all_pmids = set()
    for _, pmids in narrative_pmids:
        all_pmids |= pmids

    def pmid_sort_key(p):
        try:
            return (0, int(p))
        except (TypeError, ValueError):
            return (1, str(p))

    rows = []
    for pmid in all_pmids:
        row = {"PMID": pmid}
        count = 0
        for name, pmids in narrative_pmids:
            hit = pmid in pmids
            row[name] = "Yes" if hit else "No"
            count += 1 if hit else 0
        row["Runs citing"] = count
        rows.append(row)

    rows.sort(key=lambda r: (-r["Runs citing"], pmid_sort_key(r["PMID"])))
    return rows, names


def build_frequency_table(rows):
    """rows: output of build_agreement_table. Returns a list of
    {"Runs citing": n, "Number of PMIDs": count}, sorted by Runs citing
    ascending -- matches pmid_agreement_frequency.csv."""
    counts = Counter(r["Runs citing"] for r in rows)
    return [{"Runs citing": k, "Number of PMIDs": counts[k]} for k in sorted(counts)]
