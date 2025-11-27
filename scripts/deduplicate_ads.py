"""
Remove duplicate ads from the database, keeping only the most recent version of each.
"""
import os
os.environ['DB_BACKEND'] = 'http'

from collections import defaultdict
from tvads_rag.tvads_rag.supabase_db import _get_client, delete_ad

def main():
    client = _get_client()
    
    # Get all ads with their metadata
    resp = client.table('ads').select(
        'id, external_id, created_at, extraction_version'
    ).order('created_at', desc=True).execute()
    
    ads = resp.data or []
    
    print("=" * 80)
    print("DEDUPLICATING ADS")
    print("=" * 80)
    print(f"Total ads in database: {len(ads)}")
    
    # Group by external_id
    by_ext_id = defaultdict(list)
    for ad in ads:
        by_ext_id[ad['external_id']].append(ad)
    
    print(f"Unique external_ids: {len(by_ext_id)}")
    
    # Find duplicates
    to_delete = []
    for ext_id, versions in by_ext_id.items():
        if len(versions) > 1:
            # Sort by created_at descending (newest first)
            versions.sort(key=lambda x: x['created_at'], reverse=True)
            
            # Keep the newest, mark others for deletion
            keeper = versions[0]
            for old_version in versions[1:]:
                to_delete.append({
                    'id': old_version['id'],
                    'external_id': ext_id,
                    'created_at': old_version['created_at'],
                    'extraction_version': old_version.get('extraction_version'),
                })
            
            print(f"\n{ext_id}: {len(versions)} versions")
            print(f"  KEEP: {keeper['id'][:8]}... (v{keeper.get('extraction_version')}, {keeper['created_at'][:19]})")
            for old in versions[1:]:
                print(f"  DELETE: {old['id'][:8]}... (v{old.get('extraction_version')}, {old['created_at'][:19]})")
    
    if not to_delete:
        print("\nNo duplicates to remove!")
        return
    
    print(f"\n{'=' * 80}")
    print(f"Will delete {len(to_delete)} duplicate ads")
    print("=" * 80)
    
    # Auto-confirm (run with --dry-run to preview only)
    import sys
    if '--dry-run' in sys.argv:
        print("\nDry run - no deletions performed.")
        return
    
    print("\nProceeding with deletion...")
    
    # Delete duplicates
    deleted = 0
    for ad in to_delete:
        try:
            success = delete_ad(ad['id'])
            if success:
                deleted += 1
                print(f"  ✅ Deleted {ad['external_id']} ({ad['id'][:8]}...)")
            else:
                print(f"  ❌ Failed to delete {ad['external_id']}")
        except Exception as e:
            print(f"  ❌ Error deleting {ad['external_id']}: {e}")
    
    print(f"\nDone! Deleted {deleted}/{len(to_delete)} duplicate ads.")
    
    # Verify
    resp = client.table('ads').select('id', count='exact').execute()
    print(f"Ads remaining: {len(resp.data or [])}")


if __name__ == '__main__':
    main()

