"""Read-only Excel export configured exclusively through startup environment."""
import json
import os
from pathlib import Path
import sys
import tempfile
from datetime import datetime, timezone
from uuid import uuid4
from openpyxl import Workbook
from openpyxl.cell import WriteOnlyCell
from sqlalchemy import MetaData, Table, func, inspect, select, text

# Direct script execution also needs the repository root for tools.metrics.
if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from misp_ioc_scoring.shared.configuration import load_configuration
from misp_ioc_scoring.shared.database import engine_from_configuration
from misp_ioc_scoring.shared.errors import OperationalError
from misp_ioc_scoring.shared.logging import configure_logging
from tools.metrics.collection import collection_metrics

SCHEMAS = ('collection', 'scoring', 'sharing')


def _cell(sheet, value):
    if value is None:
        value = ''
    elif isinstance(value, datetime):
        value = value.isoformat()
    elif isinstance(value, (dict, list, tuple)):
        value = json.dumps(value, ensure_ascii=False, default=str)
    cell = WriteOnlyCell(sheet, value=str(value))
    # Force the cell type, including = + - @ and leading control characters.
    cell.data_type = 's'
    return cell


def write_workbook(output_dir, tables, row_limit, metrics):
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(directory, 0o700)
    descriptor, temporary = tempfile.mkstemp(dir=directory, suffix='.tmp')
    os.close(descriptor)
    path = directory / ('observability-' + uuid4().hex + '.xlsx')
    workbook = Workbook(write_only=True)
    try:
        names = set()
        for name, columns, rows, total in tables:
            # Excel sheet names are limited to 31 chars; use a stable suffix on collision.
            title = name[:31]
            if title in names:
                import hashlib
                title = name[:22] + '-' + hashlib.sha256(name.encode()).hexdigest()[:8]
            names.add(title)
            sheet = workbook.create_sheet(title)
            header = [_cell(sheet, c) for c in columns]
            if total > row_limit and header:
                from openpyxl.comments import Comment
                header[0].comment = Comment(f'TRUNCATED: {total} total rows; {row_limit} exported', 'observability')
            sheet.append(header)
            for index, row in enumerate(rows):
                if index >= row_limit:
                    break
                sheet.append([_cell(sheet, row.get(c)) for c in columns])
            if total > row_limit:
                # A comment on the header avoids exceeding Excel's row ceiling at the cap.
                if row_limit < 1048575:
                    sheet.append([_cell(sheet, f'TRUNCATED: {total} total rows; {row_limit} exported')])
                else:
                    # At the physical limit, the metrics sheet carries the explicit marker.
                    metrics.append((name + ':TRUNCATED', f'{total} total; {row_limit} exported'))
            sheet.close()
        sheet = workbook.create_sheet('Métricas')
        sheet.append([_cell(sheet, 'metric'), _cell(sheet, 'value')])
        for key, value in metrics:
            sheet.append([_cell(sheet, key), _cell(sheet, value)])
        workbook.save(temporary)
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
        return path
    except Exception:
        # Complete/close write-only generators before cleaning their temporary files.
        for sheet in workbook.worksheets:
            if not sheet.closed:
                sheet.close()
        workbook.close()
        Path(temporary).unlink(missing_ok=True)
        raise OperationalError('observability_export_failed') from None


def export(configuration):
    engine = engine_from_configuration(configuration)
    try:
        with engine.connect().execution_options(isolation_level='REPEATABLE READ') as connection:
            with connection.begin():
                connection.execute(text('SET TRANSACTION READ ONLY'))
                if connection.scalar(text('SELECT current_user')) != 'observer':
                    raise OperationalError('observability_requires_observer_role')
                inspector = inspect(connection)
                tables = []
                metrics = []
                reflected = {}
                for schema in SCHEMAS:
                    for name in sorted(inspector.get_table_names(schema=schema)):
                        table = Table(name, MetaData(), schema=schema, autoload_with=connection,
                                      resolve_fks=False)
                        reflected[schema + '.' + name] = table
                        columns = [c for c in table.columns if c.comment != 'secret']
                        count = connection.scalar(select(func.count()).select_from(table))
                        key = schema + '.' + name
                        metrics.append((key, count))
                        rows = connection.execute(select(*columns).execution_options(stream_results=True)).mappings()
                        tables.append((key, [c.name for c in columns], rows, count))
                metrics.extend(collection_metrics(connection, reflected))
                return write_workbook(configuration.export_output_dir, tables,
                                      configuration.export_max_rows_per_sheet, metrics)
    except OperationalError:
        raise
    except Exception:
        raise OperationalError('observability_export_failed') from None
    finally:
        engine.dispose()


def main():
    configure_logging()
    try:
        export(load_configuration('tools'))
    except OperationalError as error:
        import logging
        logging.getLogger(__name__).error('observability_export_failed', extra={
            'event': 'observability_export_failed', 'code': error.code})
        raise SystemExit(1) from None


if __name__ == '__main__':
    main()
