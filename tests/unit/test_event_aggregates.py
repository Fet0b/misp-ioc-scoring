from types import SimpleNamespace
from misp_ioc_scoring.collection.domain.event_aggregates import category_counts


def test_active_categories_only():
    observations = [SimpleNamespace(category='Network activity', removed_at=None),
                    SimpleNamespace(category='Network activity', removed_at=True)]
    counts = category_counts(observations)
    assert len(counts) == 16
    assert counts['Network activity'] == 1
