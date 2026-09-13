"""
Core parsing/classification/concordance logic for the "Known vs Unknown
(Biological-Meaning Concordance)" MyStats tool. Ported faithfully from
the standalone desktop script (same regexes, same table parser, same
pair-merging rules) -- the only real change is that a "run" now comes
from an uploaded file's text plus a condition tag chosen in the UI,
rather than being discovered from a folder structure on disk (a
Streamlit Cloud app has no access to the user's local filesystem).

Pipeline: parse each run's relationship table -> classify the claimed
DIRECTION of each row from its Group Name + Evidence Summary text
(Increase / Decrease / Associative / Contradictory / Unclassified) ->
merge into one direction per element-pair per run -> for every pair of
runs, DIRECTION CONCORDANCE = of the element-pairs BOTH runs discuss,
what fraction do they agree on the direction of -- a biology-level
agreement measure, not a wording-similarity one.
"""

import re
import itertools

from scoring_core import parse_alias_map, normalize_name

# ---------------------------------------------------------------
# Direction classification -- verbatim from the original script.
# ---------------------------------------------------------------
INCREASE_RE = re.compile(
    r"\bincreas\w*|\belevat\w*|\binduc\w*|\bpromot\w*|\bactivat\w*|\bupregulat\w*|"
    r"\bstimulat\w*|\bhigher\b|\bsignificantly elevated\b",
    re.IGNORECASE,
)
DECREASE_RE = re.compile(
    r"\bdecreas\w*|\breduc\w*|\bsuppress\w*|\binhibit\w*|\bdownregulat\w*|\blower\b",
    re.IGNORECASE,
)
ASSOCIATIVE_RE = re.compile(
    r"\bcorrelat\w*|\bassociat\w*|\binteraction\b|\blink\w*|\binvolv\w*|\brelationship\b",
    re.IGNORECASE,
)
PERTURBATION_RE = re.compile(
    r"\bdepletion\b|\bdeplet\w*|\bknockdown\b|\bknock-down\b|\bknockout\b|\bknock-out\b|"
    r"\bsilenc\w*|\bablat\w*|\bblockad\w*|\bblocking\b|\binhibition of\b",
    re.IGNORECASE,
)

DEFAULT_ALIAS_MAP_TEXT = "B-cells -> B-cell"


def classify_direction(text):
    """Increase / Decrease / Associative / Contradictory / Unclassified.

    A decrease-cue in the same sentence as a loss-of-function term
    (depletion/knockdown/knockout/silencing/blockade) is ignored: "X
    depletion reduces Y" is standard supporting evidence that X
    INCREASES Y, not a competing decrease claim about the X-Y
    relationship itself."""
    sentences = re.split(r"(?<=[.!?])\s+", text)
    has_inc = has_dec = False
    for sentence in sentences:
        if INCREASE_RE.search(sentence):
            has_inc = True
        if DECREASE_RE.search(sentence) and not PERTURBATION_RE.search(sentence):
            has_dec = True
    if has_inc and has_dec:
        return "Contradictory"
    if has_inc:
        return "Increase"
    if has_dec:
        return "Decrease"
    if ASSOCIATIVE_RE.search(text):
        return "Associative"
    return "Unclassified"


