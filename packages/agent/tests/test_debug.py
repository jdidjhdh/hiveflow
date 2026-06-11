"""
Minimal test to debug sys.path during pytest collection
"""
import sys

def test_debug_syspath():
    """Print sys.path during test execution"""
    print("\n=== sys.path during test ===")
    for i, p in enumerate(sys.path):
        print(f"  {i}: {p}")
    
    # Try to find app
    import importlib.util
    spec = importlib.util.find_spec('app')
    print(f"\napp found at: {spec.origin if spec else 'NOT FOUND'}")
    
    # Try to find hiveflow
    spec2 = importlib.util.find_spec('hiveflow')
    print(f"hiveflow found at: {spec2.origin if spec2 else 'NOT FOUND'}")
