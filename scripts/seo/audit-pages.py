#!/usr/bin/env python3
"""
SEO Page Audit Script

Audits all routes in the TellyAds app for:
- Title and description presence
- Canonical tag correctness (self-referencing, uses https://tellyads.com)
- Open Graph tags
- Robots meta tags
- Noindex rules for search/faceted pages

Usage:
  python scripts/seo/audit-pages.py --base-url http://localhost:3000
  python scripts/seo/audit-pages.py --base-url https://tellyads.com
"""

import argparse
import csv
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

CANONICAL_HOST = 'https://tellyads.com'

@dataclass
class PageAuditResult:
    """Result of auditing a single page"""
    route: str
    status_code: int
    has_title: bool
    title_value: str
    has_description: bool
    description_value: str
    has_canonical: bool
    canonical_value: str
    canonical_correct: bool
    has_og_title: bool
    has_og_description: bool
    has_og_image: bool
    has_robots: bool
    robots_value: str
    is_noindex: bool
    expected_noindex: bool
    noindex_correct: bool
    errors: list


def get_expected_noindex(route: str) -> bool:
    """Determine if a route should be noindex"""
    # Admin pages should be noindex
    if route.startswith('/admin'):
        return True
    # Search with query params should be noindex
    if route.startswith('/search?'):
        return True
    # Random redirects - should be noindex
    if route == '/random':
        return True
    # /ads/* URLs are non-canonical - should be noindex
    if re.match(r'^/ads/[^/]+$', route):
        return True
    return False


def get_expected_canonical(route: str) -> Optional[str]:
    """Get expected canonical URL for a route"""
    # Admin pages shouldn't have canonical (or should be noindex anyway)
    if route.startswith('/admin'):
        return None
    # Search with query params shouldn't have canonical
    if '?' in route:
        return None
    # Random page redirects - no canonical needed
    if route == '/random':
        return None
    # /ads/* URLs should have canonical pointing to /advert/*
    # (but we can't determine the exact canonical without DB lookup)
    if re.match(r'^/ads/[^/]+$', route):
        return None  # Skip check - would need DB lookup

    # All other pages should have self-referencing canonical
    return f"{CANONICAL_HOST}{route}"


