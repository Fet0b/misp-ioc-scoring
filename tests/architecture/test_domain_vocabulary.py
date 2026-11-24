"""SC-009: operator messages and docstrings avoid the synonyms listed in the glossary."""
import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GLOSSARY = ROOT / 'docs' / 'domain-glossary.md'
SOURCE = ROOT / 'src' / 'misp_ioc_scoring'
# "feed" names the real MISP feed that FeedRank stands in for, not a collection endpoint.
ALLOWED = {('scoring/domain/feed_rank.py', 'feed')}


def synonyms():
    found = set()
    for line in GLOSSARY.read_text().splitlines():
        if line.startswith('| ') and not line.startswith('| Termo'):
            last = line.strip().strip('|').split(' | ')[-1]
            found.update(item.strip() for item in last.split(',') if item.strip())
    return found


def texts(tree):
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if docstring := ast.get_docstring(node):
                yield docstring
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            yield node.value


def test_no_avoided_synonyms():
    words = synonyms()
    assert {'pontuação', 'blacklist', 'servidor'} <= words
    problems = []
    for path in SOURCE.rglob('*.py'):
        relative = path.relative_to(SOURCE).as_posix()
        for text in texts(ast.parse(path.read_text())):
            for word in words:
                if (relative, word) not in ALLOWED and re.search(rf'(?<!\w){re.escape(word)}(?!\w)', text, re.I):
                    problems.append(f'{relative}: "{word}"')
    assert not problems, sorted(set(problems))
