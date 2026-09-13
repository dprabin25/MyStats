"""
Cohen's Kappa computation + pair/graph parsing for the "Inter-rater
Agreement (Cohen's Kappa)" MyStats tool. Kept separate from the
Streamlit UI so it's testable without launching the app.

The raw input per rater is a list of rows in the shape the user
actually works with -- "Element A / Element B" -- where a row is
either an edge (both sides named: these two elements go together) or a
declared non-pairing (Element B is "No pair": this element isn't
paired with anything). Chains of edges transitively merge into bigger
groups (A-B and B-C means A, B, C are all one group), exactly like the
reproducibility tool's Groups -- this is just a different, row-at-a-
time way of specifying the same kind of thing: which elements a rater
thinks belong together.

Cohen's Kappa itself needs a fixed set of "items" both raters classify
into the same categories. The item chosen here is EVERY unique pair of
elements across the whole observed universe (every element either
rater mentioned), and the category is binary: did this rater group
these two elements together, or not. This is the standard way to turn
a clustering/grouping judgment into something Kappa can score, and
unlike raw percent agreement, Kappa corrects for chance -- so it
doesn't reward the trivial "we both say these two random elements
aren't paired" the way an uncorrected agreement rate would.
"""

import re

_NO_PAIR = "No pair"


def parse_rows_from_lines(text):
    """Convenience parser for a pasted 'Element A <sep> Element B' block
    (tab, comma, or ' - ' separated), one row per line -- an alternative
    to building rows through the UI. Returns a list of (a, b) tuples,
    b possibly being the literal string "No pair" (any case)."""
    rows = []
    if not isinstance(text, str):
        return rows
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = re.split(r"\t|,| - ", line, maxsplit=1)
        if len(parts) != 2:
            continue
        a, b = parts[0].strip(), parts[1].strip()
        if a:
            rows.append((a, b if b else _NO_PAIR))
    return rows


class _UnionFind:
    def __init__(self, items):
        self.parent = {x: x for x in items}

    def find(self, x):
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, x, y):
        rx, ry = self.find(x), self.find(y)
        if rx != ry:
            self.parent[rx] = ry


def build_labels_from_rows(rows, universe):
    """rows: list of (element_a, element_b) for ONE rater, element_b
    being "No pair" (any case) for a declared singleton. universe: the
    full set of elements to label (typically every element ANY rater
    mentioned -- see module docstring). Returns element -> label dict
    covering every element in `universe`:
    - Two elements connected by an edge (directly, or transitively
      through a chain of edges) get the same label.
    - An element this rater explicitly calls "No pair", or never
      mentions at all, gets its own singleton label -- both cases mean
      "this rater doesn't group it with anything," which is exactly
      what matters for the same-group comparison; nothing else
      distinguishes "explicitly alone" from "never brought up" here on
      purpose (parallel to the reproducibility tool's Unpaired vs.
      Unrecovered, which likewise both resolve to "not grouped")."""
    uf = _UnionFind(universe)
    for a, b in rows:
        if a in uf.parent and b in uf.parent and str(b).strip().lower() != _NO_PAIR.lower():
            uf.union(a, b)
    return {e: uf.find(e) for e in universe}


def elements_used(rows):
    """Every element mentioned in `rows` -- as Element A always, and as
    Element B whenever it's a real element rather than "No pair"."""
    used = set()
    for a, b in rows:
        if a:
            used.add(a)
        if b and str(b).strip().lower() != _NO_PAIR.lower():
            used.add(b)
    return used


def pairwise_same_group(labels, universe):
    """labels: element -> label dict (build_labels_from_rows output).
    universe: ordered element list. Returns a dict {(x, y): 0/1} for
    every unordered pair x < y (by universe order) -- 1 if this rater
    grouped them together, 0 otherwise."""
    result = {}
    n = len(universe)
    for i in range(n):
        for j in range(i + 1, n):
            x, y = universe[i], universe[j]
            result[(x, y)] = 1 if labels[x] == labels[y] else 0
    return result