# ---------------------------------------------------------------
# Relationship-table parsing -- verbatim from the original script,
# except normalization now goes through the shared alias-map helper
# (scoring_core.normalize_name) so it's editable in the UI instead of
# a single hardcoded dict.
# ---------------------------------------------------------------
def parse_relationship_table(text, alias_map=None):
    """text: one run's full file content. alias_map: optional {raw:
    canonical} dict (scoring_core.parse_alias_map output) for element
    name normalization (e.g. "B-cells" -> "B-cell"). Returns a list of
    {"group_name", "elements", "direction"} dicts, one per table row
    that lists 2+ elements. Raises ValueError if no relationship table
    header (a line with both "Group Name" and "List of elements") is
    found."""
    lines = text.splitlines()
    header_idx = next(
        (i for i, l in enumerate(lines) if "Group Name" in l and "List of elements" in l),
        None,
    )
    if header_idx is None:
        raise ValueError("No relationship table header found (a line with both "
                          "'Group Name' and 'List of elements').")
    header_cells = [c.strip() for c in lines[header_idx].strip().strip("|").split("|")]
    col = {name: idx for idx, name in enumerate(header_cells)}
    for required in ("Group Name", "List of elements", "Evidence Summary"):
        if required not in col:
            raise ValueError(f"Relationship table header is missing a '{required}' column.")
    elem_col, name_col, ev_col = col["List of elements"], col["Group Name"], col["Evidence Summary"]

    rows = []
    for line in lines[header_idx + 1:]:
        stripped = line.strip()
        if not stripped or stripped.startswith("###"):
            break
        if re.fullmatch(r"[\-\|\s:]+", stripped):
            continue
        if "|" not in stripped:
            break
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        if len(cells) <= max(elem_col, ev_col):
            continue
        elements = [normalize_name(e, alias_map) for e in cells[elem_col].split(";") if e.strip()]
        if len(elements) < 2:
            continue
        direction = classify_direction(f"{cells[name_col]}. {cells[ev_col]}")
        rows.append({"group_name": cells[name_col], "elements": elements, "direction": direction})
    return rows


DIRECTIONAL = {"Increase", "Decrease"}
SPECIFICITY = {"Increase": 2, "Decrease": 2, "Associative": 1, "Unclassified": 0, "Contradictory": 3}


def pairs_with_direction(rows):
    """{frozenset({a,b}): direction} across all groups in one run.

    Merging two labels for the same pair is only a real
    self-contradiction when both are directional and opposite. A vague
    label (Associative/Unclassified) never overrides a directional
    one -- it's under-specified, not opposing."""
    result = {}
    for row in rows:
        for a, b in itertools.combinations(sorted(row["elements"]), 2):
            key = frozenset((a, b))
            d = row["direction"]
            if key not in result:
                result[key] = d
                continue
            existing = result[key]
            if existing == d:
                continue
            if existing in DIRECTIONAL and d in DIRECTIONAL:
                result[key] = "Contradictory"
            elif SPECIFICITY[d] > SPECIFICITY[existing]:
                result[key] = d
    return result


def comparison_type(condition_a, condition_b):
    """'within-Known' / 'within-Unknown' / 'Known-vs-Unknown' -- matches
    the original script's exact labels for the two condition tags this
    tool works with. Falls back to the same "-vs-" join for any other
    condition pair (defensive; the UI only offers Known/Unknown)."""
    if condition_a == condition_b:
        return f"within-{condition_a}"
    return "-vs-".join(sorted((condition_a, condition_b)))


def pairwise_concordance(run_names, conditions, pair_directions):
    """run_names: list of run display names. conditions: parallel list
    of "Known"/"Unknown" tags. pair_directions: parallel list of
    pairs_with_direction() outputs. Returns a list of rows, one per
    run pair: {"pair", "comparison", "n_shared_relationships",
    "n_concordant", "concordance_rate"} (rate is None, not NaN, when
    the two runs share zero element-pairs -- nothing to agree or
    disagree on)."""
    records = []
    n = len(run_names)
    for i in range(n):
        for j in range(i + 1, n):
            li, lj = run_names[i], run_names[j]
            shared = set(pair_directions[i]) & set(pair_directions[j])
            concordant = [p for p in shared if pair_directions[i][p] == pair_directions[j][p]]
            records.append({
                "pair": f"{li} vs {lj}",
                "comparison": comparison_type(conditions[i], conditions[j]),
                "n_shared_relationships": len(shared),
                "n_concordant": len(concordant),
                "concordance_rate": (len(concordant) / len(shared)) if shared else None,
            })
    return records
