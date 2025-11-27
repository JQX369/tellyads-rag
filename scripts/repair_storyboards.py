"""
Repair missing storyboards for ads that have all other data.
Lighter weight than full re-ingestion - just downloads video, samples frames, runs Gemini.
"""
import os
import tempfile
os.environ['DB_BACKEND'] = 'http'

from pathlib import Path
from tvads_rag.tvads_rag.supabase_db import _get_client
from tvads_rag.tvads_rag import visual_analysis, media, db_backend, embeddings
from tvads_rag.tvads_rag.config import get_vision_config, get_storage_config

def get_ads_missing_storyboard():
    """Find ads that have data but missing storyboards."""
    client = _get_client()
    
    # Get recent ads
    resp = client.table('ads').select(
        'id, external_id, s3_key'
    ).order('created_at', desc=True).limit(50).execute()
    
    ads = resp.data or []
    missing = []
    
    for ad in ads:
        ad_id = ad['id']
        
        # Check if has storyboard
        story_resp = client.table('ad_storyboards').select('id', count='exact').eq('ad_id', ad_id).limit(1).execute()
        has_storyboard = len(story_resp.data or []) > 0
        
        if not has_storyboard and ad.get('s3_key'):
            missing.append(ad)
    
    return missing


def generate_storyboard_for_ad(ad):
    """Generate storyboard for an ad by downloading video and analyzing frames."""
    ad_id = ad['id']
    ext_id = ad['external_id']
    s3_key = ad['s3_key']
    
    storage_cfg = get_storage_config()
    vision_cfg = get_vision_config()
    
    print(f"  Downloading video for {ext_id}...")
    
    # Download video from S3
    video_path = None
    try:
        video_path = media.download_s3_object_to_tempfile(storage_cfg.s3_bucket, s3_key)
        
        print(f"  Sampling frames...")
        frame_samples = visual_analysis.sample_frames_for_storyboard(
            str(video_path), vision_cfg.frame_sample_seconds
        )
        
        if not frame_samples:
            print(f"  No frames could be sampled from {ext_id}")
            return 0
        
        print(f"  Analyzing {len(frame_samples)} frames with Gemini...")
        storyboard_shots = visual_analysis.analyse_frames_to_storyboard(
            frame_samples, tier="fast"
        )
        
        if not storyboard_shots:
            print(f"  Gemini returned empty storyboard for {ext_id} (may be content filtered)")
            return 0
        
        print(f"  Inserting {len(storyboard_shots)} storyboard shots...")
        storyboard_ids = db_backend.insert_storyboards(ad_id, storyboard_shots)
        
        # Generate embeddings for storyboard shots
        items = []
        for shot, shot_id in zip(storyboard_shots, storyboard_ids):
            text = f"{shot.get('shot_label') or ''}: {shot.get('description') or ''}"
            if text.strip() and text != ': ':
                items.append({
                    'ad_id': ad_id,
                    'storyboard_id': shot_id,
                    'item_type': 'storyboard_shot',
                    'text': text,
                    'meta': {},
                })
        
        if items:
            print(f"  Generating {len(items)} storyboard embeddings...")
            texts = [item['text'] for item in items]
            vectors = embeddings.embed_texts(texts)
            for item, vec in zip(items, vectors):
                item['embedding'] = vec
            db_backend.insert_embedding_items(ad_id, items)
        
        # Cleanup frames
        visual_analysis.cleanup_frame_samples(frame_samples)
        
        return len(storyboard_shots)
        
    except Exception as e:
        print(f"  Error processing {ext_id}: {e}")
        return 0
    finally:
        # Cleanup video
        if video_path and Path(video_path).exists():
            try:
                Path(video_path).unlink()
            except:
                pass


def main():
    print("=" * 80)
    print("REPAIRING MISSING STORYBOARDS")
    print("=" * 80)
    
    ads = get_ads_missing_storyboard()
    
    if not ads:
        print("No ads with missing storyboards found!")
        return
    
    print(f"Found {len(ads)} ads missing storyboards:")
    for ad in ads:
        print(f"  - {ad['external_id']}")
    
    print()
    
    total_shots = 0
    success = 0
    for ad in ads:
        try:
            count = generate_storyboard_for_ad(ad)
            total_shots += count
            if count > 0:
                print(f"  ✅ {ad['external_id']}: {count} shots created")
                success += 1
            else:
                print(f"  ⚠️ {ad['external_id']}: no shots (empty response)")
        except Exception as e:
            print(f"  ❌ {ad['external_id']}: {e}")
    
    print()
    print(f"Done! Created {total_shots} storyboard shots for {success}/{len(ads)} ads.")


if __name__ == '__main__':
    main()

