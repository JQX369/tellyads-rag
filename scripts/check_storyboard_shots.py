#!/usr/bin/env python3
"""Check storyboard shot counts vs video duration."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ['DB_BACKEND'] = 'http'
from dotenv import load_dotenv
load_dotenv()
from tvads_rag.tvads_rag.supabase_db import _get_client

client = _get_client()

print("=" * 80)
print("STORYBOARD SHOT COUNTS ANALYSIS")
print("=" * 80)

# Get recent ads with their storyboard counts
ads_resp = client.table('ads').select('id, external_id, duration_seconds').order('created_at', desc=True).limit(20).execute()
ads = ads_resp.data or []

low_shot_ads = []
normal_shot_ads = []

for ad in ads:
    ext_id = ad.get('external_id')
    duration = ad.get('duration_seconds', 0)
    ad_id = ad.get('id')
    
    # Get storyboard shots
    shots_resp = client.table('ad_storyboards').select(
        'shot_index, start_time, end_time, shot_label'
    ).eq('ad_id', ad_id).order('shot_index').execute()
    shots = shots_resp.data or []
    
    shot_count = len(shots)
    
    # Expected: roughly 1 shot per 3-6 seconds for typical ads
    # So a 30s ad should have ~5-10 shots
    expected_min = max(1, int(duration / 6))
    expected_max = max(3, int(duration / 3))
    
    if duration > 20 and shot_count < expected_min:
        low_shot_ads.append({
            'ext_id': ext_id,
            'duration': duration,
            'shot_count': shot_count,
            'expected_min': expected_min,
            'expected_max': expected_max,
            'shots': shots[:5]  # First 5 shots
        })
    else:
        normal_shot_ads.append({
            'ext_id': ext_id,
            'duration': duration,
            'shot_count': shot_count
        })

print(f"\nTotal ads checked: {len(ads)}")
print(f"Ads with low shot counts: {len(low_shot_ads)}")
print(f"Ads with normal shot counts: {len(normal_shot_ads)}")

print("\n" + "-" * 80)
print("ALL ADS - SHOT COUNTS:")
print("-" * 80)
for ad_info in sorted(normal_shot_ads + low_shot_ads, key=lambda x: x['duration'], reverse=True):
    print(f"{ad_info['ext_id']:12} ({ad_info['duration']:5.1f}s): {ad_info['shot_count']:2} shots")

if low_shot_ads:
    print("\n" + "-" * 80)
    print("ADS WITH LOW SHOT COUNTS:")
    print("-" * 80)
    
    for ad_info in low_shot_ads:
        print(f"\n📺 {ad_info['ext_id']} ({ad_info['duration']:.1f}s)")
        print(f"   Shots: {ad_info['shot_count']} (expected: {ad_info['expected_min']}-{ad_info['expected_max']})")
        
        if ad_info['shots']:
            print("   Shot breakdown:")
            for shot in ad_info['shots']:
                start = shot.get('start_time', 0)
                end = shot.get('end_time', 0)
                label = shot.get('shot_label', 'N/A')[:60]
                print(f"     - Shot {shot.get('shot_index', '?')}: {start:.1f}s-{end:.1f}s: {label}")

print("\n" + "=" * 80)
print("ANALYSIS")
print("=" * 80)

if low_shot_ads:
    print("\n💡 POSSIBLE REASONS FOR LOW SHOT COUNTS:")
    print("   1. Long continuous scenes without cuts (Gemini groups frames into single shots)")
    print("   2. Safety filtering - some frames may be blocked")
    print("   3. Gemini not detecting shot boundaries properly")
    print("   4. Video has very few actual camera cuts")
    print("\n   This is NORMAL if the ad has:")
    print("   - Long continuous shots (e.g., single camera following action)")
    print("   - Minimal editing (few cuts)")
    print("   - Static shots (talking heads, product shots)")
else:
    print("\n✅ All ads have reasonable shot counts!")

