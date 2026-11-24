"""Shared pytest options.

`pytest_addoption` must live in an initial conftest; `tests/integration/conftest.py`
is not loaded early enough when pytest runs from the repository root.
"""


def pytest_addoption(parser):
    parser.addoption('--update-golden', action='store_true', default=False,
                     help='Rewrite golden files of characterization tests')
