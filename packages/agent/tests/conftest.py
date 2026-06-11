import pytest

@pytest.fixture
def aioresponses():
    """Provide the aioresponses context manager as a pytest fixture."""
    from aioresponses import aioresponses as _aioresponses
    with _aioresponses() as mock:
        yield mock
