"""
Deep dive data quality check for ingested ads.
Verifies structure, completeness, and quality of all data.
"""
import os
import json
import sys
from pathlib import Path
from collections import defaultdict

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Set DB backend
os.environ['DB_BACKEND'] = 'http'

# Load env vars
from dotenv import load_dotenv
load_dotenv(project_root / ".env")

from tvads_rag.tvads_rag.supabase_db import _get_client

def check_data_quality():
    client = _get_client()
    
    print("=" * 80)
    print("TELLYADS RAG - DATA QUALITY CHECK")
    print("=" * 80)
    
    # 1. Get all ads
    print("\n📊 FETCHING ALL ADS...")
    ads_resp = client.table('ads').select('*').order('created_at', desc=True).execute()
    ads = ads_resp.data or []
    print(f"Total ads in database: {len(ads)}")
    
    if not ads:
        print("❌ No ads found in database!")
        return
    
    # 2. Basic stats
    print("\n" + "=" * 80)
    print("1️⃣ BASIC AD STATS")
    print("=" * 80)
    
    # Check external_id patterns
    external_ids = [ad.get('external_id', 'N/A') for ad in ads]
    print(f"\nExternal IDs (first 10): {external_ids[:10]}")
    
    # Check for compilation files that slipped through
    compilations = [eid for eid in external_ids if '-' in str(eid) and 'TA' in str(eid)]
    if compilations:
        print(f"⚠️  Compilation files found (should have been skipped): {compilations}")
    else:
        print("✅ No compilation files found (good!)")
    
    # 3. Field completeness
    print("\n" + "=" * 80)
    print("2️⃣ FIELD COMPLETENESS")
    print("=" * 80)
    
    core_fields = ['brand_name', 'product_name', 'one_line_summary', 'duration_seconds', 'format_type']
    extraction_v2_fields = ['impact_scores', 'emotional_metrics', 'effectiveness', 'cta_offer', 
                           'brand_asset_timeline', 'audio_fingerprint', 'creative_dna', 'claims_compliance']
    
    field_stats = defaultdict(int)
    for ad in ads:
        for field in core_fields + extraction_v2_fields + ['analysis_json', 'extraction_version']:
            if ad.get(field):
                field_stats[field] += 1
    
    print("\nCore Fields:")
    for field in core_fields:
        count = field_stats[field]
        pct = (count / len(ads)) * 100
        status = "✅" if pct >= 90 else "⚠️" if pct >= 50 else "❌"
        print(f"  {status} {field}: {count}/{len(ads)} ({pct:.1f}%)")
    
    print("\nExtraction v2.0 Fields:")
    for field in extraction_v2_fields:
        count = field_stats[field]
        pct = (count / len(ads)) * 100
        status = "✅" if pct >= 90 else "⚠️" if pct >= 50 else "❌"
        print(f"  {status} {field}: {count}/{len(ads)} ({pct:.1f}%)")
    
    print(f"\n  extraction_version: {field_stats['extraction_version']}/{len(ads)}")
    print(f"  analysis_json: {field_stats['analysis_json']}/{len(ads)}")
    
    # 4. Check related tables
    print("\n" + "=" * 80)
    print("3️⃣ RELATED DATA (Segments, Claims, Storyboards, Embeddings)")
    print("=" * 80)
    
    ad_ids = [ad['id'] for ad in ads]
    
    # Segments
    segments_resp = client.table('ad_segments').select('ad_id').in_('ad_id', ad_ids).execute()
    segments = segments_resp.data or []
    segments_by_ad = defaultdict(int)
    for s in segments:
        segments_by_ad[s['ad_id']] += 1
    ads_with_segments = len([a for a in ad_ids if segments_by_ad[a] > 0])
    total_segments = len(segments)
    avg_segments = total_segments / len(ads) if ads else 0
    print(f"\nSegments:")
    print(f"  Total: {total_segments}")
    print(f"  Ads with segments: {ads_with_segments}/{len(ads)}")
    print(f"  Avg per ad: {avg_segments:.1f}")
    
    # Claims
    claims_resp = client.table('ad_claims').select('ad_id').in_('ad_id', ad_ids).execute()
    claims = claims_resp.data or []
    claims_by_ad = defaultdict(int)
    for c in claims:
        claims_by_ad[c['ad_id']] += 1
    ads_with_claims = len([a for a in ad_ids if claims_by_ad[a] > 0])
    total_claims = len(claims)
    print(f"\nClaims:")
    print(f"  Total: {total_claims}")
    print(f"  Ads with claims: {ads_with_claims}/{len(ads)}")
    
    # Storyboards
    storyboards_resp = client.table('ad_storyboards').select('ad_id').in_('ad_id', ad_ids).execute()
    storyboards = storyboards_resp.data or []
    storyboards_by_ad = defaultdict(int)
    for sb in storyboards:
        storyboards_by_ad[sb['ad_id']] += 1
    ads_with_storyboards = len([a for a in ad_ids if storyboards_by_ad[a] > 0])
    total_storyboards = len(storyboards)
    avg_shots = total_storyboards / len(ads) if ads else 0
    print(f"\nStoryboards (Vision Analysis):")
    print(f"  Total shots: {total_storyboards}")
    print(f"  Ads with storyboards: {ads_with_storyboards}/{len(ads)}")
    print(f"  Avg shots per ad: {avg_shots:.1f}")
    status = "✅" if ads_with_storyboards == len(ads) else "⚠️"
    print(f"  {status} Coverage: {(ads_with_storyboards/len(ads)*100):.1f}%")
    
    # Embeddings
    embeddings_resp = client.table('embedding_items').select('ad_id, item_type').in_('ad_id', ad_ids).execute()
    embeddings = embeddings_resp.data or []
    embeddings_by_ad = defaultdict(int)
    embeddings_by_type = defaultdict(int)
    for e in embeddings:
        embeddings_by_ad[e['ad_id']] += 1
        embeddings_by_type[e['item_type']] += 1
    ads_with_embeddings = len([a for a in ad_ids if embeddings_by_ad[a] > 0])
    total_embeddings = len(embeddings)
    avg_embeddings = total_embeddings / len(ads) if ads else 0
    print(f"\nEmbeddings:")
    print(f"  Total: {total_embeddings}")
    print(f"  Ads with embeddings: {ads_with_embeddings}/{len(ads)}")
    print(f"  Avg per ad: {avg_embeddings:.1f}")
    status = "✅" if ads_with_embeddings == len(ads) else "⚠️"
    print(f"  {status} Coverage: {(ads_with_embeddings/len(ads)*100):.1f}%")
    print(f"\n  By type:")
    for item_type, count in sorted(embeddings_by_type.items()):
        print(f"    - {item_type}: {count}")
    
    # 5. Sample ad deep dive
    print("\n" + "=" * 80)
    print("4️⃣ SAMPLE AD DEEP DIVE (Most Recent)")
    print("=" * 80)
    
    sample_ad = ads[0]
    print(f"\nExternal ID: {sample_ad.get('external_id')}")
    print(f"Brand: {sample_ad.get('brand_name')}")
    print(f"Product: {sample_ad.get('product_name')}")
    print(f"Duration: {sample_ad.get('duration_seconds')}s")
    print(f"Format: {sample_ad.get('format_type')}")
    print(f"Summary: {sample_ad.get('one_line_summary', 'N/A')[:100]}...")
    print(f"Extraction Version: {sample_ad.get('extraction_version')}")
    
    # Impact scores
    impact = sample_ad.get('impact_scores')
    if impact:
        print(f"\nImpact Scores:")
        if isinstance(impact, str):
            impact = json.loads(impact)
        overall = impact.get('overall_impact', {})
        print(f"  Overall: {overall.get('score', 'N/A')}/10 (confidence: {overall.get('confidence', 'N/A')})")
        print(f"  Hook Power: {impact.get('hook_power', {}).get('score', 'N/A')}/10")
        print(f"  Brand Integration: {impact.get('brand_integration', {}).get('score', 'N/A')}/10")
        print(f"  Emotional Resonance: {impact.get('emotional_resonance', {}).get('score', 'N/A')}/10")
    else:
        print("\n⚠️  No impact_scores found")
    
    # Emotional metrics
    emotional = sample_ad.get('emotional_metrics')
    if emotional:
        print(f"\nEmotional Metrics:")
        if isinstance(emotional, str):
            emotional = json.loads(emotional)
        timeline = emotional.get('emotional_timeline', {})
        print(f"  Arc Shape: {timeline.get('arc_shape', 'N/A')}")
        print(f"  Peak Emotion: {timeline.get('peak_emotion', 'N/A')}")
        brain = emotional.get('brain_balance', {})
        print(f"  Emotional Appeal: {brain.get('emotional_appeal_score', 'N/A')}/10")
        print(f"  Rational Appeal: {brain.get('rational_appeal_score', 'N/A')}/10")
    else:
        print("\n⚠️  No emotional_metrics found")
    
    # Creative DNA
    dna = sample_ad.get('creative_dna')
    if dna:
        print(f"\nCreative DNA:")
        if isinstance(dna, str):
            dna = json.loads(dna)
        print(f"  Archetype: {dna.get('archetype', 'N/A')}")
        print(f"  Hook Type: {dna.get('hook_type', 'N/A')}")
        print(f"  Persuasion Devices: {dna.get('persuasion_devices', [])}")
    else:
        print("\n⚠️  No creative_dna found")
    
    # 6. Processing Notes (errors/warnings during ingestion)
    print("\n" + "=" * 80)
    print("5️⃣ PROCESSING NOTES (Safety blocks, timeouts, errors)")
    print("=" * 80)
    
    ads_with_notes = [a for a in ads if a.get('processing_notes')]
    if ads_with_notes:
        print(f"\n⚠️  {len(ads_with_notes)} ads have processing notes (issues during ingestion):\n")
        for ad in ads_with_notes[:10]:  # Show first 10
            notes = ad.get('processing_notes', {})
            if isinstance(notes, str):
                try:
                    notes = json.loads(notes)
                except:
                    notes = {'raw': notes}
            
            ext_id = ad.get('external_id', 'unknown')
            if 'storyboard_error' in notes:
                err = notes['storyboard_error']
                err_type = err.get('type', 'unknown')
                reason = err.get('reason', 'N/A')[:100]
                print(f"  📝 {ext_id}: Storyboard {err_type} - {reason}")
            else:
                print(f"  📝 {ext_id}: {list(notes.keys())}")
        
        if len(ads_with_notes) > 10:
            print(f"  ... and {len(ads_with_notes) - 10} more")
    else:
        print("✅ No processing notes found (all ads processed without issues)")
    
    # 7. Check for issues
    print("\n" + "=" * 80)
    print("6️⃣ POTENTIAL ISSUES")
    print("=" * 80)
    
    issues = []
    
    # Check for ads without embeddings
    ads_missing_embeddings = [a['external_id'] for a in ads if embeddings_by_ad[a['id']] == 0]
    if ads_missing_embeddings:
        issues.append(f"❌ {len(ads_missing_embeddings)} ads missing embeddings: {ads_missing_embeddings[:5]}...")
    
    # Check for ads without storyboards
    ads_missing_storyboards = [a['external_id'] for a in ads if storyboards_by_ad[a['id']] == 0]
    if ads_missing_storyboards:
        issues.append(f"⚠️  {len(ads_missing_storyboards)} ads missing storyboards: {ads_missing_storyboards[:5]}...")
    
    # Check for ads without impact scores
    ads_missing_impact = [a['external_id'] for a in ads if not a.get('impact_scores')]
    if ads_missing_impact:
        issues.append(f"⚠️  {len(ads_missing_impact)} ads missing impact_scores: {ads_missing_impact[:5]}...")
    
    # Check extraction version
    v1_ads = [a['external_id'] for a in ads if (a.get('extraction_version') or '1.0') != '2.0']
    if v1_ads:
        issues.append(f"ℹ️  {len(v1_ads)} ads using extraction v1.0 (not v2.0): {v1_ads[:5]}...")
    
    # Check for very short/long durations
    weird_durations = [a for a in ads if a.get('duration_seconds') and (a['duration_seconds'] < 5 or a['duration_seconds'] > 300)]
    if weird_durations:
        issues.append(f"ℹ️  {len(weird_durations)} ads with unusual duration (<5s or >300s)")
    
    if issues:
        print("\n".join(issues))
    else:
        print("✅ No issues detected!")
    
    # 8. Summary
    print("\n" + "=" * 80)
    print("📋 SUMMARY")
    print("=" * 80)
    
    all_good = (
        ads_with_embeddings == len(ads) and
        ads_with_storyboards >= len(ads) * 0.9 and  # Allow 10% missing storyboards
        field_stats['impact_scores'] >= len(ads) * 0.9
    )
    
    if all_good:
        print("\n✅ DATA QUALITY: GOOD - Ready for scaled ingestion!")
    else:
        print("\n⚠️  DATA QUALITY: Some issues detected - Review above before scaling")
    
    print(f"\nTotal ads: {len(ads)}")
    print(f"Ads with complete data: ~{min(ads_with_embeddings, ads_with_storyboards)}/{len(ads)}")
    print(f"Extraction v2.0 coverage: {field_stats.get('extraction_version', 0)}/{len(ads)}")
    
    return ads

if __name__ == "__main__":
    check_data_quality()

