"""
Root conftest for HiveFlow Agent tests.
Ensures the Agent package root is on sys.path so that imports like
`from core.xxx`, `from app`, `from memory.xxx` work correctly.

The Core `hiveflow` package is importable via the editable install,
so we do NOT need to add it here.
"""
import sys
import os

_here = os.path.dirname(os.path.abspath(__file__))
if _here not in sys.path:
    sys.path.insert(0, _here)
