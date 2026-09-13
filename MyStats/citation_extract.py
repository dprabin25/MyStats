"""
Citation extraction + cross-run agreement table, for the "Citation
Agreement" MyStats tool. Detects multiple citation types (PMID, UniProt
accessions, and any other type the user configures) inside pasted
narrative text, and builds a unified agreement table -- kept separate
from the Streamlit UI so it's testable without launching the app.
"""

import re

# Matches "PMID" (any case), an optional colon/space, then 4-9 digits --
# covers "(PMID: 12345678)", "PMID 12345678", "pmid:12345678", etc. The
# label is required for PMID specifically, since a bare 4-9 digit number
# is common in ordinary text and would false-positive constantly without
# it.
PMID_PATTERN = r"PMID\s*:?\s*(\d{4,9})"

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
    dicts, each pattern having exactly one capturing group for the ID.
    Returns a set of (type_name, id) tuples found in text
    (case-insensitive matching), deduplicated within the narrative --
    a narrative either cites something or it doesn't, it isn't a count
    of mentions."""
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
            ident = match if isinstance(match, str) else (match[0] if match else "")
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
