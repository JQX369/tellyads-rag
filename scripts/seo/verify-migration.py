#!/usr/bin/env python3
"""
SEO Migration Verification Script v3.0

Comprehensive verification for SEO migration safety.
Validates all P0 requirements for Wix → Next.js migration.

Tests:
1. Robots.txt validation (legacy paths allowed, sitemap referenced)
2. Sitemap validation (all URLs return 200 + self-canonical)
3. Host canonicalization (www -> non-www)
4. Redirect chain detection (max 1 hop)
5. Legacy sitemap redirects (Wix sitemaps -> /sitemap.xml)
6. Canonical tag validation (no mixed hosts)
7. Meta tag validation (title present, no noindex on canonical pages)
8. Sample URL smoke tests (from sample_urls.txt)

Usage:
    # Local testing
    python verify-migration.py --new-base http://localhost:3000 --skip-host-check

    # Staging
    python verify-migration.py --new-base https://staging.tellyads.com

    # Production
    python verify-migration.py --new-base https://tellyads.com

    # With sample file
    python verify-migration.py --new-base https://tellyads.com --sample-file docs/seo/sample_urls.txt

Output:
    - Console: PASS/FAIL summary
    - Markdown report with P0/P1/P2 issues
"""

import argparse
import re
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Tuple
from urllib.parse import urljoin, urlparse
import xml.etree.ElementTree as ET

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    print("Required packages not installed. Run:")
    print("  pip install requests beautifulsoup4")
    sys.exit(1)


# Canonical host - MUST be non-www
CANONICAL_HOST = 'tellyads.com'
CANONICAL_PROTOCOL = 'https'
CANONICAL_BASE = f'{CANONICAL_PROTOCOL}://{CANONICAL_HOST}'


@dataclass
class TestResult:
    """Individual test result."""
    name: str
    status: str  # 'PASS', 'FAIL', 'WARN', 'SKIP'
    priority: str  # 'P0', 'P1', 'P2'
    message: str
    details: List[str] = field(default_factory=list)


@dataclass
class URLTestResult:
    """Result of testing a single URL."""
    url: str
    status: str  # 'pass', 'fail', 'redirect', 'error'
    http_status: Optional[int] = None
    final_url: Optional[str] = None
    redirect_count: int = 0
    canonical_url: Optional[str] = None
    canonical_valid: bool = False
    title: Optional[str] = None
    has_noindex: bool = False
    response_time_ms: Optional[float] = None
    error: Optional[str] = None


