"""Check which ads are complete vs incomplete."""
import os
os.environ['DB_BACKEND'] = 'http'

from tvads_rag.tvads_rag.supabase_db import _get_client

client = _get_client()

# Get recent ads and check completeness
resp = client.table('ads').select('id, external_id, extraction_version, impact_scores, created_at').order('created_at', desc=True).limit(25).execute()
ads = resp.data or []

print('=' * 80)
print('RECENT ADS STATUS')
print('=' * 80)

complete = 0
incomplete = []

for ad in ads:
    ad_id = ad['id']
    ext_id = ad['external_id']
    version = ad.get('extraction_version') or '1.0'
    has_impact = bool(ad.get('impact_scores'))
    
    # Check storyboard
    story_resp = client.table('ad_storyboards').select('id', count='exact').eq('ad_id', ad_id).limit(1).execute()
    has_storyboard = len(story_resp.data or []) > 0
    
    # Check embeddings
    emb_resp = client.table('embedding_items').select('id', count='exact').eq('ad_id', ad_id).limit(1).execute()
    has_embeddings = len(emb_resp.data or []) > 0
    
    missing = []
    if version != '2.0':
        missing.append(f'v{version}')
    if not has_impact:
        missing.append('impact_scores')
    if not has_storyboard:
        missing.append('storyboard')
    if not has_embeddings:
        missing.append('embeddings')
    
    if missing:
        incomplete.append({'id': ext_id, 'missing': missing, 'ad_id': ad_id})
        print(f'❌ {ext_id}: missing {missing}')
    else:
        complete += 1
        print(f'✅ {ext_id}: complete (v{version})')

print()
print(f'SUMMARY: {complete} complete, {len(incomplete)} incomplete')

if incomplete:
    print()
    print('INCOMPLETE ADS:')
    for item in incomplete:
        print(f"  - {item['id']}: {', '.join(item['missing'])}")