def audit_page(base_url: str, route: str, timeout: int = 30) -> PageAuditResult:
    """Audit a single page for SEO compliance"""
    url = urljoin(base_url, route)
    errors = []

    try:
        response = requests.get(url, timeout=timeout, allow_redirects=True)
        status_code = response.status_code

        if status_code != 200:
            return PageAuditResult(
                route=route,
                status_code=status_code,
                has_title=False,
                title_value='',
                has_description=False,
                description_value='',
                has_canonical=False,
                canonical_value='',
                canonical_correct=False,
                has_og_title=False,
                has_og_description=False,
                has_og_image=False,
                has_robots=False,
                robots_value='',
                is_noindex=False,
                expected_noindex=get_expected_noindex(route),
                noindex_correct=False,
                errors=[f"HTTP {status_code}"]
            )

        soup = BeautifulSoup(response.text, 'html.parser')

        # Title
        title_tag = soup.find('title')
        has_title = title_tag is not None and title_tag.string
        title_value = title_tag.string.strip() if title_tag and title_tag.string else ''

        # Description
        desc_tag = soup.find('meta', attrs={'name': 'description'})
        has_description = desc_tag is not None and desc_tag.get('content')
        description_value = desc_tag.get('content', '')[:100] if desc_tag else ''

        # Canonical
        canonical_tag = soup.find('link', attrs={'rel': 'canonical'})
        has_canonical = canonical_tag is not None and canonical_tag.get('href')
        canonical_value = canonical_tag.get('href', '') if canonical_tag else ''

        # Check canonical correctness
        expected_canonical = get_expected_canonical(route)
        canonical_correct = True
        if expected_canonical:
            if not has_canonical:
                canonical_correct = False
                errors.append(f"Missing canonical (expected {expected_canonical})")
            elif canonical_value != expected_canonical:
                canonical_correct = False
                errors.append(f"Wrong canonical: {canonical_value} (expected {expected_canonical})")
        elif has_canonical and not route.startswith('/advert/'):
            # Having canonical when not expected is usually fine, just verify it uses canonical host
            if not canonical_value.startswith(CANONICAL_HOST):
                canonical_correct = False
                errors.append(f"Canonical uses wrong host: {canonical_value}")

        # Open Graph
        og_title = soup.find('meta', attrs={'property': 'og:title'})
        og_desc = soup.find('meta', attrs={'property': 'og:description'})
        og_image = soup.find('meta', attrs={'property': 'og:image'})
        has_og_title = og_title is not None and og_title.get('content')
        has_og_description = og_desc is not None and og_desc.get('content')
        has_og_image = og_image is not None and og_image.get('content')

        # Robots
        robots_tag = soup.find('meta', attrs={'name': 'robots'})
        has_robots = robots_tag is not None
        robots_value = robots_tag.get('content', '') if robots_tag else ''
        is_noindex = 'noindex' in robots_value.lower() if robots_value else False

        expected_noindex = get_expected_noindex(route)
        noindex_correct = is_noindex == expected_noindex
        if not noindex_correct:
            if expected_noindex:
                errors.append(f"Should be noindex but is indexed")
            else:
                errors.append(f"Should be indexed but has noindex")

        # Validation errors
        if not has_title:
            errors.append("Missing <title>")
        if not has_description and not expected_noindex:
            errors.append("Missing meta description")
        if not has_og_title and not expected_noindex:
            errors.append("Missing og:title")

        return PageAuditResult(
            route=route,
            status_code=status_code,
            has_title=has_title,
            title_value=title_value[:60],
            has_description=has_description,
            description_value=description_value,
            has_canonical=has_canonical,
            canonical_value=canonical_value,
            canonical_correct=canonical_correct,
            has_og_title=has_og_title,
            has_og_description=has_og_description,
            has_og_image=has_og_image,
            has_robots=has_robots,
            robots_value=robots_value,
            is_noindex=is_noindex,
            expected_noindex=expected_noindex,
            noindex_correct=noindex_correct,
            errors=errors
        )

    except requests.exceptions.Timeout:
        return PageAuditResult(
            route=route, status_code=0, has_title=False, title_value='',
            has_description=False, description_value='', has_canonical=False,
            canonical_value='', canonical_correct=False, has_og_title=False,
            has_og_description=False, has_og_image=False, has_robots=False,
            robots_value='', is_noindex=False, expected_noindex=get_expected_noindex(route),
            noindex_correct=False, errors=['TIMEOUT']
        )
    except Exception as e:
        return PageAuditResult(
            route=route, status_code=0, has_title=False, title_value='',
            has_description=False, description_value='', has_canonical=False,
            canonical_value='', canonical_correct=False, has_og_title=False,
            has_og_description=False, has_og_image=False, has_robots=False,
            robots_value='', is_noindex=False, expected_noindex=get_expected_noindex(route),
            noindex_correct=False, errors=[str(e)]
        )