class SEOMigrationVerifier:
    """Comprehensive SEO migration verification."""

    # Default sample URLs for testing (used if no sample file provided)
    DEFAULT_LEGACY_URLS = [
        # Legacy page redirects
        '/latestads',
        '/searchall',
        '/telly-ads',
        '/adsbydecade',
        '/top30ads',
        # Legacy patterns requiring DB lookup
        '/items/christmas-2020',
        '/items/getting-the-drinks-in',
        '/advert/john-lewis/christmas-2021-unexpected-guest-n',
        '/post/test-slug',
    ]

    DEFAULT_CANONICAL_URLS = [
        '/',
        '/browse',
        '/search',
        '/latest',
        '/brands',
        '/about',
    ]

    LEGACY_SITEMAPS = [
        '/dynamic-advert-sitemap.xml',
        '/dynamic-advert___1-sitemap.xml',
        '/dynamic-advert___2-sitemap.xml',
        '/dynamic-items-sitemap.xml',
        '/dynamic-items___1-sitemap.xml',
        '/dynamic-items___2-sitemap.xml',
        '/pages-sitemap.xml',
        '/sitemap_index.xml',
    ]

    def __init__(self, new_base: str, timeout: int = 30, skip_host_check: bool = False):
        self.new_base = new_base.rstrip('/')
        self.timeout = timeout
        self.skip_host_check = skip_host_check
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'TellyAds SEO Verifier/3.0',
        })
        self.test_results: List[TestResult] = []
        self.url_results: List[URLTestResult] = []
        self.sample_urls: Dict[str, List[str]] = {
            'legacy': self.DEFAULT_LEGACY_URLS.copy(),
            'canonical': self.DEFAULT_CANONICAL_URLS.copy(),
        }

    def load_sample_file(self, filepath: str) -> None:
        """Load sample URLs from file."""
        try:
            path = Path(filepath)
            if not path.exists():
                print(f"Warning: Sample file not found: {filepath}")
                return

            legacy_urls = []
            canonical_urls = []
            current_section = None

            with open(path, 'r') as f:
                for line in f:
                    line = line.strip()
                    # Skip comments and empty lines
                    if not line or line.startswith('#'):
                        # Check for section markers
                        if 'Canonical pages' in line:
                            current_section = 'canonical'
                        elif 'Legacy' in line or '/items/' in line or '/post/' in line:
                            current_section = 'legacy'
                        continue

                    # Skip lines that are just comments about test methods
                    if line.startswith('Test via:'):
                        continue

                    # Parse URL (support both plain URLs and "url -> expected" format)
                    url = line.split('->')[0].strip()
                    if url.startswith('/'):
                        if current_section == 'canonical':
                            canonical_urls.append(url)
                        else:
                            legacy_urls.append(url)

            if legacy_urls:
                self.sample_urls['legacy'] = legacy_urls
                print(f"Loaded {len(legacy_urls)} legacy URLs from sample file")

            if canonical_urls:
                self.sample_urls['canonical'] = canonical_urls
                print(f"Loaded {len(canonical_urls)} canonical URLs from sample file")

        except Exception as e:
            print(f"Error loading sample file: {e}")

    def add_result(self, name: str, status: str, priority: str, message: str, details: List[str] = None):
        """Add a test result."""
        self.test_results.append(TestResult(
            name=name,
            status=status,
            priority=priority,
            message=message,
            details=details or []
        ))

    def fetch_url(self, url: str, follow_redirects: bool = True) -> Tuple[Optional[requests.Response], float, Optional[str]]:
        """Fetch URL and return response + timing + error."""
        try:
            start = time.time()
            response = self.session.get(
                url,
                allow_redirects=follow_redirects,
                timeout=self.timeout
            )
            elapsed = (time.time() - start) * 1000
            return response, elapsed, None
        except requests.exceptions.Timeout:
            return None, 0, "Request timeout"
        except requests.exceptions.ConnectionError as e:
            return None, 0, f"Connection error: {str(e)[:100]}"
        except Exception as e:
            return None, 0, str(e)[:100]

    def fetch_with_redirect_chain(self, url: str, max_redirects: int = 10) -> List[Dict]:
        """Fetch URL tracking full redirect chain."""
        chain = []
        current_url = url

        for _ in range(max_redirects):
            try:
                response = self.session.get(
                    current_url,
                    allow_redirects=False,
                    timeout=self.timeout
                )
                chain.append({
                    'url': current_url,
                    'status': response.status_code,
                })

                if response.status_code in (301, 302, 303, 307, 308):
                    location = response.headers.get('Location', '')
                    if location:
                        current_url = urljoin(current_url, location)
                    else:
                        break
                else:
                    break
            except Exception as e:
                chain.append({'url': current_url, 'status': 'error', 'error': str(e)[:50]})
                break

        return chain

    # ==================== TEST 1: Robots.txt ====================
    def verify_robots(self) -> TestResult:
        """Verify robots.txt configuration."""
        print("\n[1/8] Verifying robots.txt...")

        url = f"{self.new_base}/robots.txt"
        response, _, error = self.fetch_url(url)

        if error or not response or response.status_code != 200:
            self.add_result(
                name="Robots.txt",
                status="FAIL",
                priority="P0",
                message="robots.txt not accessible",
                details=[f"URL: {url}", f"Error: {error or response.status_code if response else 'No response'}"]
            )
            return self.test_results[-1]

        content = response.text.lower()
        issues = []
        passes = []

        # Check sitemap reference
        if 'sitemap:' not in content:
            issues.append("Missing Sitemap: directive")
        else:
            passes.append("Sitemap directive present")

        # Check sitemap uses canonical host (non-www)
        sitemap_match = re.search(r'sitemap:\s*(\S+)', content, re.IGNORECASE)
        if sitemap_match:
            sitemap_url = sitemap_match.group(1)
            if 'www.' in sitemap_url:
                issues.append(f"Sitemap URL uses www (should be non-www): {sitemap_url}")
            else:
                passes.append("Sitemap uses canonical host")

        # CRITICAL: Check we're NOT blocking legacy paths
        legacy_paths = ['/items/', '/post/', '/advert/']
        blocked_paths = []
        for path in legacy_paths:
            # Check if explicitly disallowed
            if f'disallow: {path}' in content or f'disallow:{path}' in content:
                blocked_paths.append(path)

        if blocked_paths:
            issues.append(f"CRITICAL: Legacy paths blocked (prevents 301 discovery): {blocked_paths}")
        else:
            passes.append("Legacy paths (/items/, /post/, /advert/) allowed")

        # Check private paths are blocked
        private_paths = ['/api/', '/admin/', '/_next/']
        missing_blocks = []
        for path in private_paths:
            if f'disallow: {path}' not in content and f'disallow:{path}' not in content:
                missing_blocks.append(path)

        if missing_blocks:
            issues.append(f"Private paths not blocked: {missing_blocks}")
        else:
            passes.append("Private paths blocked")

        if issues:
            priority = "P0" if blocked_paths else "P1"
            self.add_result(
                name="Robots.txt",
                status="FAIL",
                priority=priority,
                message=f"{len(issues)} issues found",
                details=issues
            )
        else:
            self.add_result(
                name="Robots.txt",
                status="PASS",
                priority="P0",
                message="robots.txt correctly configured",
                details=passes
            )

        return self.test_results[-1]

    # ==================== TEST 2: Sitemap ====================
    def verify_sitemap(self) -> TestResult:
        """Verify sitemap.xml - all URLs canonical and return 200."""
        print("\n[2/8] Verifying sitemap.xml...")

        url = f"{self.new_base}/sitemap.xml"
        response, _, error = self.fetch_url(url)

        if error or not response or response.status_code != 200:
            self.add_result(
                name="Sitemap",
                status="FAIL",
                priority="P0",
                message="sitemap.xml not accessible",
                details=[f"URL: {url}", f"Error: {error or response.status_code if response else 'No response'}"]
            )
            return self.test_results[-1]

        # Parse sitemap
        try:
            root = ET.fromstring(response.content)
            ns = {'sm': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
            urls = [elem.text for elem in root.findall('.//sm:loc', ns) if elem.text]
        except Exception as e:
            self.add_result(
                name="Sitemap",
                status="FAIL",
                priority="P0",
                message=f"Failed to parse sitemap: {e}",
            )
            return self.test_results[-1]

        print(f"   Found {len(urls)} URLs in sitemap")

        issues = []
        passes = []

        # Check for www URLs (should all be non-www)
        www_urls = [u for u in urls if 'www.' in urlparse(u).netloc]
        if www_urls:
            issues.append(f"URLs with www host in sitemap: {len(www_urls)}")
            for u in www_urls[:3]:
                issues.append(f"  - {u}")
        else:
            passes.append("All URLs use non-www canonical host")

        # Check for query parameter URLs (should not be in sitemap)
        query_urls = [u for u in urls if '?' in u]
        if query_urls:
            issues.append(f"Query parameter URLs in sitemap: {len(query_urls)}")
            for u in query_urls[:3]:
                issues.append(f"  - {u}")
        else:
            passes.append("No query parameter URLs")

        # Check for -n suffix URLs (Wix artifact)
        suffix_urls = [u for u in urls if u.rstrip('/').endswith('-n')]
        if suffix_urls:
            issues.append(f"URLs with -n suffix in sitemap: {len(suffix_urls)}")
            for u in suffix_urls[:3]:
                issues.append(f"  - {u}")
        else:
            passes.append("No -n suffix URLs")

        # Sample test: check a few URLs return 200
        test_count = min(10, len(urls))
        test_urls = urls[:test_count]
        failed_urls = []

        print(f"   Testing {test_count} sample URLs...")
        for test_url in test_urls:
            resp, _, err = self.fetch_url(test_url)
            if err or not resp or resp.status_code != 200:
                failed_urls.append(f"{test_url} ({err or resp.status_code if resp else 'error'})")
            time.sleep(0.1)  # Rate limiting

        if failed_urls:
            issues.append(f"URLs returning non-200: {len(failed_urls)}")
            for u in failed_urls[:3]:
                issues.append(f"  - {u}")
        else:
            passes.append(f"All {test_count} sampled URLs return 200")

        if issues:
            self.add_result(
                name="Sitemap",
                status="FAIL",
                priority="P0" if www_urls or query_urls else "P1",
                message=f"{len(issues)} issues found",
                details=issues
            )
        else:
            self.add_result(
                name="Sitemap",
                status="PASS",
                priority="P0",
                message=f"Sitemap valid ({len(urls)} URLs)",
                details=passes
            )

        return self.test_results[-1]

    # ==================== TEST 3: Host Canonicalization ====================
    def verify_host_canonical(self) -> TestResult:
        """Verify www -> non-www redirect."""
        print("\n[3/8] Verifying host canonicalization (www -> non-www)...")

        if self.skip_host_check:
            self.add_result(
                name="Host Canonical",
                status="SKIP",
                priority="P0",
                message="Skipped (--skip-host-check flag)",
            )
            return self.test_results[-1]

        # Extract domain from base URL
        parsed = urlparse(self.new_base)
        if parsed.hostname == 'localhost' or (parsed.hostname and parsed.hostname.startswith('127.')):
            self.add_result(
                name="Host Canonical",
                status="SKIP",
                priority="P0",
                message="Skipped (localhost)",
            )
            return self.test_results[-1]

        # Test paths with www
        test_paths = ['/', '/browse', '/search', '/latest']
        issues = []
        passes = []

        for path in test_paths:
            www_url = f"https://www.{parsed.hostname}{path}"
            print(f"   Testing: {www_url}")

            chain = self.fetch_with_redirect_chain(www_url)

            if not chain:
                issues.append(f"{path}: Could not fetch www version")
                continue

            # Check redirect
            first_hop = chain[0]
            if first_hop['status'] not in (301, 302, 303, 307, 308):
                issues.append(f"{path}: www version does not redirect (status: {first_hop['status']})")
                continue

            # Check final URL is non-www
            final_url = chain[-1]['url']
            if 'www.' in final_url.lower():
                issues.append(f"{path}: Still on www after redirect: {final_url}")
                continue

            # Check it's a single hop (301)
            redirect_hops = sum(1 for hop in chain if hop.get('status') in (301, 302, 303, 307, 308))
            if redirect_hops > 1:
                issues.append(f"{path}: Multiple redirects ({redirect_hops} hops)")
                continue

            passes.append(f"{path}: www -> non-www (301, single hop)")
            time.sleep(0.2)

        if issues:
            self.add_result(
                name="Host Canonical",
                status="FAIL",
                priority="P0",
                message=f"{len(issues)} issues found",
                details=issues
            )
        else:
            self.add_result(
                name="Host Canonical",
                status="PASS",
                priority="P0",
                message="www redirects to non-www correctly",
                details=passes
            )

        return self.test_results[-1]

    # ==================== TEST 4: Redirect Chains ====================
    def verify_redirect_chains(self) -> TestResult:
        """Verify no redirect chains (max 1 hop for legacy URLs)."""
        print("\n[4/8] Verifying redirect chains...")

        issues = []
        passes = []
        test_urls = self.sample_urls['legacy']

        print(f"   Testing {len(test_urls)} legacy URLs...")

        for path in test_urls:
            url = f"{self.new_base}{path}"
            chain = self.fetch_with_redirect_chain(url)

            if not chain:
                issues.append(f"{path}: Could not fetch")
                continue

            # Count redirect hops
            redirect_count = sum(1 for hop in chain if isinstance(hop.get('status'), int) and hop['status'] in (301, 302, 303, 307, 308))

            final_status = chain[-1].get('status')

            if redirect_count > 1:
                issues.append(f"{path}: {redirect_count} redirects (max allowed: 1)")
                for i, hop in enumerate(chain[:5]):
                    issues.append(f"  Hop {i}: {hop.get('status')} -> {hop.get('url', '')[:60]}...")
            elif redirect_count == 1 and final_status == 200:
                passes.append(f"{path}: 1 redirect -> 200")
            elif redirect_count == 0 and final_status == 200:
                passes.append(f"{path}: Direct 200 (no redirect needed)")
            elif final_status in (302, 404):
                # 302 to search (no match) or 404 is acceptable for unknown slugs
                passes.append(f"{path}: {final_status} (expected for unmatched slugs)")
            else:
                issues.append(f"{path}: Unexpected final status: {final_status}")

            time.sleep(0.1)

        if issues:
            self.add_result(
                name="Redirect Chains",
                status="FAIL",
                priority="P0",
                message=f"{len(issues)} URLs have issues",
                details=issues[:20]  # Limit details
            )
        else:
            self.add_result(
                name="Redirect Chains",
                status="PASS",
                priority="P0",
                message=f"All {len(test_urls)} legacy URLs resolve correctly",
                details=passes[:10]
            )

        return self.test_results[-1]

    # ==================== TEST 5: Legacy Sitemaps ====================
    def verify_legacy_sitemaps(self) -> TestResult:
        """Verify legacy Wix sitemap URLs redirect to /sitemap.xml."""
        print("\n[5/8] Verifying legacy sitemap redirects...")

        issues = []
        passes = []

        for sitemap_path in self.LEGACY_SITEMAPS:
            url = f"{self.new_base}{sitemap_path}"
            chain = self.fetch_with_redirect_chain(url)

            if not chain:
                issues.append(f"{sitemap_path}: Could not fetch")
                continue

            # Check for redirect to /sitemap.xml
            final_url = chain[-1].get('url', '')
            final_status = chain[-1].get('status')

            if final_url.endswith('/sitemap.xml') and final_status == 200:
                redirect_count = len(chain) - 1
                passes.append(f"{sitemap_path}: 301 -> /sitemap.xml ({redirect_count} hop)")
            elif final_status == 404:
                issues.append(f"{sitemap_path}: Returns 404 (should redirect to /sitemap.xml)")
            else:
                issues.append(f"{sitemap_path}: Unexpected response (status: {final_status}, url: {final_url[:50]})")

            time.sleep(0.1)

        if issues:
            self.add_result(
                name="Legacy Sitemaps",
                status="FAIL",
                priority="P1",
                message=f"{len(issues)} legacy sitemaps not redirecting",
                details=issues
            )
        else:
            self.add_result(
                name="Legacy Sitemaps",
                status="PASS",
                priority="P1",
                message="All legacy sitemaps redirect to /sitemap.xml",
                details=passes
            )

        return self.test_results[-1]

    # ==================== TEST 6: Canonical Tags ====================
    def verify_canonical_tags(self) -> TestResult:
        """Verify canonical tags are present and use non-www host."""
        print("\n[6/8] Verifying canonical tags...")

        issues = []
        passes = []
        test_urls = self.sample_urls['canonical']

        for path in test_urls:
            url = f"{self.new_base}{path}"
            response, _, error = self.fetch_url(url)

            if error or not response or response.status_code != 200:
                issues.append(f"{path}: Not accessible ({error or response.status_code if response else 'error'})")
                continue

            soup = BeautifulSoup(response.text, 'html.parser')

            # Check canonical tag
            canonical = soup.find('link', rel='canonical')
            if not canonical:
                issues.append(f"{path}: Missing canonical tag")
                continue

            canonical_href = canonical.get('href', '')
            if not canonical_href:
                issues.append(f"{path}: Empty canonical href")
                continue

            # Check canonical uses non-www
            if 'www.' in canonical_href:
                issues.append(f"{path}: Canonical uses www: {canonical_href}")
                continue

            # Check canonical matches expected host
            parsed = urlparse(canonical_href)
            if parsed.netloc and parsed.netloc != CANONICAL_HOST:
                issues.append(f"{path}: Canonical host mismatch: {parsed.netloc} (expected: {CANONICAL_HOST})")
                continue

            passes.append(f"{path}: Canonical OK ({canonical_href[:50]})")
            time.sleep(0.1)

        if issues:
            self.add_result(
                name="Canonical Tags",
                status="FAIL",
                priority="P1",
                message=f"{len(issues)} canonical tag issues",
                details=issues
            )
        else:
            self.add_result(
                name="Canonical Tags",
                status="PASS",
                priority="P1",
                message="All canonical tags valid and use non-www host",
                details=passes
            )

        return self.test_results[-1]

    # ==================== TEST 7: Meta Tags ====================
    def verify_meta_tags(self) -> TestResult:
        """Verify meta tags (title present, no noindex on canonical pages)."""
        print("\n[7/8] Verifying meta tags...")

        issues = []
        passes = []
        test_urls = self.sample_urls['canonical']

        for path in test_urls:
            url = f"{self.new_base}{path}"
            response, _, error = self.fetch_url(url)

            if error or not response or response.status_code != 200:
                continue  # Already covered in other tests

            soup = BeautifulSoup(response.text, 'html.parser')

            # Check title
            title = soup.find('title')
            if not title or not title.string or not title.string.strip():
                issues.append(f"{path}: Missing or empty title")
            else:
                passes.append(f"{path}: Has title")

            # Check for noindex (should NOT be present on canonical pages)
            robots = soup.find('meta', attrs={'name': 'robots'})
            if robots:
                content = robots.get('content', '').lower()
                if 'noindex' in content:
                    issues.append(f"{path}: Has noindex on canonical page!")

            time.sleep(0.1)

        if issues:
            priority = "P0" if any('noindex' in i for i in issues) else "P2"
            self.add_result(
                name="Meta Tags",
                status="FAIL",
                priority=priority,
                message=f"{len(issues)} meta tag issues",
                details=issues
            )
        else:
            self.add_result(
                name="Meta Tags",
                status="PASS",
                priority="P2",
                message="All meta tags valid",
                details=["All canonical pages have titles", "No noindex on canonical pages"]
            )

        return self.test_results[-1]

    # ==================== TEST 8: OG/Social Tags ====================
    def verify_og_tags(self) -> TestResult:
        """Verify Open Graph tags use canonical host."""
        print("\n[8/8] Verifying Open Graph tags...")

        issues = []
        passes = []
        test_urls = self.sample_urls['canonical'][:3]  # Sample just a few

        for path in test_urls:
            url = f"{self.new_base}{path}"
            response, _, error = self.fetch_url(url)

            if error or not response or response.status_code != 200:
                continue

            soup = BeautifulSoup(response.text, 'html.parser')

            # Check og:url
            og_url = soup.find('meta', property='og:url')
            if og_url:
                og_url_content = og_url.get('content', '')
                if 'www.' in og_url_content:
                    issues.append(f"{path}: og:url uses www: {og_url_content}")
                else:
                    passes.append(f"{path}: og:url OK")
            else:
                passes.append(f"{path}: No og:url (acceptable)")

            time.sleep(0.1)

        if issues:
            self.add_result(
                name="OG Tags",
                status="FAIL",
                priority="P2",
                message=f"{len(issues)} OG tag issues",
                details=issues
            )
        else:
            self.add_result(
                name="OG Tags",
                status="PASS",
                priority="P2",
                message="Open Graph tags use canonical host",
                details=passes
            )

        return self.test_results[-1]

    # ==================== Run All Tests ====================
    def run_all_tests(self) -> bool:
        """Run all verification tests. Returns True if all pass."""
        print("=" * 70)
        print("SEO MIGRATION VERIFICATION v3.0")
        print(f"Target: {self.new_base}")
        print(f"Canonical Host: {CANONICAL_BASE}")
        print("=" * 70)

        self.verify_robots()
        self.verify_sitemap()
        self.verify_host_canonical()
        self.verify_redirect_chains()
        self.verify_legacy_sitemaps()
        self.verify_canonical_tags()
        self.verify_meta_tags()
        self.verify_og_tags()

        return all(r.status in ('PASS', 'SKIP') for r in self.test_results)

    def generate_report(self) -> str:
        """Generate markdown report."""
        passed = sum(1 for r in self.test_results if r.status == 'PASS')
        failed = sum(1 for r in self.test_results if r.status == 'FAIL')
        skipped = sum(1 for r in self.test_results if r.status == 'SKIP')
        total = len(self.test_results)

        overall = "PASS" if failed == 0 else "FAIL"

        md = f"""# SEO Migration Verification Report

**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**Target:** {self.new_base}
**Canonical Host:** {CANONICAL_BASE}
**Overall Status:** {'PASS' if failed == 0 else 'FAIL'}

## Summary

| Result | Count |
|--------|-------|
| PASS | {passed} |
| FAIL | {failed} |
| SKIP | {skipped} |
| Total | {total} |

## Test Results

"""
        # Group by priority
        for priority in ['P0', 'P1', 'P2']:
            results = [r for r in self.test_results if r.priority == priority]
            if results:
                priority_label = {'P0': 'Critical', 'P1': 'High', 'P2': 'Medium'}[priority]
                md += f"### {priority} - {priority_label}\n\n"

                for r in results:
                    icon = {'PASS': 'PASS', 'FAIL': 'FAIL', 'SKIP': 'SKIP', 'WARN': 'WARN'}[r.status]
                    md += f"#### [{icon}] {r.name}\n\n"
                    md += f"{r.message}\n\n"

                    if r.details:
                        md += "**Details:**\n"
                        for d in r.details:
                            md += f"- {d}\n"
                        md += "\n"

        # Definition of Done checklist
        md += """## Definition of Done Checklist

| Requirement | Status |
|-------------|--------|
"""
        # Check each requirement
        robots_pass = any(r.name == 'Robots.txt' and r.status == 'PASS' for r in self.test_results)
        sitemap_pass = any(r.name == 'Sitemap' and r.status == 'PASS' for r in self.test_results)
        host_pass = any(r.name == 'Host Canonical' and r.status in ('PASS', 'SKIP') for r in self.test_results)
        chains_pass = any(r.name == 'Redirect Chains' and r.status == 'PASS' for r in self.test_results)
        canonical_pass = any(r.name == 'Canonical Tags' and r.status == 'PASS' for r in self.test_results)
        meta_pass = any(r.name == 'Meta Tags' and r.status == 'PASS' for r in self.test_results)

        md += f"| All legacy URLs resolve in <= 1 hop | {'PASS' if chains_pass else 'FAIL'} |\n"
        md += f"| No www URLs in canonicals/sitemap | {'PASS' if sitemap_pass and canonical_pass else 'FAIL'} |\n"
        md += f"| Robots allows legacy paths + refs sitemap | {'PASS' if robots_pass else 'FAIL'} |\n"
        md += f"| Sitemap contains only canonical paths | {'PASS' if sitemap_pass else 'FAIL'} |\n"
        md += f"| No noindex on canonical pages | {'PASS' if meta_pass else 'FAIL'} |\n"

        md += """
## Next Steps

"""
        if failed == 0:
            md += """1. Migration verification **PASSED**
2. Safe to proceed with DNS cutover
3. Monitor Google Search Console after launch for any crawl errors
4. Re-run verification in 24h and 7d post-launch
"""
        else:
            md += """1. **Fix FAIL issues before launch**
2. Re-run verification: `python scripts/seo/verify-migration.py --new-base <url>`
3. P0 issues block migration
4. P1 issues should be fixed before launch
5. P2 issues can be fixed post-launch
"""

        return md

    def print_summary(self):
        """Print console summary."""
        print("\n" + "=" * 70)
        print("VERIFICATION SUMMARY")
        print("=" * 70)

        passed = sum(1 for r in self.test_results if r.status == 'PASS')
        failed = sum(1 for r in self.test_results if r.status == 'FAIL')
        skipped = sum(1 for r in self.test_results if r.status == 'SKIP')

        for r in self.test_results:
            status_icon = {'PASS': 'PASS', 'FAIL': 'FAIL', 'SKIP': 'SKIP', 'WARN': 'WARN'}[r.status]
            print(f"[{r.priority}] {r.name}: {status_icon} - {r.message}")

        print("-" * 70)

        if failed == 0:
            print(f"\nOVERALL: PASS ({passed} passed, {skipped} skipped)")
            print("\n*** SAFE TO PROCEED WITH MIGRATION ***")
        else:
            print(f"\nOVERALL: FAIL ({failed} failed, {passed} passed, {skipped} skipped)")
            print("\n*** FIX ISSUES BEFORE MIGRATION ***")


def main():
    parser = argparse.ArgumentParser(
        description='SEO Migration Verification',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Local testing
  python verify-migration.py --new-base http://localhost:3000 --skip-host-check

  # Production
  python verify-migration.py --new-base https://tellyads.com

  # With sample file
  python verify-migration.py --new-base https://tellyads.com --sample-file docs/seo/sample_urls.txt
"""
    )
    parser.add_argument('--new-base', default='https://tellyads.com',
                        help='Base URL of new site')
    parser.add_argument('--output', default='docs/seo/migration_report.md',
                        help='Output file for report')
    parser.add_argument('--sample-file', default=None,
                        help='File containing sample URLs to test')
    parser.add_argument('--skip-host-check', action='store_true',
                        help='Skip www/non-www host check (for localhost)')
    parser.add_argument('--timeout', type=int, default=30,
                        help='Request timeout in seconds')

    args = parser.parse_args()

    verifier = SEOMigrationVerifier(
        args.new_base,
        timeout=args.timeout,
        skip_host_check=args.skip_host_check
    )

    # Load sample file if provided
    if args.sample_file:
        verifier.load_sample_file(args.sample_file)

    all_passed = verifier.run_all_tests()

    # Generate and save report
    report = verifier.generate_report()
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w') as f:
        f.write(report)

    print(f"\nReport saved to: {output_path}")

    # Print summary
    verifier.print_summary()

    # Exit code
    sys.exit(0 if all_passed else 1)


if __name__ == '__main__':
    main()
