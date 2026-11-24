"""FeedRank (orgc proxy) on a three-organization graph computed by hand.

Pairs: p1 A first, B later; p2 A first, C later; p3 B first, C later; p4 only C.
Edges (later -> earlier, weight = pairs in common): B->A 1, C->A 1, C->B 1; A has no
out-edge (mass spread uniformly). With d = 0.85 and N = 3 the fixed point is
PR_C = 0.05 + 0.85·PR_A/3, PR_B = PR_C + 0.425·PR_C·... solved: PR_A = 0.87875/1.687083,
PR_C = 0.05 + 0.283333·PR_A, PR_B = 0.07125 + 0.40375·PR_A.
Contributions: A 2/4, B 1/4, C 1/4. V = 50·c·100 + 50·MinMax(PR).
"""
import pytest

from misp_ioc_scoring.scoring.domain.carioca_configuration import FeedRankParameters
from misp_ioc_scoring.scoring.domain.feed_rank import feed_rank, first_publishers, pagerank
from tests.support.carioca import observation, uid

PARAMETERS = FeedRankParameters('orgc-proxy', 0.85, 50, 'uniform', 50, 50)
A, B, C = uid('org:A'), uid('org:B'), uid('org:C')


def graph():
    return [
        observation('p1a', 'p1.org', org='A', created_days=30), observation('p1b', 'p1.org', org='B', created_days=20),
        observation('p2a', 'p2.org', org='A', created_days=30), observation('p2c', 'p2.org', org='C', created_days=10),
        observation('p3b', 'p3.org', org='B', created_days=30), observation('p3c', 'p3.org', org='C', created_days=10),
        observation('p4c', 'p4.org', org='C', created_days=10),
        observation('x1', 'p4.org', org='A', created_days=90, published=False),
        observation('x2', 'p4.org', org='B', created_days=90, to_ids=False),
        observation('x3', 'p4.org', org='B', created_days=90, removed=True),
    ]


def test_three_organizations_by_hand():
    ranks = feed_rank(graph(), PARAMETERS)
    pr_a = 0.87875 / 1.6870833
    expected = {A: pr_a, B: 0.07125 + 0.40375 * pr_a, C: 0.05 + 0.2833333 * pr_a}
    for org, value in expected.items():
        assert ranks[org].pagerank == pytest.approx(value, abs=5e-4)
    assert sum(r.pagerank for r in ranks.values()) == pytest.approx(1)
    assert (ranks[A].first_pairs, ranks[B].first_pairs, ranks[C].first_pairs) == (2, 1, 1)
    assert ranks[A].contribution == 0.5 and ranks[C].contribution == 0.25
    assert ranks[A].pagerank_norm == 100 and ranks[C].pagerank_norm == 0
    assert ranks[B].pagerank_norm == pytest.approx(25.97, abs=0.1)
    assert ranks[A].value == pytest.approx(7500, abs=1)
    assert ranks[C].value == pytest.approx(1250, abs=1)
    assert ranks[A].source_norm == 100 and ranks[C].source_norm == 0
    assert ranks[B].source_norm == pytest.approx(20.78, abs=0.1)


def test_tie_break_by_creation_then_organization_and_filters():
    tie = [observation('t1', 'tie.org', org='B', created_days=5), observation('t2', 'tie.org', org='A', created_days=5)]
    first, publishers = first_publishers(tie)[('domain', 'tie.org')]
    assert first == min((A, B), key=str) and publishers == {A, B}
    assert first_publishers([observation('u', 'u.org', published=False), observation('v', 'v.org', to_ids=False)]) == {}


def test_pagerank_uniform_dangling_and_empty():
    ranks = pagerank({'x', 'y'}, {}, 0.85, 50)
    assert ranks == {'x': pytest.approx(0.5), 'y': pytest.approx(0.5)}
    assert pagerank(set(), {}, 0.85, 50) == {}
    assert feed_rank([], PARAMETERS) == {}
