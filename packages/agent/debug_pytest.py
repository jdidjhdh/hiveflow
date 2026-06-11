# debug_pytest.py
"""
Debug what pytest does with sys.path
"""
import sys
import os

print("=== BEFORE hiveflow import ===")
print(f"sys.path: {[p for p in sys.path]}")

# Import hiveflow first (simulating what the test does)
import hiveflow

print("\n=== AFTER hiveflow import ===")
print(f"sys.path: {[p for p in sys.path]}")

# Clear cached modules
for key in list(sys.modules.keys()):
    if key in ('app', 'orchestrator'):
        del sys.modules[key]

# Now try to import app
import app
print(f"\napp resolved to: {app.__file__}")

import orchestrator
print(f"orchestrator resolved to: {orchestrator.__file__}")
