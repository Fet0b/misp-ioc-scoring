"""Import contracts plus explicit checks for the only public cross-module surface."""
import ast
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]


def test_import_linter():
    result = subprocess.run([str(Path(sys.executable).parent / 'lint-imports')],
                            cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr


def test_cross_module_access_only_through_api():
    root = ROOT / 'src' / 'misp_ioc_scoring'
    for path in root.rglob('*.py'):
        owner = path.relative_to(root).parts[0]
        if owner not in {'collection', 'scoring', 'sharing'}:
            continue
        package = ('misp_ioc_scoring', *path.relative_to(root).parts[:-1])
        for node in ast.walk(ast.parse(path.read_text())):
            names = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            if isinstance(node, ast.ImportFrom):
                base = '.'.join(package[:len(package) - node.level + 1]) if node.level else ''
                target = '.'.join(filter(None, [base, node.module]))
                names = [target + '.' + alias.name for alias in node.names]
            for name in names:
                parts = name.split('.')
                if len(parts) < 2 or parts[0] != 'misp_ioc_scoring':
                    continue
                if parts[1] in {'collection', 'scoring', 'sharing'} and parts[1] != owner:
                    assert len(parts) > 2 and parts[2] == 'api', f'{path}: {name}'
