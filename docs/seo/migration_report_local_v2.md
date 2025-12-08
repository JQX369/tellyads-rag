# SEO Migration Verification Report

**Generated:** 2025-12-08T16:54:26.544004
**Target:** http://localhost:3000
**Overall Status:** FAIL

## Summary

| Result | Count |
|--------|-------|
| PASS | 4 |
| FAIL | 2 |
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

### P1 - High

####  Canonical Tags: FAIL

6 canonical issues

**Details:**
- /: canonical points to URL that redirects: https://tellyads.com
- /browse: canonical points to URL that redirects: https://tellyads.com/browse
- /search: canonical points to URL that redirects: https://tellyads.com/search
- /latest: canonical points to URL that redirects: https://tellyads.com/latest
- /brands: canonical points to URL that redirects: https://tellyads.com/brands
- /about: canonical points to URL that redirects: https://tellyads.com/about

### P2 - Medium

####  Meta Tags: PASS

All meta tags valid

**Details:**
- Tested 6 URLs
- All have titles
- No noindex on canonical pages

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
- `/: canonical points to URL that redirects: https://tellyads.com`
- `/browse: canonical points to URL that redirects: https://tellyads.com/browse`
- `/search: canonical points to URL that redirects: https://tellyads.com/search`
- `/latest: canonical points to URL that redirects: https://tellyads.com/latest`
- `/brands: canonical points to URL that redirects: https://tellyads.com/brands`
- `/about: canonical points to URL that redirects: https://tellyads.com/about`

## Next Steps

1. **Fix P0 issues immediately** - these block migration
2. Fix P1 issues before launch
3. P2 issues can be fixed post-launch
4. Re-run verification after fixes: `python scripts/seo/verify-migration.py`
