"""Clean install runs 0000 → head in the session fixture; here: upgrade from 0007 with data."""
from pathlib import Path
from uuid import uuid4

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text

CONFIG = Config(str(Path(__file__).resolve().parents[2] / 'alembic.ini'))


def test_linear_history_up_to_0011():
    script = ScriptDirectory.from_config(CONFIG)
    assert script.get_current_head() == '0011'
    assert [r.revision for r in script.walk_revisions('base', 'head')][::-1] == [
        f'{n:04d}' for n in range(12)]


def test_upgrade_from_0007_preserves_blocking_and_pihole(engine):
    run, attribute = uuid4(), uuid4()
    command.downgrade(CONFIG, '0007')
    try:
        with engine.begin() as connection:
            assert not inspect(connection).has_table('execucao_scoring', schema='scoring')
            params = {'run': run, 'attribute': attribute}
            connection.execute(text(
                "INSERT INTO scoring.execucao_bloqueio VALUES (:run, now(), now(), 'default-v1', 'completed')"), params)
            connection.execute(text("""
                INSERT INTO scoring.decisao_bloqueio VALUES ('test', :attribute, 42, :run, 1, true, 'eligible',
                    now(), now() + interval '1 day', '{"kind": "domain"}')"""), params)
            connection.execute(text("""
                INSERT INTO sharing.pihole_entry VALUES ('https://pihole.example', 'kept.example',
                    'misp-ioc-scoring:abc', 7, 'confirmed', '[]')"""))
    finally:
        command.upgrade(CONFIG, 'head')
    with engine.begin() as connection:
        assert connection.execute(text(
            "SELECT block, reason, attribute_id FROM scoring.decisao_bloqueio WHERE attribute_uuid=:a"),
            {'a': attribute}).one() == (True, 'eligible', 42)
        assert connection.execute(text(
            "SELECT remote_id, status FROM sharing.pihole_entry WHERE hostname='kept.example'")).one() == (7, 'confirmed')
        columns = {c['name'] for c in inspect(connection).get_columns('observacao_origem', schema='collection')}
        assert 'event_sharing_group_id' in columns
        for table in ('execucao_scoring', 'resultado_score', 'candidato_rescoring'):
            assert inspect(connection).has_table(table, schema='scoring')
        assert inspect(connection).has_table('tentativa_compartilhamento', schema='sharing')
        connection.execute(text('TRUNCATE scoring.execucao_bloqueio CASCADE'))
        connection.execute(text('TRUNCATE sharing.pihole_entry'))
