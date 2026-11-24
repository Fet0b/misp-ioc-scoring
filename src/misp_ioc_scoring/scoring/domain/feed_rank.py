"""FeedRank with the creator organization (`orgc`) as proxy for the feed.

Limitation: MISP does not record the feed an attribute came from, so the
organization stands in for it. The value measures volume and pioneering, not quality.
"""
from dataclasses import dataclass

from .priority import minmax

PROXY_LIMITATION = ('Source usa a organização criadora (orgc) como proxy do feed, porque o MISP '
                    'não registra o feed de origem; mede volume e pioneirismo, não qualidade.')


@dataclass(frozen=True)
class OrganizationRank:
    first_pairs: int
    contribution: float
    pagerank: float
    pagerank_norm: float
    value: float
    source_norm: float


def qualifying(observation) -> bool:
    """Only active, published, `to_ids=true` observations with an organization count."""
    return (observation.removed_at is None and observation.to_ids is True
            and observation.published is True and observation.orgc_uuid is not None)


def first_publishers(observations) -> dict:
    """Pair `(type, value)` -> (first organization, organizations that published it)."""
    pairs = {}
    for observation in observations:
        if not qualifying(observation):
            continue
        key = (observation.misp_type, observation.normalized_value)
        order = (observation.source_created_at, str(observation.orgc_uuid))
        first, publishers = pairs.get(key, (None, set()))
        if first is None or order < first:
            first = order
        publishers.add(observation.orgc_uuid)
        pairs[key] = (first, publishers)
    return {key: (next(org for org in publishers if str(org) == first[1]), publishers)
            for key, (first, publishers) in pairs.items()}


def pagerank(nodes, edges, damping, iterations) -> dict:
    """Weighted PageRank; mass of nodes without out-edges is spread uniformly."""
    nodes = sorted(nodes, key=str)
    if not nodes:
        return {}
    count = len(nodes)
    out_weight = {node: 0.0 for node in nodes}
    for (source, _), weight in edges.items():
        out_weight[source] += weight
    rank = dict.fromkeys(nodes, 1 / count)
    for _ in range(iterations):
        dangling = sum(rank[node] for node in nodes if out_weight[node] == 0)
        following = {node: (1 - damping) / count + damping * dangling / count for node in nodes}
        for (source, target), weight in edges.items():
            following[target] += damping * rank[source] * weight / out_weight[source]
        rank = following
    return rank


def feed_rank(observations, parameters) -> dict:
    """Organization -> `OrganizationRank` (contribution, PageRank and Source value)."""
    pairs = first_publishers(observations)
    organizations = set()
    first_count = {}
    edges = {}
    for first, publishers in pairs.values():
        organizations.update(publishers)
        first_count[first] = first_count.get(first, 0) + 1
        for later in publishers:
            if later != first:
                edges[(later, first)] = edges.get((later, first), 0) + 1
    if not organizations:
        return {}
    ranks = pagerank(organizations, edges, parameters.damping, parameters.iterations)
    pagerank_norm, *_ = minmax(ranks)
    total = len(pairs)
    values = {org: parameters.contribution_weight * (first_count.get(org, 0) / total) * 100
              + parameters.pagerank_weight * pagerank_norm[org] for org in organizations}
    source_norm, *_ = minmax(values)
    return {org: OrganizationRank(first_count.get(org, 0), first_count.get(org, 0) / total, ranks[org],
                                  pagerank_norm[org], values[org], source_norm[org])
            for org in organizations}
