"""
Element-grouping parsing + pairwise/aggregate V-measure computation for
the "Reproducibility (V-measure)" MyStats tool. Kept separate from the
Streamlit UI so it's testable without launching the app.

Pipeline (per mechanism): each run's pasted text says which elements it
found shifting together (one group per line) -> that implies a
partition of the tracked elements for that run -> V-measure between two
runs' partitions scores how well they agree -> averaging over all run
pairs gives one reproducibility number for the mechanism.
"""

import re

from vmeasure_core import v_measure_score


def parse_element_list(text):
    """Flat list of tracked elements: one per line, or comma/semicolon
    separated -- same convention as the rest of MyStats. Case preserved
    (exact match, no folding), input order preserved, duplicates
    dropped."""
    if not isinstance(text, str):
        return []
    seen = set()
    elements = []
    for line in text.replace(";", ",").splitlines():
        for part in line.split(","):
            e = part.strip()
            if e and e not in seen:
                seen.add(e)
                elements.append(e)
    return elements


def parse_groups(text):
    """Each non-empty line is one group; elements within a line are
    comma/semicolon separated. Returns a list of element lists, in the
    order the groups appear (an element repeated within one line is
    deduplicated; repeats across lines are handled by build_labels)."""
    if not isinstance(text, str):
        return []
    groups = []
    for line in text.splitlines():
        elems = [e.strip() for e in line.replace(";", ",").split(",")]
        elems = [e for e in elems if e]
        if elems:
            groups.append(elems)
    return groups


def build_labels(groups, tracked_elements=None):
    """groups: list of element lists (parse_groups output). tracked_elements:
    optional explicit vocabulary (parse_element_list output). Returns a
    dict element -> label (an int; only equality between labels within
    the SAME dict is meaningful, the values themselves carry no
    ordering).

    - Every element mentioned in `groups` gets its group's index as its
      label (first group it appears in, if repeated).
    - If tracked_elements is given: elements in `groups` that aren't in
      the tracked vocabulary are dropped as noise/typos, AND every
      tracked element that this run never mentions in any group gets
      its own singleton label. That singleton is deliberate, not a gap
      -- it means "this run didn't recover/group this element", and
      keeping it labeled (rather than omitting it) is what lets that
      disagreement show up as a lower V-measure instead of being
      silently excluded from the comparison.
    - If tracked_elements is None, the label set is exactly what the
      groups say -- nothing is dropped, nothing gets an invented
      singleton, and an element only one run happens to mention is
      handled by the intersection step in pairwise_v_measure instead."""
    labels = {}
    group_id = 0
    for group in groups:
        used = False
        for e in group:
            if tracked_elements is not None and e not in tracked_elements:
                continue
            if e not in labels:
                labels[e] = group_id
                used = True
        if used:
            group_id += 1

    if tracked_elements is not None:
        next_singleton = group_id
        for e in tracked_elements:
            if e not in labels:
                labels[e] = next_singleton
                next_singleton += 1

    return labels


def split_sentences(text):
    """Split narrative text into sentence-ish chunks: first on
    newlines (narratives often list findings one per line), then on
    sentence-ending punctuation within each line. Deliberately simple
    -- it doesn't need to be a real sentence tokenizer, just a
    consistent unit of "mentioned close together"."""
    if not isinstance(text, str):
        return []
    sentences = []
    for line in re.split(r"[\r\n]+", text):
        for s in re.split(r"(?<=[.!?])\s+", line):
            s = s.strip()
            if s:
                sentences.append(s)
    return sentences


def _mentions(sentence, element):
    """Whether `element` appears in `sentence` as a whole token, not as
    a substring of a longer one -- e.g. "IL-1" must not match inside
    "IL-10" or "IL-12". Case-insensitive, since narrative prose
    capitalizes inconsistently (start of sentence, headers, etc.) in a
    way that isn't meant to distinguish entities."""
    pattern = r"(?<![A-Za-z0-9])" + re.escape(element) + r"(?![A-Za-z0-9])"
    return re.search(pattern, sentence, flags=re.IGNORECASE) is not None


def build_labels_from_narrative(text, tracked_elements):
    """text: one run's raw narrative for this mechanism. tracked_elements:
    the known vocabulary (parse_element_list output) -- required, since
    automatic relation detection only makes sense against a known list,
    not arbitrary text. Returns an element -> label dict via union-find
    over sentence co-occurrence: two tracked elements get the SAME
    label iff this narrative mentions them together in at least one
    sentence, directly or transitively through a chain of shared
    sentences (A+B in one sentence, B+C in another -> A, B, C all one
    group). An element the narrative never mentions at all still gets
    its own singleton label -- it's "not recovered" by this run, and
    keeping it labeled (instead of omitted) is what lets that
    disagreement show up as a lower V-measure rather than being
    silently excluded from the comparison."""
    n = len(tracked_elements)
    parent = list(range(n))
    index = {e: i for i, e in enumerate(tracked_elements)}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x, y):
        rx, ry = find(x), find(y)
        if rx != ry:
            parent[rx] = ry

    for sentence in split_sentences(text):
        present = [e for e in tracked_elements if _mentions(sentence, e)]
        for e in present[1:]:
            union(index[present[0]], index[e])

    return {e: find(index[e]) for e in tracked_elements}


def pairwise_v_measure(labels_a, labels_b):
    """labels_a, labels_b: element -> label dicts for two runs (same
    mechanism, from build_labels). Compares only elements present in
    BOTH dicts. When both were built with the same tracked_elements
    list, every tracked element is present in both automatically (as a
    real group or a "not recovered" singleton), so nothing is excluded;
    without a tracked list, an element only one run happened to mention
    is excluded from this particular comparison.
    Returns (score, n_common) -- score is None when fewer than 2
    elements are shared (V-measure isn't meaningful with 0-1 items)."""
    common = sorted(set(labels_a) & set(labels_b))
    if len(common) < 2:
        return None, len(common)
    a_vec = [labels_a[e] for e in common]
    b_vec = [labels_b[e] for e in common]
    return v_measure_score(a_vec, b_vec), len(common)


def mechanism_reproducibility(run_names, run_labels):
    """run_names: list of run display names. run_labels: parallel list
    of element->label dicts (build_labels output), one per run.
    Returns {"pairs": [...], "average_v_measure": float or None,
    "n_valid_pairs": int} -- pairs is one row per run pair with its
    V-measure (None if too few shared elements) and shared-element
    count; average_v_measure is the mean over pairs that had a score
    (None if no pair qualified)."""
    pairs = []
    scores = []
    for i in range(len(run_names)):
        for j in range(i + 1, len(run_names)):
            score, n_common = pairwise_v_measure(run_labels[i], run_labels[j])
            pairs.append({
                "Run A": run_names[i],
                "Run B": run_names[j],
                "V-measure": round(score, 4) if score is not None else None,
                "Shared elements": n_common,
            })
            if score is not None:
                scores.append(score)
    average = sum(scores) / len(scores) if scores else None
    return {"pairs": pairs, "average_v_measure": average, "n_valid_pairs": len(scores)}
