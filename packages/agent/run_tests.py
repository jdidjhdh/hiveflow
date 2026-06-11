"""
Helper script to run Agent tests with correct Python path.
"""
import sys
import os
import subprocess

# Get the agent package root
_here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _here)

# Add Core's hiveflow package
_core = os.path.normpath(os.path.join(_here, '..', 'core', 'hiveflow'))
if os.path.isdir(_core):
    sys.path.insert(0, _core)

if __name__ == "__main__":
    # Re-run pytest with the same arguments
    import pytest
    sys.exit(pytest.main(sys.argv[1:]))