def load_inventory(inventory_path: str) -> list[dict]:
    """Load pages inventory CSV"""
    routes = []
    with open(inventory_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            routes.append(row)
    return routes


def generate_report(results: list[PageAuditResult], output_path: str):
    """Generate markdown audit report"""
    passed = [r for r in results if not r.errors]
    failed = [r for r in results if r.errors]

    report = f"""# SEO Page Audit Report

**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**Total Pages**: {len(results)}
**Passed**: {len(passed)}
**Failed**: {len(failed)}

---

## Summary

| Metric | Count | Percentage |
|--------|-------|------------|
| Pages with title | {sum(1 for r in results if r.has_title)} | {sum(1 for r in results if r.has_title)*100//len(results)}% |
| Pages with description | {sum(1 for r in results if r.has_description)} | {sum(1 for r in results if r.has_description)*100//len(results)}% |
| Pages with canonical | {sum(1 for r in results if r.has_canonical)} | {sum(1 for r in results if r.has_canonical)*100//len(results)}% |
| Correct canonical | {sum(1 for r in results if r.canonical_correct)} | {sum(1 for r in results if r.canonical_correct)*100//len(results)}% |
| Correct noindex | {sum(1 for r in results if r.noindex_correct)} | {sum(1 for r in results if r.noindex_correct)*100//len(results)}% |

---

## Failed Pages

"""

    if failed:
        for r in failed:
            report += f"""### `{r.route}`

- **Status**: {r.status_code}
- **Title**: {r.title_value[:50] or 'MISSING'}
- **Canonical**: {r.canonical_value or 'MISSING'}
- **Noindex**: {'Yes' if r.is_noindex else 'No'} (expected: {'Yes' if r.expected_noindex else 'No'})
- **Errors**:
"""
            for error in r.errors:
                report += f"  - {error}\n"
            report += "\n"
    else:
        report += "*No failures detected!*\n\n"

    report += """---

## All Pages Detail

| Route | Status | Title | Canonical | Noindex | OG | Errors |
|-------|--------|-------|-----------|---------|----|----|
"""

    for r in results:
        status_emoji = "✅" if not r.errors else "❌"
        canonical_emoji = "✅" if r.canonical_correct else "❌"
        noindex_emoji = "✅" if r.noindex_correct else "❌"
        og_emoji = "✅" if (r.has_og_title and r.has_og_description) else "⚠️"
        errors_str = "; ".join(r.errors[:2]) if r.errors else "-"

        report += f"| `{r.route}` | {status_emoji} {r.status_code} | {r.has_title} | {canonical_emoji} | {noindex_emoji} | {og_emoji} | {errors_str} |\n"

    report += """

---

## Recommendations

### Critical (Fix Before Launch)

1. **Missing canonical tags**: Pages without self-referencing canonical tags risk duplicate content issues
2. **Wrong noindex rules**: Pages that should be indexed but have noindex will be removed from search
3. **Missing titles/descriptions**: Affects search snippets and CTR

### Important

1. **Missing OG tags**: Affects social sharing appearance
2. **Non-canonical host in canonical**: Should always use `https://tellyads.com`

---

*Report generated by audit-pages.py*
"""

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(report)


def main():
    parser = argparse.ArgumentParser(description='Audit pages for SEO compliance')
    parser.add_argument('--base-url', default='http://localhost:3000', help='Base URL to audit')
    parser.add_argument('--inventory', default='docs/seo/pages_inventory.csv', help='Path to inventory CSV')
    parser.add_argument('--output', default='docs/seo/pages_audit_report.md', help='Output report path')
    parser.add_argument('--timeout', type=int, default=30, help='Request timeout in seconds')
    args = parser.parse_args()

    print(f"SEO Page Audit")
    print(f"=" * 50)
    print(f"Base URL: {args.base_url}")
    print(f"Inventory: {args.inventory}")
    print()

    # Define routes to test
    # Static routes from inventory
    routes_to_test = [
        '/',
        '/browse',
        '/search',
        '/search?q=test',
        '/latest',
        '/brands',
        '/about',
        '/random',
        '/admin',
        '/categories',  # Expected to 404
    ]

    # Add sample dynamic routes if base URL is localhost
    if 'localhost' in args.base_url:
        # These would need actual slugs from the database
        pass

    results = []
    for route in routes_to_test:
        print(f"Auditing {route}...", end=' ')
        result = audit_page(args.base_url, route, args.timeout)
        status = "PASS" if not result.errors else "FAIL"
        print(f"{status} ({result.status_code})")
        results.append(result)

    print()
    print(f"Generating report: {args.output}")
    generate_report(results, args.output)

    # Summary
    passed = sum(1 for r in results if not r.errors)
    failed = len(results) - passed

    print()
    print(f"Results: {passed} passed, {failed} failed")

    return 0 if failed == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
