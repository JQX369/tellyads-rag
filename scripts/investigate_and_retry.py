"""Investigate incomplete ads and retry them."""
import os
os.environ['DB_BACKEND'] = 'http'

from tvads_rag.tvads_rag.supabase_db import _get_client, find_incomplete_ads, delete_ad

client = _get_client()

# First, let's see what data TA10011 and TA10012 have
print("=" * 80)
print("INVESTIGATING INCOMPLETE ADS")
print("=" * 80)

for ext_id in ['TA10011', 'TA10012', 'TA10017']:
    resp = client.table('ads').select('id, external_id, s3_key, brand_name, one_line_summary, extraction_version').eq('external_id', ext_id).execute()
    ads = resp.data or []
    
    if not ads:
        print(f"\n{ext_id}: NOT FOUND IN DATABASE")
        continue
        
    ad = ads[0]
    ad_id = ad['id']
    
    print(f"\n{ext_id}:")
    print(f"  Brand: {ad.get('brand_name')}")
    print(f"  Summary: {(ad.get('one_line_summary') or '')[:60]}...")
    print(f"  S3 Key: {ad.get('s3_key')}")
    print(f"  Version: {ad.get('extraction_version')}")
    
    # Check child tables
    seg_resp = client.table('ad_segments').select('id', count='exact').eq('ad_id', ad_id).execute()
    claim_resp = client.table('ad_claims').select('id', count='exact').eq('ad_id', ad_id).execute()
    story_resp = client.table('ad_storyboards').select('id', count='exact').eq('ad_id', ad_id).execute()
    emb_resp = client.table('embedding_items').select('id', count='exact').eq('ad_id', ad_id).execute()
    
    print(f"  Segments: {len(seg_resp.data or [])}")
    print(f"  Claims: {len(claim_resp.data or [])}")
    print(f"  Storyboard: {len(story_resp.data or [])}")
    print(f"  Embeddings: {len(emb_resp.data or [])}")

print("\n" + "=" * 80)
print("FINDING ALL INCOMPLETE ADS FOR RETRY")
print("=" * 80)

# Find incomplete ads
incomplete = find_incomplete_ads(
    check_storyboard=True,
    check_v2_extraction=True, 
    check_impact_scores=True,
    limit=50
)

print(f"\nFound {len(incomplete)} incomplete ads:")
for ad in incomplete:
    print(f"  - {ad['external_id']}: {', '.join(ad['missing'])}")

# Show which ones have S3 keys (can be retried)
retryable = [ad for ad in incomplete if ad.get('s3_key')]
print(f"\nRetryable (have S3 keys): {len(retryable)}")
for ad in retryable:
    print(f"  - {ad['external_id']}: {ad['s3_key']}")


