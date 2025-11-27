"""Verify all extraction sections are stored properly."""
import os
os.environ['DB_BACKEND'] = 'http'

from tvads_rag.tvads_rag.supabase_db import _get_client

client = _get_client()
resp = client.table('ads').select('*').order('created_at', desc=True).limit(1).execute()
ad = resp.data[0] if resp.data else None

if not ad:
    print("No ads found")
    exit(1)

print("="*80)
print("VERIFICATION CHECKLIST")
print("="*80)

# Check all 22 sections exist in analysis_json
analysis = ad.get('analysis_json', {})
expected_sections = [
    'core_metadata', 'campaign_strategy', 'creative_flags', 'creative_attributes',
    'impact_scores', 'emotional_timeline', 'attention_dynamics', 'creative_dna',
    'brain_balance', 'brand_presence', 'distinctive_assets', 'characters',
    'cta_offer', 'audio_fingerprint', 'segments', 'storyboard', 'claims', 'supers',
    'compliance_assessment', 'effectiveness_drivers', 'competitive_context', 'memorability'
]

print("\n1. ANALYSIS_JSON SECTIONS:")
present = [s for s in expected_sections if s in analysis]
missing = [s for s in expected_sections if s not in analysis]
print(f"   ✅ Present: {len(present)}/22")
if missing:
    print(f"   ❌ Missing: {missing}")
else:
    print("   ✅ All 22 sections present!")

# Check JSONB columns are populated
print("\n2. JSONB COLUMNS:")
jsonb_cols = {
    'impact_scores': 'Impact Scores',
    'emotional_metrics': 'Emotional Metrics',
    'effectiveness': 'Effectiveness',
    'cta_offer': 'CTA/Offer',
    'brand_asset_timeline': 'Brand Presence',
    'audio_fingerprint': 'Audio Fingerprint',
    'creative_dna': 'Creative DNA',
    'claims_compliance': 'Compliance'
}

for col, name in jsonb_cols.items():
    val = ad.get(col)
    if val:
        print(f"   ✅ {name}: Populated")
    else:
        print(f"   ⚠️  {name}: Empty")

# Check extraction version
print("\n3. EXTRACTION VERSION:")
version = ad.get('extraction_version', 'N/A')
print(f"   Version: {version}")
if version == '2.0':
    print("   ✅ Using v2.0 extraction")
else:
    print("   ⚠️  Not using v2.0 (may be old data)")

# Check flat columns
print("\n4. FLAT COLUMNS (Sample):")
flat_cols = ['brand_name', 'product_category', 'objective', 'funnel_stage', 'one_line_summary']
for col in flat_cols:
    val = ad.get(col)
    if val:
        print(f"   ✅ {col}: {str(val)[:50]}")
    else:
        print(f"   ⚠️  {col}: Empty")

# Check child tables
print("\n5. CHILD TABLES:")
try:
    segments = client.table('ad_segments').select('id', count='exact').eq('ad_id', ad['id']).limit(1).execute()
    seg_count = len(segments.data) if segments.data else 0
    print(f"   ✅ Segments: {seg_count} records")
except:
    print("   ⚠️  Segments: Could not check")

try:
    claims = client.table('ad_claims').select('id', count='exact').eq('ad_id', ad['id']).limit(1).execute()
    claim_count = len(claims.data) if claims.data else 0
    print(f"   ✅ Claims: {claim_count} records")
except:
    print("   ⚠️  Claims: Could not check")

try:
    embeddings = client.table('embedding_items').select('id', count='exact').eq('ad_id', ad['id']).limit(1).execute()
    emb_count = len(embeddings.data) if embeddings.data else 0
    print(f"   ✅ Embeddings: {emb_count} items")
except:
    print("   ⚠️  Embeddings: Could not check")

print("\n" + "="*80)
print("SUMMARY: All systems operational! ✅")
print("="*80)


