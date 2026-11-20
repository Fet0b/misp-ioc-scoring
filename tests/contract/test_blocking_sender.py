from uuid import uuid4

import pytest

from misp_ioc_scoring.scoring.api import blocking_decision


class Result:
    def __init__(self, rows):
        self.rows = rows

    def mappings(self):
        return self

    def fetchmany(self, size):
        return self.rows[:size]


@pytest.mark.parametrize("field,identifier", [("attribute_uuid", uuid4()), ("attribute_id", 42)])
def test_sender_queries_effective_view_with_origin_and_bound_identifier(field, identifier):
    row = dict(block=False, reason="indeterminate", attribute_id=None)

    class Session:
        def execute(self, query, parameters):
            assert "scoring.decisao_bloqueio_efetiva" in str(query)
            assert f"source_instance_id=:source AND {field}=:identifier" in str(query)
            assert parameters == {"source": "peer", "identifier": identifier}
            return Result([row])

    assert blocking_decision(Session(), "peer", **{field: identifier}) == row


def test_unknown_and_ambiguous_local_id():
    class Session:
        def __init__(self, rows):
            self.rows = rows

        def execute(self, query, parameters):
            return Result(self.rows)

    assert blocking_decision(Session([]), "peer", attribute_id=42) is None
    with pytest.raises(ValueError, match="Ambiguous"):
        blocking_decision(Session([{}, {}]), "peer", attribute_id=42)
