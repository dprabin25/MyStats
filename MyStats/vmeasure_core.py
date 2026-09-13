"""
V-measure (Rosenberg & Hirschberg, 2007) computation, kept dependency-free
(no scikit-learn) so it's testable and deployable without adding a new
requirement -- matches the same math scikit-learn's
`v_measure_score`/`homogeneity_completeness_v_measure` use, verified
against it directly (see the module's test suite in
verify_vmeasure.py-style checks run during development).

V-measure scores how well two partitions of the SAME set of items agree,
with no need for either one to be "ground truth" -- it's the harmonic
mean of homogeneity (every group in A contains only items B also
grouped together) and completeness (everything B grouped together, A
also grouped together). Because it's a harmonic mean of a quantity and
its mirror image, swapping which partition is "A" and which is "B"
leaves the V-measure itself unchanged, which is what makes it usable as
a symmetric agreement score between two independent runs rather than a
prediction-vs-truth score.
"""

import math
from collections import Counter


def _entropy(labels):
    """Shannon entropy (natural log) of a label sequence."""
    n = len(labels)
    if n == 0:
        return 0.0
    counts = Counter(labels)
    h = 0.0
    for c in counts.values():
        p = c / n
        h -= p * math.log(p)
    return h


def _conditional_entropy(labels_a, labels_b):
    """H(A | B): the entropy remaining in partition A once partition B's
    group for each item is known."""
    n = len(labels_a)
    if n == 0:
        return 0.0
    joint = Counter(zip(labels_a, labels_b))
    b_counts = Counter(labels_b)
    h = 0.0
    for (a, b), n_ab in joint.items():
        h -= (n_ab / n) * math.log(n_ab / b_counts[b])
    return h


def homogeneity_completeness_v_measure(labels_a, labels_b, beta=1.0):
    """labels_a, labels_b: two equal-length sequences giving each item's
    group id under partition A and partition B respectively (item i's
    group under A is labels_a[i], under B is labels_b[i]). Returns
    (homogeneity, completeness, v_measure).

    homogeneity = 1 - H(A|B)/H(A)  (undefined/trivially 1 if H(A) == 0,
        i.e. A has only one group)
    completeness = 1 - H(B|A)/H(B) (trivially 1 if H(B) == 0)
    v_measure = (1+beta) * h * c / (beta*h + c), the weighted harmonic
        mean of homogeneity and completeness (beta=1 -> unweighted, the
        standard V-measure)."""
    n = len(labels_a)
    if n != len(labels_b):
        raise ValueError("labels_a and labels_b must be the same length")
    if n == 0:
        return 1.0, 1.0, 1.0

    h_a = _entropy(labels_a)
    h_b = _entropy(labels_b)
    h_a_given_b = _conditional_entropy(labels_a, labels_b)
    h_b_given_a = _conditional_entropy(labels_b, labels_a)

    homogeneity = 1.0 if h_a == 0.0 else 1.0 - h_a_given_b / h_a
    completeness = 1.0 if h_b == 0.0 else 1.0 - h_b_given_a / h_b

    if homogeneity + completeness == 0.0:
        v_measure = 0.0
    else:
        v_measure = (1 + beta) * homogeneity * completeness / (beta * homogeneity + completeness)
    return homogeneity, completeness, v_measure


def v_measure_score(labels_a, labels_b, beta=1.0):
    return homogeneity_completeness_v_measure(labels_a, labels_b, beta=beta)[2]
