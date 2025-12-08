#!/usr/bin/env python3
"""
Analytics Truth Test

Emits a deterministic set of events and verifies they are correctly captured
in the database. Run this to prove correctness of the analytics pipeline.

Usage:
    python scripts/analytics/truth_test.py --base-url http://localhost:3000
    python scripts/analytics/truth_test.py --base-url https://tellyads.com --admin-key <key>

Requirements:
    pip install requests psycopg2-binary python-dotenv

Environment:
    SUPABASE_DB_URL - PostgreSQL connection string (for direct DB verification)
    ADMIN_API_KEY - Admin API key (for API-based verification)
"""

import argparse
import hashlib
import json
import os
import random
import string
import sys
import time
from datetime import datetime, timezone
from typing import Optional

import requests

try:
    import psycopg2
    HAS_PSYCOPG2 = True
except ImportError:
    HAS_PSYCOPG2 = False

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


# =============================================================================
# Configuration
# =============================================================================

# Test events to emit
TEST_EVENTS = {
    "page.view": 5,
    "search.performed": 3,
    "search.zero_results": 1,
    "search.result_click": 2,
    "advert.view": 4,
    "advert.play": 2,
    "advert.complete": 1,
    "browse.era_click": 2,
    "browse.brand_click": 1,
}

# Unique test session ID for this run
def generate_test_session() -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    random_suffix = "".join(random.choices(string.ascii_lowercase, k=6))
    return f"truth_test_{timestamp}_{random_suffix}"


def generate_ua_hash() -> str:
    """Generate a consistent UA hash for testing."""
    ua = "TruthTest/1.0 (Analytics Verification)"
    return hashlib.sha256(ua.encode()).hexdigest()[:16]


# =============================================================================
# Event Emission
# =============================================================================

def emit_event(
    base_url: str,
    event: str,
    session_id: str,
    ua_hash: str,
    props: Optional[dict] = None,
) -> bool:
    """Emit a single analytics event."""
    url = f"{base_url}/api/analytics/capture"

    payload = {
        "event": event,
        "path": f"/truth-test/{event.replace('.', '/')}",
        "session_id": session_id,
        "ua_hash": ua_hash,
        "props": props or {},
    }

    try:
        response = requests.post(
            url,
            json=payload,
            headers={
                "Content-Type": "application/json",
                "Origin": base_url,  # Required for origin validation
            },
            timeout=10,
        )
        # 204 No Content is success, 400 is validation error, 429 is rate limit
        return response.status_code in (204, 200)
    except requests.RequestException as e:
        print(f"  Error emitting {event}: {e}")
        return False


def emit_all_events(base_url: str, session_id: str, ua_hash: str) -> dict:
    """Emit all test events and return expected counts."""
    print(f"\nEmitting events with session: {session_id}")
    print("-" * 50)

    expected = {}

    for event, count in TEST_EVENTS.items():
        expected[event] = count
        successes = 0

        for i in range(count):
            # Add event-specific props
            props = {}
            if event == "search.performed":
                props = {"query": f"test query {i}", "results_count": 10 + i}
            elif event == "search.zero_results":
                props = {"query": "nonexistent query"}
            elif event == "search.result_click":
                props = {"query": "test", "ad_id": f"ad_{i}", "position": i + 1}
            elif event == "advert.view":
                props = {"ad_id": f"test_ad_{i}", "brand": "TestBrand", "source": "truth_test"}
            elif event == "browse.era_click":
                props = {"decade": f"{1980 + i * 10}s"}

            if emit_event(base_url, event, session_id, ua_hash, props):
                successes += 1

            # Small delay to avoid rate limiting
            time.sleep(0.05)

        status = "OK" if successes == count else "PARTIAL"
        print(f"  {event}: {successes}/{count} [{status}]")
        expected[event] = successes  # Update to actual success count

    return expected


# =============================================================================
# Verification
# =============================================================================

def verify_via_db(session_id: str, expected: dict) -> dict:
    """Verify counts directly from the database."""
    db_url = os.getenv("SUPABASE_DB_URL")
    if not db_url:
        return {"error": "SUPABASE_DB_URL not set"}

    if not HAS_PSYCOPG2:
        return {"error": "psycopg2 not installed"}

    try:
        conn = psycopg2.connect(db_url)
        cur = conn.cursor()

        # Count events by type for this session
        cur.execute("""
            SELECT event, COUNT(*) as count
            FROM analytics_events
            WHERE session_id = %s
            GROUP BY event
            ORDER BY event
        """, (session_id,))

        rows = cur.fetchall()
        actual = {row[0]: row[1] for row in rows}

        cur.close()
        conn.close()

        return {"actual": actual, "source": "database"}
    except Exception as e:
        return {"error": str(e)}


