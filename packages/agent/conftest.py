import sys
import os
import importlib
import importlib.util

# Add HiveFlow Core directory to Python path first
_core_dir = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'HiveFlow Core'))
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
_agent_dir = os.path.dirname(os.path.abspath(__file__))
if _agent_dir not in sys.path:
    sys.path.insert(0, _agent_dir)
