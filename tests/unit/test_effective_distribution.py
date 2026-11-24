import pytest

from tests.support.carioca import observation


@pytest.mark.parametrize('attribute,event,attribute_group,event_group,expected', [
    ('5', '3', None, None, ('3', None)),
    ('3', '1', None, None, ('1', None)),
    ('1', '3', None, None, ('1', None)),
    ('0', '3', None, None, ('0', None)),
    ('5', '4', None, '7', ('4', '7')),
    ('5', '4', None, None, ('0', None)),
    ('4', '1', '9', None, ('4', '9')),
    ('2', '4', None, '7', ('4', '7')),
    ('4', '4', '9', '7', ('0', None)),
    ('4', '4', '7', '7', ('4', '7')),
    ('x', '1', None, None, ('0', None)),
])
def test_effective_distribution(attribute, event, attribute_group, event_group, expected):
    item = observation('o', distribution=attribute, event_distribution=event, sharing_group_id=attribute_group)
    from dataclasses import replace
    assert replace(item, event_sharing_group_id=event_group).effective_distribution() == expected
