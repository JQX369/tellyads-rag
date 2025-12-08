# 10x SEO Roadmap: TellyAds Growth Strategy

**Last Updated:** 2025-12-08
**Goal:** Transform TellyAds from a migrated site to the #1 search result for TV commercial queries

---

## Vision

Make every TellyAds page "the best result on the internet" for its target query. Build programmatic content hubs that create an internal linking goldmine while providing genuine value to searchers.

---

## 30-Day Milestones (Foundation)

### Week 1-2: Migration Verification & Quick Wins

- [ ] **Run verification script** against production
  ```bash
  python scripts/seo/verify-migration.py --new-base https://tellyads.com
  ```
- [ ] **Submit sitemap to Google Search Console**
- [ ] **Request indexing** for top 50 highest-traffic pages
- [ ] **Fix any 404s or redirect chains** found in verification
- [ ] **Set up monitoring dashboards**
  - Google Search Console connected
  - Core Web Vitals tracking
  - Rank tracking for 20 key terms

### Week 2-3: Content Quality Foundation

- [ ] **Audit top 100 ad pages** for content quality
  - Ensure unique, descriptive titles
  - Add missing meta descriptions (generate from one_line_summary)
  - Verify H1 presence and uniqueness
- [ ] **Add thumbnail images** to ad pages (from S3 or generate)
- [ ] **Implement lazy-loading video embeds** for Core Web Vitals
- [ ] **Add alt text** to all images

### Week 3-4: Technical Quick Wins

- [ ] **Implement image sitemap** (separate sitemap for thumbnails)
- [ ] **Add hreflang** if targeting multiple regions
- [ ] **Optimize title templates** based on CTR data
- [ ] **Internal linking audit**
  - Add "Related Ads" section using embedding similarity
  - Link between brand pages
  - Cross-link decades/themes

**30-Day Success Metrics:**
- 100% of pages indexed (via GSC)
- 0 redirect chains
- Core Web Vitals: All green
- Impressions restored to pre-migration levels

---

## 60-Day Milestones (Growth)

### Programmatic Hub Pages

#### Brand Hub Pages (`/advertiser/{brand-slug}`)

Create dedicated pages for each brand with:
- [ ] Brand history/overview (auto-generated or manual)
- [ ] All ads from that brand (with filters by year, category)
- [ ] Related brands in same category
- [ ] Timeline visualization of brand's ad history

**Implementation:**
```
frontend/app/advertiser/[brand]/page.tsx
```

**Target:** Top 200 brands with 3+ ads

#### Year Hub Pages (`/year/{yyyy}`)

Create yearly archive pages with:
- [ ] Top ads from that year
- [ ] Category breakdown
- [ ] Notable trends/themes
- [ ] "This year in advertising" narrative

**Implementation:**
```
frontend/app/year/[year]/page.tsx
```

**Target:** Years 1980-2025

#### Decade Hub Pages (`/decade/{decade}`)

Enhanced decade pages with:
- [ ] Decade overview and advertising trends
- [ ] Top 10 most memorable ads
- [ ] Technology/format evolution
- [ ] Category leaders by decade

**Implementation:**
```
frontend/app/decade/[decade]/page.tsx
```

**Target:** 1950s, 1960s, 1970s, 1980s, 1990s, 2000s, 2010s, 2020s

### Content Enhancement

- [ ] **Generate transcripts** for all video ads (via Whisper)
- [ ] **Add schema markup** for transcripts
- [ ] **Create "watch time" badges** (e.g., "30 second ad")
- [ ] **Add social share cards** with auto-generated OG images

**60-Day Success Metrics:**
- 50+ new hub pages indexed
- 20% increase in impressions
- 10% increase in click-through rate
- Average position improvement for brand queries

---

## 90-Day Milestones (Scale)

### Advanced Content Features

#### Theme/Tag Hub Pages (`/theme/{tag}`)

- [ ] Christmas Ads collection
- [ ] Funny Ads collection
- [ ] Charity/PSA collection
- [ ] Music in Advertising collection
- [ ] Celebrity Endorsements collection

**Quality Control:** Only create if 10+ high-quality ads exist

#### Advertiser Comparison Pages

- [ ] "Nike vs Adidas: Ad Battle Through the Years"
- [ ] "Supermarket Ad Wars: Tesco vs Sainsbury's"
- [ ] Auto-generated based on competing brands in same category

#### Annual Awards/Rankings

- [ ] "Best Christmas Ads of [Year]"
- [ ] "Most Memorable Ads of the [Decade]"
- [ ] User-voted + AI-scored rankings

### Technical Multipliers

#### Segmented Sitemaps