def cohens_kappa(a_values, b_values):
    """a_values, b_values: two equal-length sequences of category
    labels for the SAME items (any hashable type -- ints, strings,
    bools all work, since only equality between values matters).
    Returns (kappa, po, pe):
    - po: observed agreement -- fraction of items where a_values[i]
      == b_values[i].
    - pe: expected agreement by chance -- sum over every category c of
      (fraction of items rater A assigned c) * (fraction rater B
      assigned c), i.e. the agreement rate two raters using each
      other's marginal category frequencies would produce by chance
      alone.
    - kappa: (po - pe) / (1 - pe), the chance-corrected agreement.
      Returns 1.0 when po == pe == 1 (both raters used only one,
      shared category -- perfect and trivially certain), 0.0 when
      pe == 1 but po < 1 (impossible in practice, guarded anyway)."""
    n = len(a_values)
    if n != len(b_values):
        raise ValueError("a_values and b_values must be the same length")
    if n == 0:
        return 1.0, 1.0, 1.0

    po = sum(1 for a, b in zip(a_values, b_values) if a == b) / n

    from collections import Counter
    a_counts = Counter(a_values)
    b_counts = Counter(b_values)
    categories = set(a_counts) | set(b_counts)
    pe = sum((a_counts.get(c, 0) / n) * (b_counts.get(c, 0) / n) for c in categories)

    if pe >= 1.0:
        kappa = 1.0 if po >= 1.0 else 0.0
    else:
        kappa = (po - pe) / (1 - pe)
    return kappa, po, pe


def kappa_interpretation(kappa):
    """Standard Landis & Koch (1977) benchmark bands -- the conventional
    way Cohen's Kappa is reported in the literature."""
    if kappa is None:
        return "N/A"
    if kappa < 0:
        return "Poor (< 0)"
    if kappa <= 0.20:
        return "Slight"
    if kappa <= 0.40:
        return "Fair"
    if kappa <= 0.60:
        return "Moderate"
    if kappa <= 0.80:
        return "Substantial"
    return "Almost perfect"


def pairwise_kappa_for_raters(labels_by_rater, universe):
    """labels_by_rater: list of element -> label dicts, one per rater
    (build_labels_from_rows output, all built against the same
    `universe`). Returns {"pairs": [...], "average_kappa": float or
    None} -- pairs is one row per rater pair with kappa, po, pe, the
    interpretation band, and the 2x2 contingency counts (both graders
    agreeing paired / both agreeing not-paired / disagreeing each way);
    average_kappa is the simple mean over all rater pairs (matches the
    reproducibility tool's "simple pairwise average" convention for
    combining more than two raters)."""
    n_raters = len(labels_by_rater)
    pairs_out = []
    kappas = []
    for i in range(n_raters):
        for j in range(i + 1, n_raters):
            same_i = pairwise_same_group(labels_by_rater[i], universe)
            same_j = pairwise_same_group(labels_by_rater[j], universe)
            item_pairs = list(same_i.keys())
            a_vals = [same_i[p] for p in item_pairs]
            b_vals = [same_j[p] for p in item_pairs]
            kappa, po, pe = cohens_kappa(a_vals, b_vals)

            both_paired = sum(1 for a, b in zip(a_vals, b_vals) if a == 1 and b == 1)
            both_not = sum(1 for a, b in zip(a_vals, b_vals) if a == 0 and b == 0)
            only_i = sum(1 for a, b in zip(a_vals, b_vals) if a == 1 and b == 0)
            only_j = sum(1 for a, b in zip(a_vals, b_vals) if a == 0 and b == 1)

            pairs_out.append({
                "Rater A": i, "Rater B": j,
                "Kappa": round(kappa, 4),
                "Interpretation": kappa_interpretation(kappa),
                "Observed agreement": round(po, 4),
                "Expected agreement (chance)": round(pe, 4),
                "Both: paired": both_paired,
                "Both: not paired": both_not,
                "Only Rater A: paired": only_i,
                "Only Rater B: paired": only_j,
                "Element pairs compared": len(item_pairs),
            })
            kappas.append(kappa)
    average = sum(kappas) / len(kappas) if kappas else None
    return {"pairs": pairs_out, "average_kappa": average}


def build_group_table(labels, universe):
    """labels: element -> label dict for one rater. Returns a list of
    rows {"Element": e, "Group": g} where g is either "Singleton" or a
    stable "Group N" name (assigned in the order each new group's first
    element appears in `universe`) -- purely a human-readable summary
    of what the rater's edges resolved to, so the tool's interpretation
    of a rater's rows can be sanity-checked before trusting the kappa
    score built on top of it."""
    group_names = {}
    rows = []
    for e in universe:
        root = labels[e]
        members = [x for x in universe if labels[x] == root]
        if len(members) == 1:
            rows.append({"Element": e, "Group": "Singleton"})
        else:
            if root not in group_names:
                group_names[root] = f"Group {len(group_names) + 1}"
            rows.append({"Element": e, "Group": group_names[root]})
    return rows
