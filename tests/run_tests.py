"""
tests/run_tests.py

Test runner script for Agentic Cinema tests.
"""
from __future__ import annotations

import os
import subprocess
import sys


def run_pytest():
    """Run pytest with coverage."""
    print("=" * 60)
    print("Running Pytest with Coverage")
    print("=" * 60)
    
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-v", "--cov=.", "--cov-report=term-missing", "--cov-report=html"],
        cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    )
    return result.returncode


def run_unit_tests():
    """Run individual unit test files."""
    print("=" * 60)
    print("Running Individual Unit Tests")
    print("=" * 60)
    
    test_files = [
        "tests/test_entities_schema.py",
        "tests/test_gatekeeper.py",
        "tests/test_deterministic_grounding.py",
        "tests/test_schema_precision.py",
        "tests/test_edge_cases_extraction.py",
    ]
    
    results = []
    for test_file in test_files:
        print(f"\nRunning {test_file}...")
        result = subprocess.run([sys.executable, test_file])
        results.append(result.returncode == 0)
    
    return all(results)


def run_integration_tests():
    """Run integration tests."""
    print("=" * 60)
    print("Running Integration Tests")
    print("=" * 60)
    
    test_files = [
        "tests/test_integration_pipeline.py",
    ]
    
    results = []
    for test_file in test_files:
        print(f"\nRunning {test_file}...")
        result = subprocess.run([sys.executable, test_file])
        results.append(result.returncode == 0)
    
    return all(results)


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("Agentic Cinema Test Suite")
    print("=" * 60)
    
    unit_ok = run_unit_tests()
    print(f"\nUnit tests: {'PASSED' if unit_ok else 'FAILED'}")
    
    integration_ok = run_integration_tests()
    print(f"\nIntegration tests: {'PASSED' if integration_ok else 'FAILED'}")
    
    pytest_ok = run_pytest()
    print(f"\nPytest with coverage: {'PASSED' if pytest_ok == 0 else 'FAILED'}")
    
    print("\n" + "=" * 60)
    if unit_ok and integration_ok and pytest_ok == 0:
        print("ALL TESTS PASSED")
        print("=" * 60)
        return 0
    print("SOME TESTS FAILED")
    print("=" * 60)
    return 1


if __name__ == "__main__":
    sys.exit(main())