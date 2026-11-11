import importlib
import pkgutil
import re
import misp_ioc_scoring
from misp_ioc_scoring.shared.database import Base


def test_table_ownership_and_secret_comments():
    for module in pkgutil.walk_packages(misp_ioc_scoring.__path__, misp_ioc_scoring.__name__ + '.'):
        if '.infrastructure.persistence' in module.name:
            importlib.import_module(module.name)
    for mapper in Base.registry.mappers:
        module = mapper.class_.__module__.split('.')[1]
        assert mapper.local_table.schema == module
        for column in mapper.local_table.columns:
            if re.search('credential|secret|token|password', column.name, re.I):
                assert column.comment == 'secret'
