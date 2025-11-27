"""
Repair missing embeddings for ads that have all other data.
This is faster than full re-ingestion.
"""
import os
import sys
os.environ['DB_BACKEND'] = 'http'

from tvads_rag.tvads_rag.supabase_db import _get_client, find_incomplete_ads
from tvads_rag.tvads_rag import embeddings, db_backend

def get_ads_missing_embeddings():
    """Find ads that have data but missing embeddings."""
    client = _get_client()
    
    # Get recent ads
    resp = client.table('ads').select(
        'id, external_id, analysis_json'
    ).order('created_at', desc=True).limit(50).execute()
    
    ads = resp.data or []
    missing = []
    
    for ad in ads:
        ad_id = ad['id']
        
        # Check if has embeddings
        emb_resp = client.table('embedding_items').select('id', count='exact').eq('ad_id', ad_id).limit(1).execute()
        has_embeddings = len(emb_resp.data or []) > 0
        
        if not has_embeddings and ad.get('analysis_json'):
            missing.append(ad)
    
    return missing


def generate_embeddings_for_ad(ad):
    """Generate embeddings for an ad from its analysis_json."""
    ad_id = ad['id']
    ext_id = ad['external_id']
    analysis = ad.get('analysis_json') or {}
    
    client = _get_client()
    
    # Get child record IDs
    seg_resp = client.table('ad_segments').select('id').eq('ad_id', ad_id).execute()
    claim_resp = client.table('ad_claims').select('id').eq('ad_id', ad_id).execute()
    story_resp = client.table('ad_storyboards').select('id, shot_label, description').eq('ad_id', ad_id).execute()
    super_resp = client.table('ad_supers').select('id').eq('ad_id', ad_id).execute()
    chunk_resp = client.table('ad_chunks').select('id').eq('ad_id', ad_id).execute()
    
    segment_ids = [s['id'] for s in (seg_resp.data or [])]
    claim_ids = [c['id'] for c in (claim_resp.data or [])]
    storyboard_data = story_resp.data or []
    super_ids = [s['id'] for s in (super_resp.data or [])]
    chunk_ids = [c['id'] for c in (chunk_resp.data or [])]
    
    # Prepare embedding items
    items = []
    
    # 1. Segments
    for idx, seg in enumerate(analysis.get('segments', [])):
        if idx < len(segment_ids):
            text = seg.get('summary') or seg.get('transcript_text') or ''
            if text.strip():
                items.append({
                    'ad_id': ad_id,
                    'segment_id': segment_ids[idx],
                    'item_type': 'segment_summary',
                    'text': text,
                    'meta': {'aida_stage': seg.get('aida_stage')},
                })
    
    # 2. Claims
    for idx, claim in enumerate(analysis.get('claims', [])):
        if idx < len(claim_ids):
            text = claim.get('text') or ''
            if text.strip():
                items.append({
                    'ad_id': ad_id,
                    'claim_id': claim_ids[idx],
                    'item_type': 'claim',
                    'text': text,
                    'meta': {'claim_type': claim.get('claim_type')},
                })
    
    # 3. Storyboard shots
    for story in storyboard_data:
        text = f"{story.get('shot_label') or ''}: {story.get('description') or ''}"
        if text.strip() and text != ': ':
            items.append({
                'ad_id': ad_id,
                'storyboard_id': story['id'],
                'item_type': 'storyboard_shot',
                'text': text,
                'meta': {},
            })
    
    # 4. Ad summary
    summary = analysis.get('core_metadata', {}).get('one_line_summary') or ''
    if summary.strip():
        items.append({
            'ad_id': ad_id,
            'item_type': 'ad_summary',
            'text': summary,
            'meta': {},
        })
    
    # 5. Creative DNA
    dna = analysis.get('creative_dna', {})
    if dna.get('primary_technique'):
        text = f"Creative approach: {dna.get('primary_technique')} - {dna.get('tone')}"
        items.append({
            'ad_id': ad_id,
            'item_type': 'creative_dna',
            'text': text,
            'meta': dna,
        })
    
    # 6. CTA/Offer
    cta = analysis.get('cta_offer', {})
    if cta.get('primary_cta'):
        text = f"CTA: {cta.get('primary_cta')}"
        if cta.get('offer'):
            text += f" | Offer: {cta.get('offer')}"
        items.append({
            'ad_id': ad_id,
            'item_type': 'cta_offer',
            'text': text,
            'meta': cta,
        })
    
    # 7. Impact summary
    impact = analysis.get('impact_scores', {})
    if impact.get('overall_impact', {}).get('rationale'):
        items.append({
            'ad_id': ad_id,
            'item_type': 'impact_summary',
            'text': f"Overall Impact: {impact['overall_impact']['rationale']}",
            'meta': {'score': impact['overall_impact'].get('score')},
        })
    
    if not items:
        print(f"  No items to embed for {ext_id}")
        return 0
    
    print(f"  Generating {len(items)} embeddings for {ext_id}...")
    
    # Generate embeddings
    texts = [item['text'] for item in items]
    vectors = embeddings.embed_texts(texts)
    
    for item, vec in zip(items, vectors):
        item['embedding'] = vec
    
    # Insert into database
    db_backend.insert_embedding_items(ad_id, items)
    
    return len(items)


def main():
    print("=" * 80)
    print("REPAIRING MISSING EMBEDDINGS")
    print("=" * 80)
    
    ads = get_ads_missing_embeddings()
    
    if not ads:
        print("No ads with missing embeddings found!")
        return
    
    print(f"Found {len(ads)} ads missing embeddings:")
    for ad in ads:
        print(f"  - {ad['external_id']}")
    
    print()
    
    total_embeddings = 0
    for ad in ads:
        try:
            count = generate_embeddings_for_ad(ad)
            total_embeddings += count
            print(f"  ✅ {ad['external_id']}: {count} embeddings created")
        except Exception as e:
            print(f"  ❌ {ad['external_id']}: {e}")
    
    print()
    print(f"Done! Created {total_embeddings} embeddings for {len(ads)} ads.")


if __name__ == '__main__':
    main()


