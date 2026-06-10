import sys
import os

# Add HiveFlow Core directory to Python path so modules can be imported directly
_core_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _core_dir not in sys.path:
    sys.path.insert(0, _core_dir)

# Now import hiveflow.__init__ to register all exports
import importlib
import importlib.util

# Force load the __init__.py as 'hiveflow' package
init_path = os.path.join(_core_dir, "__init__.py")
spec = importlib.util.spec_from_file_location("hiveflow", init_path)
hiveflow_pkg = importlib.util.module_from_spec(spec)
sys.modules["hiveflow"] = hiveflow_pkg

# Set the package path so sub-module imports work
hiveflow_pkg.__path__ = [_core_dir]

# Execute the __init__.py to register all exports
spec.loader.exec_module(hiveflow_pkg)

# Also register sub-modules with the hiveflow prefix for relative imports
for mod_file in os.listdir(_core_dir):
    if mod_file.endswith(".py") and mod_file not in ("__init__.py",):
        mod_name = mod_file[:-3]
        mod_path = os.path.join(_core_dir, mod_file)
        sub_spec = importlib.util.spec_from_file_location(f"hiveflow.{mod_name}", mod_path)
        sub_mod = importlib.util.module_from_spec(sub_spec)
        sys.modules[f"hiveflow.{mod_name}"] = sub_mod
        sub_spec.loader.exec_module(sub_mod)
