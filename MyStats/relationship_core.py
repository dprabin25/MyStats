"""
Relationship-set parsing + Jaccard/Dice agreement computation for the
"Relationship Agreement" MyStats tool.

This tool exists for a specific kind of data the Reproducibility
(V-measure) tool handles badly: narratives that report individual
pairwise relationships ("IL-1beta increases MMP-8", "Lactobacillus
rhamnosus reduces IL-1beta") rather than a clean partition of elements
into mutually-exclusive clusters. V-measure requires each run to reduce
to a strict partition, so its Groups input gets fed through union-find:
any two elements connected -- even transitively, through a chain of
unrelated pairwise claims sharing one element -- end up merged into one
cluster. A single hub element mentioned in several separate, otherwise-
unrelated relationships (a cytokine the literature connects to five
different things that aren't connected to EACH OTHER) is exactly the
case that breaks under that assumption: it silently drags every partner
into one supercluster, regardless of whether the narrative ever claimed
those partners belonged together.

This module sidesteps that by never building a partition at all. Each
run's relationships are kept as a SET OF EDGES (unordered element pairs)
and compared directly -- Jaccard/Dice similarity of the edge sets. No
transitive closure, no forced clustering: a relationship agrees or
disagrees on its own, independent of what else either run reported.

Kept separate from the Streamlit UI so it's testable without launching
the app.
"""


def edge_key(a, b):
    """Canonical, order-independent identity for a reported relationship
    between two elements -- "A relates to B" and "B relates to A" are
    the same reported relationship, not two. Returns a frozenset (usable
    directly as a set/dict element), or None for an incomplete or
    self-referential row (an element can't be reported as relating to
    itself; that's not a relationship)."""
    a = (a or "").strip()
    b = (b or "").strip()
    if not a or not b or a == b:
        return None
    return frozenset({a, b})


def parse_relationship_rows(rows):
    """rows: an iterable of (element_a, element_b) pairs (or anything
    with that shape -- tuples, 2-item lists), typically the app's
    per-run relationship rows. Returns a set of edge_key() results,
    silently dropping incomplete/self-referential rows and de-duplicating
    a relationship restated more than once (a narrative saying the same
    thing twice is one relationship, not two -- matching the citation
    tool's "a narrative either cites something or doesn't" convention)."""
    edges = set()
    for row in rows:
        a, b = row[0], row[1]
        key = edge_key(a, b)
        if key is not None:
            edges.add(key)
    return edges


def jaccard(set_a, set_b):
    """|A intersect B| / |A union B|. Returns None when both sets are
    empty -- "neither run reported any relationships" is not the same
    claim as "these runs completely disagree" (which would be 0.0), so
    it's left undefined rather than silently reported as either extreme."""
    union = set_a | set_b
    if not union:
        return None
    return len(set_a & set_b) / len(union)


def dice(set_a, set_b):
    """2*|A intersect B| / (|A|+|B|) -- the Sorensen-Dice coefficient.
    Always >= Jaccard for the same two sets (it weights partial overlap
    a bit more generously), which is why both are offered side by side
    rather than picking just one -- they rarely disagree by much, and
    showing both makes it obvious when they do (a sign the two run's
    relationship counts differ a lot, which either number alone would
    hide). Same empty-both-sets handling as jaccard()."""
    total = len(set_a) + len(set_b)
    if total == 0:
        return None
    return 2 * len(set_a & set_b) / total


def pairwise_relationship_agreement(run_names, run_edge_sets):
    """run_names: list of run display names. run_edge_sets: parallel list
    of edge sets (parse_relationship_rows output), one per run. Returns
    {"pairs": [...], "average_jaccard": float or None, "n_valid_pairs":
    int} -- pairs is one row per run pair with Jaccard, Dice, how many
    relationships they share vs. the total distinct relationships either
    one reported, and each side's own count (so a pair where one run
    reported 20 relationships and the other reported 2 doesn't look the
    same as two runs of similar size); average_jaccard is the mean over
    pairs that had a defined score (both empty is excluded, matching
    jaccard()'s own None-when-undefined convention)."""
    pairs = []
    scores = []
    for i in range(len(run_names)):
        for j in range(i + 1, len(run_names)):
            a, b = run_edge_sets[i], run_edge_sets[j]
            j_score = jaccard(a, b)
            d_score = dice(a, b)
            pairs.append({
                "Run A": run_names[i],
                "Run B": run_names[j],
                "Jaccard": round(j_score, 4) if j_score is not None else None,
                "Dice": round(d_score, 4) if d_score is not None else None,
                "Shared relationships": len(a & b),
                "Total distinct relationships": len(a | b),
                "Run A relationships": len(a),
                "Run B relationships": len(b),
            })
            if j_score is not None:
                scores.append(j_score)
    average = sum(scores) / len(scores) if scores else None
    return {"pairs": pairs, "average_jaccard": average, "n_valid_pairs": len(scores)}


def build_relationship_table(run_names, run_edge_sets):
    """One row per distinct relationship across ALL runs (no duplicates):
    {"Element A": a, "Element B": b, <run name>: "Yes"/"No", ...,
    "Runs reporting": n}. "Element A"/"Element B" here are just the pair
    sorted alphabetically for stable, readable display -- the underlying
    relationship is undirected, matching edge_key(). Sorted by how many
    runs reported it (descending), then alphabetically, so the most
    broadly-agreed-on relationships surface first."""
    all_edges = set()
    for edges in run_edge_sets:
        all_edges |= edges

    rows = []
    for edge in all_edges:
        a, b = sorted(edge)
        row = {"Element A": a, "Element B": b}
        count = 0
        for name, edges in zip(run_names, run_edge_sets):
            hit = edge in edges
            row[name] = "Yes" if hit else "No"
            count += 1 if hit else 0
        row["Runs reporting"] = count
        rows.append(row)

    rows.sort(key=lambda r: (-r["Runs reporting"], r["Element A"], r["Element B"]))
    return rows
