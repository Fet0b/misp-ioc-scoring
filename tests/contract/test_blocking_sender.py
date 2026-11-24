from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

import pytest

from misp_ioc_scoring.scoring.api import blocking_decision


class Result:
    def __init__(self, rows):
        self.rows = rows

    def fetchmany(self, size):
        return self.rows[:size]


@pytest.mark.parametrize("field,identifier", [("attribute_uuid", uuid4()), ("attribute_id", 42)])
def test_sender_queries_effective_view_with_origin_and_bound_identifier(field, identifier):
    now = datetime(2026, 11, 24, tzinfo=timezone.utc)
    row = SimpleNamespace(source_instance_id="peer", attribute_uuid=uuid4(), attribute_id=None, block=False,
                          reason="indeterminate", as_of=now, expires_at=now, rule_version="default-v1")

    class Session:
        def execute(self, query, parameters):
            assert "scoring.decisao_bloqueio_efetiva" in str(query)
            assert f"source_instance_id=:source AND {field}=:identifier" in str(query)
            assert parameters == {"source": "peer", "identifier": identifier}
            return Result([row])

    decision = blocking_decision(Session(), "peer", **{field: identifier})
    assert (decision.block, decision.reason, decision.attribute_id) == (False, "indeterminate", None)


def test_unknown_and_ambiguous_local_id():
    class Session:
        def __init__(self, rows):
            self.rows = rows

        def execute(self, query, parameters):
            return Result(self.rows)

    assert blocking_decision(Session([]), "peer", attribute_id=42) is None
    with pytest.raises(ValueError, match="Ambiguous"):
        blocking_decision(Session([object(), object()]), "peer", attribute_id=42)
