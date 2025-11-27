"""
Clean up compilation files that were ingested before the filter was added.
"""
import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Set DB backend
os.environ['DB_BACKEND'] = 'http'

# Load env vars
from dotenv import load_dotenv
load_dotenv(project_root / ".env")

from tvads_rag.tvads_rag.supabase_db import _get_client, delete_ad

def cleanup_compilations():
    client = _get_client()
    
    # Find compilation files (those with ranges in external_id)
    print("🔍 Finding compilation files...")
    
    ads_resp = client.table('ads').select('id, external_id').execute()
    ads = ads_resp.data or []
    
    compilations = []
    for ad in ads:
        ext_id = ad.get('external_id', '')
        if '-' in ext_id and 'TA' in ext_id:
            # Check if it's a range pattern
            parts = ext_id.split('-')
            if len(parts) == 2:
                p1 = parts[0].replace('TA', '')
                p2 = parts[1].replace('TA', '')
                try:
                    int(p1)
                    int(p2)
                    compilations.append(ad)
                except ValueError:
                    pass
    
    if not compilations:
        print("✅ No compilation files found!")
        return
    
    print(f"\n⚠️  Found {len(compilations)} compilation files to delete:")
    for ad in compilations:
        print(f"   - {ad['external_id']} (ID: {ad['id']})")
    
    # Auto-confirm for non-interactive mode
    if len(sys.argv) > 1 and sys.argv[1] == '-y':
        confirm = 'y'
    else:
        confirm = input("\nDelete these? (y/n): ")
    
    if confirm.lower() != 'y':
        print("Aborted. Run with -y to auto-confirm.")
        return
    
    for ad in compilations:
        print(f"Deleting {ad['external_id']}...")
        delete_ad(ad['id'])
    
    print(f"\n✅ Deleted {len(compilations)} compilation files!")

if __name__ == "__main__":
    cleanup_compilations()

