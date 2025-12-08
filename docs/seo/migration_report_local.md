# SEO Migration Verification Report

**Generated:** 2025-12-08T16:46:01.740333
**Target:** http://localhost:3000
**Overall Status:** FAIL

## Summary

| Result | Count |
|--------|-------|
| PASS | 3 |
| FAIL | 3 |
| Total | 6 |

## Test Results

### P0 - Critical

####  Robots.txt: PASS

robots.txt correctly configured

**Details:**
- Sitemap referenced
- Legacy paths allowed
- Private paths blocked

####  Sitemap: FAIL

12 issues found

**Details:**
- URLs returning non-200: 17
-   - https://tellyads.com/latest (error: None)
-   - https://tellyads.com/brands (error: None)
-   - https://tellyads.com/about (error: None)
-   - https://tellyads.com/advert/mumford-26-sons/sigh-no-more (error: None)
-   - https://tellyads.com/advert/playcom/dvd-box-sets (error: None)
- URLs with different canonical (potential redirect): 33
-   - https://tellyads.com -> https://www.tellyads.com
-   - https://tellyads.com/browse -> https://www.tellyads.com/browse
-   - https://tellyads.com/search -> https://www.tellyads.com/search
-   - https://tellyads.com/advert/warner-bros/sherlock-holmes -> https://www.tellyads.com/advert/warner-bros/sherlock-holmes
-   - https://tellyads.com/advert/primula/enjoy-primula-this-christmas -> https://www.tellyads.com/advert/primula/enjoy-primula-this-christmas

####  Host Canonical: PASS

Skipped (--skip-host-check)

####  Redirect Chains: PASS

No redirect chains found

**Details:**
- Tested 9 legacy URLs

####  Meta Tags: FAIL

1 meta tag issues

**Details:**
- /search: has noindex on canonical page!

### P1 - High

####  Canonical Tags: FAIL

6 canonical issues

**Details:**
- /: missing canonical tag
- /browse: missing canonical tag
- /search: missing canonical tag
- /latest: not accessible (HTTPConnectionPool(host='localhost', port=3000): Read timed out.)
- /brands: not accessible (HTTPConnectionPool(host='localhost', port=3000): Read timed out.)
- /about: missing canonical tag

## Failed URLs

URLs that failed verification (fix these before launch):

- `  - https://tellyads.com/latest (error: None)`
- `  - https://tellyads.com/brands (error: None)`
- `  - https://tellyads.com/about (error: None)`
- `  - https://tellyads.com/advert/mumford-26-sons/sigh-no-more (error: None)`
- `  - https://tellyads.com/advert/playcom/dvd-box-sets (error: None)`
- `  - https://tellyads.com -> https://www.tellyads.com`
- `  - https://tellyads.com/browse -> https://www.tellyads.com/browse`
- `  - https://tellyads.com/search -> https://www.tellyads.com/search`
- `  - https://tellyads.com/advert/warner-bros/sherlock-holmes -> https://www.tellyads.com/advert/warner-bros/sherlock-holmes`
- `  - https://tellyads.com/advert/primula/enjoy-primula-this-christmas -> https://www.tellyads.com/advert/primula/enjoy-primula-this-christmas`
- `/: missing canonical tag`
- `/browse: missing canonical tag`
- `/search: missing canonical tag`
- `/latest: not accessible (HTTPConnectionPool(host='localhost', port=3000): Read timed out.)`
- `/brands: not accessible (HTTPConnectionPool(host='localhost', port=3000): Read timed out.)`
- `/about: missing canonical tag`
- `/search: has noindex on canonical page!`

## Next Steps

1. **Fix P0 issues immediately** - these block migration
2. Fix P1 issues before launch
3. P2 issues can be fixed post-launch
4. Re-run verification after fixes: `python scripts/seo/verify-migration.py`