def verify_via_api(base_url: str, admin_key: str, session_id: str) -> dict:
    """Verify counts via admin API (less precise, uses daily rollups)."""
    # The admin APIs use rollups which may not have run yet
    # This is a basic check that events are being captured
    url = f"{base_url}/api/admin/analytics/overview"

    try:
        response = requests.get(
            url,
            headers={"x-admin-key": admin_key},
            timeout=10,
        )

        if response.status_code == 200:
            data = response.json()
            return {
                "events_today": data.get("events_today", 0),
                "capture_events_24h": data.get("capture_events_24h", 0),
                "capture_error_count": data.get("capture_error_count", 0),
                "source": "api",
            }
        else:
            return {"error": f"API returned {response.status_code}"}
    except requests.RequestException as e:
        return {"error": str(e)}


def compare_results(expected: dict, actual: dict) -> tuple[bool, list[str]]:
    """Compare expected vs actual counts."""
    all_pass = True
    messages = []

    for event, exp_count in expected.items():
        act_count = actual.get(event, 0)
        if act_count == exp_count:
            messages.append(f"  PASS: {event} = {act_count}")
        else:
            messages.append(f"  FAIL: {event} expected {exp_count}, got {act_count}")
            all_pass = False

    # Check for unexpected events
    for event, count in actual.items():
        if event not in expected:
            messages.append(f"  WARN: unexpected event {event} = {count}")

    return all_pass, messages


# =============================================================================
# Main
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description="Analytics Truth Test")
    parser.add_argument(
        "--base-url",
        default="http://localhost:3000",
        help="Base URL of the TellyAds app",
    )
    parser.add_argument(
        "--admin-key",
        default=os.getenv("ADMIN_API_KEY"),
        help="Admin API key for verification",
    )
    parser.add_argument(
        "--skip-emit",
        action="store_true",
        help="Skip event emission (verify existing session)",
    )
    parser.add_argument(
        "--session",
        help="Use specific session ID instead of generating new one",
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Only run verification against existing events",
    )

    args = parser.parse_args()

    print("=" * 60)
    print("ANALYTICS TRUTH TEST")
    print("=" * 60)
    print(f"Base URL: {args.base_url}")
    print(f"Time: {datetime.now(timezone.utc).isoformat()}")

    session_id = args.session or generate_test_session()
    ua_hash = generate_ua_hash()

    # Step 1: Emit events
    if not args.skip_emit and not args.verify_only:
        expected = emit_all_events(args.base_url, session_id, ua_hash)
        total_expected = sum(expected.values())
        print(f"\nTotal events emitted: {total_expected}")
    else:
        expected = TEST_EVENTS.copy()
        print(f"\nSkipping emission, using expected: {expected}")

    # Step 2: Wait for events to be processed
    if not args.verify_only:
        print("\nWaiting 2 seconds for events to be processed...")
        time.sleep(2)

    # Step 3: Verify via database (preferred)
    print("\n" + "=" * 60)
    print("VERIFICATION")
    print("=" * 60)

    db_result = verify_via_db(session_id, expected)

    if "error" not in db_result:
        print(f"\nDatabase verification (session: {session_id}):")
        all_pass, messages = compare_results(expected, db_result["actual"])
        for msg in messages:
            print(msg)

        if all_pass:
            print("\n" + "=" * 60)
            print("RESULT: ALL TESTS PASSED")
            print("=" * 60)
            return 0
        else:
            print("\n" + "=" * 60)
            print("RESULT: SOME TESTS FAILED")
            print("=" * 60)
            return 1
    else:
        print(f"\nDatabase verification unavailable: {db_result['error']}")

    # Step 4: Fallback to API verification
    if args.admin_key:
        print("\nAPI verification (overview metrics):")
        api_result = verify_via_api(args.base_url, args.admin_key, session_id)

        if "error" not in api_result:
            print(f"  events_today: {api_result.get('events_today', 'N/A')}")
            print(f"  capture_events_24h: {api_result.get('capture_events_24h', 'N/A')}")
            print(f"  capture_error_count: {api_result.get('capture_error_count', 'N/A')}")

            # Basic sanity check
            if api_result.get("capture_events_24h", 0) > 0:
                print("\n  API shows events being captured (exact verification requires DB)")
                return 0
            else:
                print("\n  WARNING: API shows no events captured in last 24h")
                return 1
        else:
            print(f"  Error: {api_result['error']}")
    else:
        print("\nAPI verification skipped (no admin key provided)")

    print("\n" + "=" * 60)
    print("RESULT: VERIFICATION INCOMPLETE")
    print("=" * 60)
    print("Set SUPABASE_DB_URL or ADMIN_API_KEY for full verification")
    return 2


if __name__ == "__main__":
    sys.exit(main())
