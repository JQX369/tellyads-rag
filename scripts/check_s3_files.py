"""
Check which S3 video files actually exist before ingestion.
Helps identify gaps in the sequence.
"""
import os
from tvads_rag.tvads_rag.config import get_storage_config
from tvads_rag.tvads_rag import media

def main():
    storage_cfg = get_storage_config()
    
    print("=" * 80)
    print("CHECKING S3 FILES")
    print("=" * 80)
    print(f"Bucket: {storage_cfg.s3_bucket}")
    print(f"Prefix: {storage_cfg.s3_prefix or '(none)'}")
    print()
    
    # List all video keys
    print("Listing all video files from S3...")
    all_keys = media.list_s3_videos(
        storage_cfg.s3_bucket,
        storage_cfg.s3_prefix or "",
        limit=None,
    )
    
    print(f"Found {len(all_keys)} video files")
    print()
    
    # Show first and last few
    print("First 10 files:")
    for key in all_keys[:10]:
        print(f"  {key}")
    
    print()
    print("Last 10 files:")
    for key in all_keys[-10:]:
        print(f"  {key}")
    
    # Check for gaps in TA#### sequence
    print()
    print("Checking for gaps in TA#### sequence...")
    ta_keys = [k for k in all_keys if '/TA' in k]
    if ta_keys:
        # Extract numbers
        import re
        numbers = []
        for key in ta_keys:
            match = re.search(r'TA(\d+)', key)
            if match:
                numbers.append(int(match.group(1)))
        
        if numbers:
            numbers.sort()
            print(f"Found TA#### files from TA{numbers[0]} to TA{numbers[-1]}")
            
            # Find gaps
            gaps = []
            for i in range(len(numbers) - 1):
                if numbers[i+1] - numbers[i] > 1:
                    gap_start = numbers[i] + 1
                    gap_end = numbers[i+1] - 1
                    if gap_start == gap_end:
                        gaps.append(f"TA{gap_start}")
                    else:
                        gaps.append(f"TA{gap_start}-TA{gap_end}")
            
            if gaps:
                print(f"Gaps found: {', '.join(gaps[:20])}")
                if len(gaps) > 20:
                    print(f"... and {len(gaps) - 20} more gaps")
            else:
                print("No gaps found in sequence")
    
    print()
    print("=" * 80)
    print("To verify a specific file exists, use:")
    print(f"  python -c \"from tvads_rag.tvads_rag import media; print(media.s3_object_exists('{storage_cfg.s3_bucket}', 'Vids/TA1000.mp4'))\"")


if __name__ == '__main__':
    main()


