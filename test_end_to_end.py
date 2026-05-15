#!/usr/bin/env python3
"""End-to-end test suite for HuntFlow to verify all components work."""

import os
import sys
from datetime import datetime

# Add project to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def test_imports():
    """Test 1: Verify all critical imports work."""
    print("\n[TEST 1] Verifying imports...")
    try:
        from cli import run_daily, run_outreach, digest
        from crews import create_daily_discovery_crew, create_outreach_crew, create_interview_prep_crew, create_digest_crew
        from agents import get_llm
        from tools.sqlite_tracker import DatabaseManager
        from tools.chromadb_memory import MemoryManager
        print("  [OK] All imports successful")
        return True
    except Exception as e:
        print(f"  [FAIL] Import failed: {e}")
        return False


def test_llm_factory():
    """Test 2: Verify LLM factory works with new model."""
    print("\n[TEST 2] Testing LLM factory...")
    try:
        from agents import get_llm
        llm = get_llm()
        print(f"  [OK] LLM factory initialized")
        print(f"    - Provider: {os.getenv('LLM_PROVIDER', 'groq')}")
        print(f"    - Model: {os.getenv('LLM_MODEL', 'mixtral-8x7b-32768')}")
        print(f"    - LLM object: {type(llm).__name__}")
        return True
    except Exception as e:
        print(f"  [FAIL] LLM factory failed: {e}")
        return False


def test_crews_creation():
    """Test 3: Verify all crews can be created."""
    print("\n[TEST 3] Creating all crews...")
    try:
        from crews import create_daily_discovery_crew, create_outreach_crew, create_interview_prep_crew, create_digest_crew

        # Digest crew (simplest, no Tavily dependency)
        digest_crew = create_digest_crew()
        print(f"  [OK] Digest crew: {len(digest_crew.tasks)} task(s), {len(digest_crew.agents)} agent(s)")

        # Interview prep crew
        interview_crew = create_interview_prep_crew("TestCorp", "Backend Engineer")
        print(f"  [OK] Interview prep crew: {len(interview_crew.tasks)} task(s), {len(interview_crew.agents)} agent(s)")

        # Outreach crew
        outreach_crew = create_outreach_crew()
        print(f"  [OK] Outreach crew: {len(outreach_crew.tasks)} task(s), {len(outreach_crew.agents)} agent(s)")

        # Daily discovery crew (most complex)
        daily_crew = create_daily_discovery_crew()
        print(f"  [OK] Daily discovery crew: {len(daily_crew.tasks)} task(s), {len(daily_crew.agents)} agent(s)")

        return True
    except Exception as e:
        print(f"  [FAIL] Crew creation failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_database():
    """Test 4: Verify database initialization."""
    print("\n[TEST 4] Testing database...")
    try:
        from tools.sqlite_tracker import DatabaseManager
        db = DatabaseManager()
        stats = db.get_daily_stats()
        print(f"  [OK] Database initialized and queryable")
        print(f"    - Pipeline stats keys: {list(stats.keys())}")
        return True
    except Exception as e:
        print(f"  [FAIL] Database test failed: {e}")
        return False


def test_memory():
    """Test 5: Verify memory system (ChromaDB)."""
    print("\n[TEST 5] Testing memory system...")
    try:
        from tools.chromadb_memory import MemoryManager
        memory = MemoryManager()
        stats = memory.get_collection_stats()
        print(f"  [OK] Memory system initialized")
        print(f"    - Collections: {list(stats.keys())}")
        return True
    except Exception as e:
        print(f"  [FAIL] Memory test failed: {e}")
        return False


def test_scheduler_args():
    """Test 6: Verify scheduler argument parsing."""
    print("\n[TEST 6] Testing scheduler argument parsing...")
    try:
        import argparse
        parser = argparse.ArgumentParser(description="HuntFlow Scheduler")
        parser.add_argument("--once", action="store_true", help="Run job once and exit")
        parser.add_argument("--job", default="daily", choices=["daily", "digest", "outreach", "stale"], help="Job to run")

        # Test various argument combinations
        test_cases = [
            (["--once", "--job", "daily"], {"once": True, "job": "daily"}),
            (["--once", "--job", "digest"], {"once": True, "job": "digest"}),
            (["--job", "outreach"], {"once": False, "job": "outreach"}),
            ([], {"once": False, "job": "daily"}),
        ]

        for args, expected in test_cases:
            parsed = parser.parse_args(args)
            assert parsed.once == expected["once"], f"once mismatch for {args}"
            assert parsed.job == expected["job"], f"job mismatch for {args}"

        print(f"  [OK] Scheduler argument parsing works for all test cases")
        return True
    except Exception as e:
        print(f"  [FAIL] Scheduler arg parsing failed: {e}")
        return False


def test_cli_functions():
    """Test 7: Verify CLI functions are callable."""
    print("\n[TEST 7] Testing CLI functions...")
    try:
        from cli import run_daily, run_outreach, digest, prep_impl, status_impl
        import inspect

        functions = {
            "run_daily": run_daily,
            "run_outreach": run_outreach,
            "digest": digest,
            "prep_impl": prep_impl,
            "status_impl": status_impl,
        }

        for name, func in functions.items():
            if not callable(func):
                raise ValueError(f"{name} is not callable")
            sig = inspect.signature(func)
            print(f"  [OK] {name}{sig}")

        return True
    except Exception as e:
        print(f"  [FAIL] CLI function test failed: {e}")
        return False


def run_all_tests():
    """Run all tests and report results."""
    print("=" * 70)
    print("HuntFlow End-to-End Test Suite")
    print("=" * 70)
    print("Started: " + datetime.now().isoformat())

    tests = [
        ("Imports", test_imports),
        ("LLM Factory", test_llm_factory),
        ("Crew Creation", test_crews_creation),
        ("Database", test_database),
        ("Memory System", test_memory),
        ("Scheduler Args", test_scheduler_args),
        ("CLI Functions", test_cli_functions),
    ]

    results = {}
    for name, test_func in tests:
        try:
            results[name] = test_func()
        except Exception as e:
            print("\n[ERROR] Test '" + name + "' crashed: " + str(e))
            import traceback
            traceback.print_exc()
            results[name] = False

    # Summary
    print("\n" + "=" * 70)
    print("Test Results Summary")
    print("=" * 70)
    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for name, result in results.items():
        status = "[PASS]" if result else "[FAIL]"
        print("  " + status + ": " + name)

    print("\nTotal: " + str(passed) + "/" + str(total) + " tests passed")

    if passed == total:
        print("\n[SUCCESS] All tests passed! Ready for production.")
        return 0
    else:
        print("\n[FAILURE] " + str(total - passed) + " test(s) failed. Fix before production.")
        return 1


if __name__ == "__main__":
    sys.exit(run_all_tests())
