"""Pytest configuration for HiveFlow Core tests."""
import os
import sys

# Ensure packages/core is on path so `import hiveflow` resolves to hiveflow/
_core_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _core_dir not in sys.path:
    sys.path.insert(0, _core_dir)
