from dataclasses import replace
from datetime import timedelta

from misp_ioc_scoring.scoring.domain.aggregation import ObservationEvaluation, winners
from misp_ioc_scoring.scoring.domain.selection import ranked
from tests.support.carioca import AS_OF, uid


def evaluation(ioc, name, priority, created_days=0, source='s1'):
    return ObservationEvaluation(
        ioc_id=uid(ioc), source_instance_id=source, attribute_uuid=uid(name), event_uuid=uid('e'),
        orgc_uuid=uid('o'), source_created_at=AS_OF - timedelta(days=created_days), decay_group='domain',
        age_days=1, attribute_raw=1, attribute_norm=1, threat_level=0, analysis=0, cade_raw=0, cade_norm=0,
        event_raw=0, event_norm=0, source_value=0, source_norm=0, priority=priority)


def test_winning_observation_and_tie_break():
    low, high = evaluation('i', 'a', 40), evaluation('i', 'b', 70)
    older, newer = evaluation('j', 'c', 50, created_days=10), evaluation('j', 'd', 50, created_days=1)
    first_source = evaluation('k', 'e', 50, source='a')
    second_source = replace(evaluation('k', 'e', 50), source_instance_id='b')
    result = winners([low, high, newer, older, second_source, first_source])
    assert result[uid('i')] == (high, 2)
    assert result[uid('j')] == (older, 2)
    assert result[uid('k')] == (first_source, 2)


def test_dense_rank_and_exact_top_n():
    items = [evaluation(f'i{n}', f'a{n}', p, created_days=n) for n, p in enumerate([90, 80, 80, 80, 10])]
    rows = ranked(winners(items), 2)
    assert [rank for *_, rank, _ in rows] == [1, 2, 3, 4, 5]
    assert [top for *_, top in rows] == [True, True, False, False, False]
    assert rows[1][0].attribute_uuid == uid('a3')  # oldest wins the tie at the boundary
    assert all(top for *_, top in ranked(winners(items), 50))