```
/sitemap-index.xml
├── /sitemap-ads.xml (all ad pages)
├── /sitemap-brands.xml (brand hub pages)
├── /sitemap-years.xml (year hub pages)
├── /sitemap-themes.xml (theme hub pages)
└── /sitemap-images.xml (ad thumbnails)
```

#### 404 Capture Pipeline

- [ ] **Log all 404s** to database
- [ ] **Auto-suggest redirects** based on URL similarity
- [ ] **Weekly report** of missing pages with suggested fixes
- [ ] **Auto-create redirect** if high-confidence match found

#### Search Intent Optimization

- [ ] **Analyze GSC query data** weekly
- [ ] **Identify gaps** between searched queries and existing pages
- [ ] **Create pages targeting** high-volume, low-competition queries
- [ ] **A/B test titles** based on CTR

**90-Day Success Metrics:**
- 200+ hub pages indexed
- 50% increase in organic traffic
- Top 3 ranking for 10+ brand name queries
- Featured snippets for "best [year] ads" queries

---

## Ongoing SEO Operations

### Weekly Tasks

- [ ] Review GSC for crawl errors
- [ ] Check 404 capture report
- [ ] Monitor Core Web Vitals
- [ ] Review new content indexing

### Monthly Tasks

- [ ] Rank tracking review
- [ ] Competitor analysis
- [ ] Content gap analysis
- [ ] Link profile review

### Quarterly Tasks

- [ ] Technical SEO audit
- [ ] Content audit (thin content, duplicates)
- [ ] Schema markup validation
- [ ] Sitemap health check

---

## Priority Matrix

### High Impact, Low Effort (Do First)
1. Fix any redirect chains found in verification
2. Add image sitemap
3. Optimize title tags based on CTR
4. Internal linking improvements

### High Impact, High Effort (Plan & Execute)
1. Brand hub pages
2. Year/Decade hub pages
3. Transcript generation for all ads
4. 404 capture pipeline

### Low Impact, Low Effort (Quick Wins)
1. Add missing meta descriptions
2. Social share card generation
3. Breadcrumb improvements
4. FAQ schema on about page

### Low Impact, High Effort (Deprioritize)
1. Multiple language support
2. Complex comparison pages
3. User-generated content features

---

## Technical Implementation Notes

### New Routes Required

```
frontend/app/
├── advertiser/[brand]/page.tsx       # Brand hub
├── year/[year]/page.tsx              # Year hub
├── decade/[decade]/page.tsx          # Decade hub
├── theme/[tag]/page.tsx              # Theme hub
└── compare/[brands]/page.tsx         # Comparison pages
```

### Database Changes

Consider adding:
```sql
-- Brand metadata for hub pages
ALTER TABLE ads ADD COLUMN brand_slug VARCHAR(255);
CREATE INDEX idx_ads_brand_slug ON ads(brand_slug);

-- Ad collections/lists
CREATE TABLE ad_collections (
  id UUID PRIMARY KEY,
  slug VARCHAR(255) UNIQUE,
  title VARCHAR(500),
  description TEXT,
  ad_ids UUID[],
  is_featured BOOLEAN DEFAULT false,
  created_at TIMESTAMP DEFAULT NOW()
);
```

### Caching Strategy

- Hub pages: ISR with 1-hour revalidation
- Ad detail pages: ISR with 24-hour revalidation
- Sitemaps: 1-hour cache
- Search results: No cache (dynamic)

---

## Success Metrics Dashboard

Track weekly:

| Metric | Baseline | 30-Day | 60-Day | 90-Day |
|--------|----------|--------|--------|--------|
| Indexed Pages | TBD | +100% | +150% | +200% |
| Organic Impressions | TBD | Same | +20% | +50% |
| Organic Clicks | TBD | Same | +15% | +40% |
| Avg Position | TBD | Same | -2 | -5 |
| Core Web Vitals | TBD | Green | Green | Green |
| Featured Snippets | 0 | 0 | 2 | 10 |

---

## Appendix: Competitor Analysis

### Key Competitors
- Archive.org TV News Archive
- Ads of the World (adsoftheworld.com)
- YouTube (brand channels)
- Individual brand websites

### Competitive Advantages
1. **Focus:** UK TV commercials specifically
2. **Depth:** Decades of historical content
3. **Metadata:** Rich AI-extracted data
4. **Search:** Semantic search capabilities
5. **Speed:** Modern tech stack

### Opportunities
- "Best [brand] ads" queries largely uncontested
- Year-specific ad queries have low competition
- Christmas ad queries highly seasonal but valuable
- Brand comparison queries unexploited
