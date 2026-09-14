"""
Citation extraction + cross-run agreement table, for the "Citation
Agreement" MyStats tool. Detects multiple citation types (PMID, UniProt
accessions, and any other type the user configures) inside pasted
narrative text, and builds a unified agreement table -- kept separate
from the Streamlit UI so it's testable without launching the app.
"""

import re

# Matches "PMID" (any case) next to 4-9 digits, in EITHER order --
# "PMID: 12345678" / "PMID 12345678" / "pmid:12345678" (label first,
# as prose usually writes it), AND "12345678 (PMID)" / "12345678(PMID)"
# (number first, as a "List of ... IDs (Evidence Source)" table column
# typically writes it -- e.g. "35578115 (PMID); 28232966 (PMID)"). Only
# matching the label-first form silently missed every citation written
# the other way around: a real run found ZERO citations in narratives
# whose only PMID mentions were in that table format, understating
# "Runs citing" and dropping whole narratives from the agreement table
# with no error or warning. The label is required in both directions
# (never a bare 4-9 digit number alone), since a bare number that size
# is common in ordinary text and would false-positive constantly
# otherwise.
PMID_PATTERN = r"PMID\s*:?\s*(\d{4,9})|(\d{4,9})\s*\(\s*PMID\s*\)"

# Standard UniProtKB accession format: the classic 6-character form
# ([A-NR-Z][0-9]([A-Z][A-Z0-9]{2}[0-9])) or the "extended" 10-character
# form introduced for combinatorially diverse proteins such as
# immunoglobulins (two repeats of that same 4-character block), plus the
# [OPQ]-prefixed 6-character variant. Matched directly against the
# accession itself, not the word "UniProt" -- the format is distinctive
# enough on its own that it doesn't matter whether a narrative writes
# "(UniProt: A0A246K8E8)", "(A0A246K8E8, UniProt)", or just the bare
# accession with no label at all; label order and separator (":", ",",
# or none) never need to be guessed.
UNIPROT_PATTERN = (
    r"\b((?:[OPQ][0-9][A-Z0-9]{3}[0-9])"
    r"|(?:[A-NR-Z][0-9](?:[A-Z][A-Z0-9]{2}[0-9]){1,2}))\b"
)

# ImmuneXpresso (sometimes spelled "Immunoxpresso") is the PubMed-mining
# tool from Vered et al., Nature Biotechnology 2018 (PMID 29912209) that
# builds cytokine<->immune-cell interaction networks from the literature.
# It isn't a per-record database with its own accession scheme the way
# UniProt is -- there's no public "ImmuneXpresso ID" format -- so a
# narrative citing it is expected to just name the tool, with no separate
# ID to capture. Both common spellings are matched and normalized to one
# canonical name below, so "ImmuneXpresso" and "Immunoxpresso" collapse
# to the same agreement-table row instead of splitting into two. If your
# narratives actually cite a specific per-entry ID from it, replace this
# pattern in the app's "Advanced: citation types" panel with one that
# captures that ID instead.
IMMUNEXPRESSO_PATTERN = r"\b(Immune[Xx]presso|Immuno[Xx]presso)\b"

# Preloaded citation types. Add more from the app's "Advanced: citation
# types" panel once you know a new source's format -- nothing here needs
# to be hardcoded for a new type to be supported.
DEFAULT_CITATION_TYPES = [
    {"name": "PMID", "pattern": PMID_PATTERN},
    {"name": "UniProt", "pattern": UNIPROT_PATTERN},
    {"name": "ImmuneXpresso", "pattern": IMMUNEXPRESSO_PATTERN},
]

# Per-type normalization applied to whatever the pattern captures, keyed
# by lowercased type name. UniProt accessions are conventionally
# upper-cased; ImmuneXpresso mentions collapse both spellings to one
# canonical row instead of matching case/spelling verbatim.
_NORMALIZERS = {
    "uniprot": lambda s: s.upper(),
    "immunexpresso": lambda s: "ImmuneXpresso",
}


def extract_citations(text, citation_types):
    """text: narrative text. citation_types: list of {"name", "pattern"}
    dicts, each pattern having one or more capturing groups for the ID --
    more than one when a pattern matches the ID in multiple label/number
    orders via alternation (like PMID_PATTERN above), where exactly one
    group is populated per match and the rest come back empty. Returns a
    set of (type_name, id) tuples found in text (case-insensitive
    matching), deduplicated within the narrative -- a narrative either
    cites something or it doesn't, it isn't a count of mentions."""
    if not isinstance(text, str) or not text.strip():
        return set()
    found = set()
    for ct in citation_types:
        name = (ct.get("name") or "").strip()
        pattern = (ct.get("pattern") or "").strip()
        if not name or not pattern:
            continue
        try:
            matches = re.findall(pattern, text, flags=re.IGNORECASE)
        except re.error:
            continue
        for match in matches:
            if isinstance(match, str):
                ident = match
            else:
                # Multiple alternatives, each with its own group -- take
                # whichever one actually matched (the others are "").
                ident = next((g for g in match if g), "")
            ident = ident.strip()
            if not ident:
                continue
            normalize = _NORMALIZERS.get(name.lower())
            found.add((name, normalize(ident) if normalize else ident))
    return found


def _id_sort_key(citation_id):
    try:
        return (0, int(citation_id))
    except (TypeError, ValueError):
        return (1, str(citation_id))


def build_agreement_table(narrative_citations):
    """narrative_citations: list of (display_name, set_of_(type, id))
    tuples, in narrative order. Returns (rows, names) where rows is a
    list of dicts: {"Type": type_name, "Citation ID": id,
    <narrative name>: "Yes"/"No", ..., "Runs citing": n} -- one row per
    distinct (type, id) pair (no duplicates across narratives), sorted
    by Runs citing descending, then Type, then ID (numeric-aware)."""
    names = [name for name, _ in narrative_citations]
    all_citations = set()
    for _, citations in narrative_citations:
        all_citations |= citations

    rows = []
    for type_name, cid in all_citations:
        row = {"Type": type_name, "Citation ID": cid}
        count = 0
        for name, citations in narrative_citations:
            hit = (type_name, cid) in citations
            row[name] = "Yes" if hit else "No"
            count += 1 if hit else 0
        row["Runs citing"] = count
        rows.append(row)

    rows.sort(key=lambda r: (-r["Runs citing"], r["Type"], _id_sort_key(r["Citation ID"])))
    return rows, names
