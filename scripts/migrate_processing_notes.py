#!/usr/bin/env python3
"""
Migration script to add processing_notes column to ads table.
"""

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tvads_rag.tvads_rag.supabase_db import _get_client


def main():
    client = _get_client()
    
    # Check if column exists by trying to select it
    try:
        result = client.table("ads").select("processing_notes").limit(1).execute()
        print("✅ Column 'processing_notes' already exists!")
        return True
    except Exception as e:
        if "column" in str(e).lower() and "does not exist" in str(e).lower():
            print("Column 'processing_notes' does not exist. Need to add it via Supabase SQL Editor.")
            print("\nRun this SQL in Supabase Dashboard > SQL Editor:")
            print("-" * 50)
            print("""
ALTER TABLE ads ADD COLUMN IF NOT EXISTS processing_notes jsonb;
""")
            print("-" * 50)
            return False
        else:
            # Column might exist but there's a different issue
            print(f"Note: Could not verify column: {e}")
            return True


if __name__ == "__main__":
    main()






