import sys
import os
import importlib
import importlib.util
import pytest

# Add HiveFlow Core directory to Python path first (so Agent can import from hiveflow)
# Try both the new name (hiveflow-core) and old name (HiveFlow Core)
_base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_core_dir = os.path.normpath(os.path.join(_base, '..', 'hiveflow-core'))
_old_core_dir = os.path.normpath(os.path.join(_base, '..', 'HiveFlow Core'))

# Check if new name exists, fall back to old name
if not os.path.exists(_core_dir) and os.path.exists(_old_core_dir):
    _core_dir = _old_core_dir

_core_dir = os.path.abspath(_core_dir)
if _core_dir not in sys.path:
    sys.path.insert(0, _core_dir)

# Register 'hiveflow' package from Core's __init__.py
core_init_path = os.path.join(_core_dir, "__init__.py")
if os.path.exists(core_init_path) and "hiveflow" not in sys.modules:
    core_spec = importlib.util.spec_from_file_location("hiveflow", core_init_path)
    core_pkg = importlib.util.module_from_spec(core_spec)
    core_pkg.__path__ = [_core_dir]
    sys.modules["hiveflow"] = core_pkg
    core_spec.loader.exec_module(core_pkg)

# Add HiveFlow Agent directory to Python path
_agent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _agent_dir not in sys.path:
    sys.path.insert(0, _agent_dir)


@pytest.fixture
def aioresponses():
    """Provide the aioresponses context manager as a pytest fixture."""
    from aioresponses import aioresponses as _aioresponses
    with _aioresponses() as mock:
        yield mock
