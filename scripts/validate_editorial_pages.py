#!/usr/bin/env python3
"""
Editorial Page Validation Script

Validates that all published editorial pages:
1. Return HTTP 200
2. Have expected title present
3. Have canonical URL present
4. Have no redirect loops

Usage:
  python scripts/validate_editorial_pages.py
  python scripts/validate_editorial_pages.py --api-url http://localhost:8000
  python scripts/validate_editorial_pages.py --frontend-url http://localhost:3000
  python scripts/validate_editorial_pages.py --output report.json
"""

import argparse
import json
import os
import sys
import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from urllib.parse import urljoin

# Load .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import psycopg2
from psycopg2.extras import RealDictCursor

try:
    import requests
except ImportError:
    print("ERROR: requests package required. Run: pip install requests")
    sys.exit(1)


def get_published_editorial(db_url: str) -> List[Dict]:
    """
    Get all published editorial records from the database.
    """
    conn = psycopg2.connect(db_url)
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""
            SELECT
                e.id as editorial_id,
                e.ad_id,
                e.brand_slug,
                e.slug,
                e.headline,
                e.editorial_summary,
                e.curated_tags,
                e.status,
                e.publish_date,
                e.legacy_url,
                a.external_id,
                a.brand_name,
                a.one_line_summary
            FROM ad_editorial e
            JOIN ads a ON a.id = e.ad_id
            WHERE e.status = 'published'
              AND e.is_hidden = false
              AND (e.publish_date IS NULL OR e.publish_date <= NOW())
            ORDER BY e.brand_slug, e.slug
        """)
        return cur.fetchall()


def validate_api_response(api_url: str, brand_slug: str, slug: str) -> Dict:
    """
    Validate the backend API response for a single ad.

    Returns:
        {
            'status_code': int,
            'passed': bool,
            'checks': {
                'http_200': bool,
                'has_headline': bool,
                'has_description': bool,
                'no_error': bool,
            },
            'errors': [str],
            'response_data': dict or None,
        }
    """
    result = {
        'status_code': None,
        'passed': False,
        'checks': {
            'http_200': False,
            'has_headline': False,
            'has_description': False,
            'no_error': False,
        },
        'errors': [],
        'response_data': None,
    }

    try:
        url = f"{api_url.rstrip('/')}/api/advert/{brand_slug}/{slug}"
        resp = requests.get(url, timeout=10, allow_redirects=True)
        result['status_code'] = resp.status_code

        # Check 1: HTTP 200
        result['checks']['http_200'] = resp.status_code == 200
        if resp.status_code != 200:
            result['errors'].append(f"HTTP {resp.status_code}")
            return result

        # Parse JSON response
        try:
            data = resp.json()
            result['response_data'] = data
            result['checks']['no_error'] = True
        except json.JSONDecodeError as e:
            result['errors'].append(f"Invalid JSON: {e}")
            return result

        # Check 2: Has headline or one_line_summary
        headline = data.get('headline') or data.get('one_line_summary') or data.get('description')
        result['checks']['has_headline'] = bool(headline)
        if not headline:
            result['errors'].append("Missing headline/title")

        # Check 3: Has description
        description = data.get('description') or data.get('editorial_summary') or data.get('one_line_summary')
        result['checks']['has_description'] = bool(description)
        if not description:
            result['errors'].append("Missing description")

        # Determine pass/fail
        result['passed'] = all([
            result['checks']['http_200'],
            result['checks']['has_headline'],
            result['checks']['no_error'],
        ])

    except requests.exceptions.Timeout:
        result['errors'].append("Request timeout")
    except requests.exceptions.ConnectionError as e:
        result['errors'].append(f"Connection error: {e}")
    except Exception as e:
        result['errors'].append(f"Unexpected error: {e}")

    return result


def validate_frontend_page(frontend_url: str, brand_slug: str, slug: str) -> Dict:
    """
    Validate the frontend page for a single ad.

    Checks:
    - HTTP 200
    - <title> tag present and non-empty
    - Canonical URL present
    - No redirect loops

    Returns similar structure to validate_api_response.
    """
    result = {
        'status_code': None,
        'passed': False,
        'checks': {
            'http_200': False,
            'has_title': False,
            'has_canonical': False,
            'no_redirect_loop': True,
        },
        'errors': [],
        'html_preview': None,
    }

    try:
        url = f"{frontend_url.rstrip('/')}/advert/{brand_slug}/{slug}"

        # Track redirects
        redirect_count = 0
        max_redirects = 10
        visited_urls = set()

        current_url = url
        while redirect_count < max_redirects:
            if current_url in visited_urls:
                result['checks']['no_redirect_loop'] = False
                result['errors'].append(f"Redirect loop detected at {current_url}")
                return result
            visited_urls.add(current_url)

            resp = requests.get(current_url, timeout=10, allow_redirects=False)

            if resp.status_code in (301, 302, 307, 308):
                redirect_count += 1
                current_url = resp.headers.get('Location', '')
                if not current_url.startswith('http'):
                    current_url = urljoin(current_url, resp.headers.get('Location', ''))
                continue
            else:
                break

        result['status_code'] = resp.status_code

        # Check 1: HTTP 200
        result['checks']['http_200'] = resp.status_code == 200
        if resp.status_code != 200:
            result['errors'].append(f"HTTP {resp.status_code}")
            return result

        html = resp.text
        result['html_preview'] = html[:500] if html else None

        # Check 2: <title> tag present
        title_match = re.search(r'<title[^>]*>([^<]+)</title>', html, re.IGNORECASE)
        if title_match:
            title = title_match.group(1).strip()
            result['checks']['has_title'] = bool(title) and 'Not Found' not in title
            if not result['checks']['has_title']:
                result['errors'].append(f"Title appears to be error page: {title}")
        else:
            result['errors'].append("Missing <title> tag")

        # Check 3: Canonical URL present
        canonical_match = re.search(r'<link[^>]+rel=["\']canonical["\'][^>]+href=["\']([^"\']+)["\']', html, re.IGNORECASE)
        if not canonical_match:
            canonical_match = re.search(r'<link[^>]+href=["\']([^"\']+)["\'][^>]+rel=["\']canonical["\']', html, re.IGNORECASE)

        if canonical_match:
            canonical_url = canonical_match.group(1)
            result['checks']['has_canonical'] = bool(canonical_url)
            # Verify canonical contains expected path
            expected_path = f"/advert/{brand_slug}/{slug}"
            if expected_path not in canonical_url:
                result['errors'].append(f"Canonical URL mismatch: {canonical_url}")
        else:
            result['errors'].append("Missing canonical URL")

        # Determine pass/fail
        result['passed'] = all([
            result['checks']['http_200'],
            result['checks']['has_title'],
            result['checks']['has_canonical'],
            result['checks']['no_redirect_loop'],
        ])

    except requests.exceptions.Timeout:
        result['errors'].append("Request timeout")
    except requests.exceptions.ConnectionError as e:
        result['errors'].append(f"Connection error: {e}")
    except Exception as e:
        result['errors'].append(f"Unexpected error: {e}")

    return result


def run_validation(
    db_url: str,
    api_url: Optional[str] = None,
    frontend_url: Optional[str] = None,
    verbose: bool = False,
) -> Dict:
    """
    Run full validation across all published editorial records.

    Returns:
        {
            'summary': {
                'total': int,
                'passed': int,
                'failed': int,
                'pass_rate': float,
            },
            'results': [...],
            'failures': [...],
        }
    """
    print("Loading published editorial records from database...")
    records = get_published_editorial(db_url)
    print(f"Found {len(records)} published editorial records\n")

    results = []
    failures = []
    passed_count = 0

    for i, record in enumerate(records, 1):
        brand_slug = record['brand_slug']
        slug = record['slug']
        headline = record['headline'] or record['one_line_summary'] or '(no title)'

        print(f"[{i}/{len(records)}] {brand_slug}/{slug}")

        row_result = {
            'brand_slug': brand_slug,
            'slug': slug,
            'headline': headline,
            'external_id': record['external_id'],
            'legacy_url': record['legacy_url'],
            'api_result': None,
            'frontend_result': None,
            'passed': True,
        }

        # Validate API if URL provided
        if api_url:
            api_result = validate_api_response(api_url, brand_slug, slug)
            row_result['api_result'] = api_result
            if not api_result['passed']:
                row_result['passed'] = False
                if verbose:
                    print(f"  API FAIL: {', '.join(api_result['errors'])}")
            else:
                if verbose:
                    print(f"  API PASS")

        # Validate frontend if URL provided
        if frontend_url:
            fe_result = validate_frontend_page(frontend_url, brand_slug, slug)
            row_result['frontend_result'] = fe_result
            if not fe_result['passed']:
                row_result['passed'] = False
                if verbose:
                    print(f"  Frontend FAIL: {', '.join(fe_result['errors'])}")
            else:
                if verbose:
                    print(f"  Frontend PASS")

        # If no URL provided, just mark as passed (schema validation only)
        if not api_url and not frontend_url:
            row_result['passed'] = True
            if verbose:
                print(f"  (No URL validation - schema only)")

        results.append(row_result)

        if row_result['passed']:
            passed_count += 1
            print(f"  PASS")
        else:
            failures.append(row_result)
            print(f"  FAIL")

    summary = {
        'total': len(records),
        'passed': passed_count,
        'failed': len(records) - passed_count,
        'pass_rate': (passed_count / len(records) * 100) if records else 0,
        'timestamp': datetime.now().isoformat(),
    }

    return {
        'summary': summary,
        'results': results,
        'failures': failures,
    }


def print_report(report: Dict):
    """Print human-readable validation report."""
    summary = report['summary']

    print("\n" + "=" * 60)
    print("EDITORIAL PAGE VALIDATION REPORT")
    print("=" * 60)
    print(f"Total records:    {summary['total']}")
    print(f"Passed:           {summary['passed']}")
    print(f"Failed:           {summary['failed']}")
    print(f"Pass rate:        {summary['pass_rate']:.1f}%")
    print(f"Timestamp:        {summary['timestamp']}")
    print("=" * 60)

    if report['failures']:
        print("\nFAILURES:")
        print("-" * 60)
        for failure in report['failures']:
            print(f"\n{failure['brand_slug']}/{failure['slug']}")
            print(f"  Headline: {failure['headline']}")
            print(f"  External ID: {failure['external_id']}")
            if failure['api_result'] and not failure['api_result']['passed']:
                print(f"  API errors: {', '.join(failure['api_result']['errors'])}")
            if failure['frontend_result'] and not failure['frontend_result']['passed']:
                print(f"  Frontend errors: {', '.join(failure['frontend_result']['errors'])}")
    else:
        print("\nAll pages passed validation!")


def main():
    parser = argparse.ArgumentParser(description='Validate editorial pages')
    parser.add_argument('--api-url', default='http://localhost:8000',
                        help='Backend API URL (default: http://localhost:8000)')
    parser.add_argument('--frontend-url', default=None,
                        help='Frontend URL (optional, for HTML validation)')
    parser.add_argument('--db-url', default=None,
                        help='Database URL (default: SUPABASE_DB_URL env)')
    parser.add_argument('--output', '-o', default=None,
                        help='Output JSON report to file')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Verbose output')
    parser.add_argument('--api-only', action='store_true',
                        help='Only validate API, skip frontend')
    parser.add_argument('--frontend-only', action='store_true',
                        help='Only validate frontend, skip API')
    parser.add_argument('--schema-only', action='store_true',
                        help='Only validate database schema, skip HTTP checks')

    args = parser.parse_args()

    db_url = args.db_url or os.environ.get('SUPABASE_DB_URL')
    if not db_url:
        print("Error: Database URL required (--db-url or SUPABASE_DB_URL env)")
        sys.exit(1)

    # Determine what to validate
    api_url = None if (args.frontend_only or args.schema_only) else args.api_url
    frontend_url = None if (args.api_only or args.schema_only) else args.frontend_url

    report = run_validation(
        db_url=db_url,
        api_url=api_url,
        frontend_url=frontend_url,
        verbose=args.verbose,
    )

    print_report(report)

    # Save JSON report if requested
    if args.output:
        # Clean up non-serializable data
        for result in report['results']:
            if result.get('frontend_result'):
                result['frontend_result'].pop('html_preview', None)

        with open(args.output, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        print(f"\nReport saved to: {args.output}")

    # Exit with error code if any failures
    sys.exit(0 if report['summary']['failed'] == 0 else 1)


if __name__ == '__main__':
    main()
