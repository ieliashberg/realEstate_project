#!/usr/bin/env python3
"""
Test runner for the real estate project.

This script provides a convenient way to run all tests or specific test categories.
"""

import sys
import os
import subprocess
import argparse
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def run_tests(test_pattern=None, verbose=False, coverage=False, parallel=False):
    """
    Run tests using pytest.
    
    Args:
        test_pattern: Pattern to match test files (e.g., 'test_job_runner*')
        verbose: Enable verbose output
        coverage: Enable coverage reporting
        parallel: Run tests in parallel
    """
    # Base pytest command
    cmd = ["python", "-m", "pytest"]
    
    # Add test pattern if specified
    if test_pattern:
        cmd.append(f"tests/{test_pattern}")
    else:
        cmd.append("tests/")
    
    # Add verbosity
    if verbose:
        cmd.append("-v")
    
    # Add coverage
    if coverage:
        cmd.append("--cov=.")
        cmd.append("--cov-report=html")
        cmd.append("--cov-report=term")
    
    # Add parallel execution
    if parallel:
        cmd.extend(["-n", "auto"])
    
    # Add other useful options
    cmd.extend([
        "--tb=short",  # Shorter traceback format
        "--strict-markers",  # Strict marker handling
        "--disable-warnings",  # Disable warnings for cleaner output
    ])
    
    print(f"Running command: {' '.join(cmd)}")
    print("-" * 60)
    
    # Run the tests
    result = subprocess.run(cmd, cwd=project_root)
    return result.returncode


def run_specific_tests():
    """Run specific test categories."""
    test_categories = {
        "1": ("All tests", None),
        "2": ("Error handling tests", "test_comprehensive_error_handling*"),
        "3": ("Job runner tests", "test_job_runner*"),
        "4": ("Zestimate helper tests", "test_zestimate_helper*"),
        "5": ("Home info helper tests", "test_specfic_home_info_helper*"),
        "6": ("Homes from zipcode tests", "test_homes_from_zipcode_helper*"),
        "7": ("User agent service tests", "test_user_agent_service*"),
        "8": ("HTTP utils tests", "test_http_utils*"),
        "9": ("Integration tests", "test_integration*"),
        "10": ("Legacy tests", "test_*"),  # Original test files
    }
    
    print("Available test categories:")
    print("-" * 40)
    for key, (description, _) in test_categories.items():
        print(f"{key}. {description}")
    
    choice = input("\nSelect test category (1-10): ").strip()
    
    if choice in test_categories:
        description, pattern = test_categories[choice]
        print(f"\nRunning {description}...")
        return run_tests(pattern, verbose=True)
    else:
        print("Invalid choice!")
        return 1


def run_quick_tests():
    """Run a quick subset of tests for fast feedback."""
    quick_tests = [
        "test_http_utils_comprehensive.py",
        "test_comprehensive_error_handling.py::TestErrorHandling::test_get_specific_property_info_with_none_payload",
    ]
    
    cmd = ["python", "-m", "pytest"]
    for test in quick_tests:
        cmd.append(f"tests/{test}")
    
    cmd.extend(["-v", "--tb=short"])
    
    print("Running quick tests...")
    print(f"Command: {' '.join(cmd)}")
    print("-" * 60)
    
    result = subprocess.run(cmd, cwd=project_root)
    return result.returncode


def run_coverage_report():
    """Run tests with coverage and generate HTML report."""
    print("Running tests with coverage...")
    return run_tests(verbose=True, coverage=True)


def main():
    """Main function to handle command line arguments."""
    parser = argparse.ArgumentParser(description="Real Estate Project Test Runner")
    parser.add_argument("--pattern", "-p", help="Test file pattern (e.g., 'test_job_runner*')")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--coverage", "-c", action="store_true", help="Run with coverage")
    parser.add_argument("--parallel", action="store_true", help="Run tests in parallel")
    parser.add_argument("--quick", "-q", action="store_true", help="Run quick tests")
    parser.add_argument("--interactive", "-i", action="store_true", help="Interactive test selection")
    
    args = parser.parse_args()
    
    # Handle special modes
    if args.quick:
        return run_quick_tests()
    
    if args.interactive:
        return run_specific_tests()
    
    if args.coverage:
        return run_coverage_report()
    
    # Run tests with specified options
    return run_tests(
        test_pattern=args.pattern,
        verbose=args.verbose,
        coverage=args.coverage,
        parallel=args.parallel
    )


if __name__ == "__main__":
    sys.exit(main())
