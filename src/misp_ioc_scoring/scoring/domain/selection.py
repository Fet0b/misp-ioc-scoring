"""Rank and top-N between IOCs of a run."""
from .aggregation import order_key


def ranked(winning, top_n):
    """[(evaluation, observations_evaluated, rank, in_top_n)] ordered by rank.

    The rank is dense and, with the aggregation tie-break, unique: exactly `top_n`
    IOCs are in the top-N even when priorities tie at the boundary.
    """
    ordered = sorted(winning.values(), key=lambda item: order_key(item[0]))
    return [(evaluation, count, position, position <= top_n)
            for position, (evaluation, count) in enumerate(ordered, start=1)]
