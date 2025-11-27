#!/usr/bin/env python3
"""
Calculate costs for different Gemini vision model options.
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ['DB_BACKEND'] = 'http'
from dotenv import load_dotenv
load_dotenv()
from tvads_rag.tvads_rag.supabase_db import _get_client

# Pricing (as of Nov 2025, from dashboard.py and cost docs)
GEMINI_25_FLASH_INPUT = 0.075  # $0.075 per 1M tokens input
GEMINI_25_FLASH_OUTPUT = 0.30  # $0.30 per 1M tokens output (estimated)
GEMINI_3_PRO_INPUT = 2.00      # $2.00 per 1M tokens input
GEMINI_3_PRO_OUTPUT = 6.00     # $6.00 per 1M tokens output (estimated)

# For vision models, images are counted as tokens
# Gemini counts images as: base_tokens + (image_tokens_per_image * num_images)
# Base tokens: ~1000 tokens for prompt
# Per image: ~85 tokens per image (for 512x512 images, scales with resolution)
# Our frames are JPEG, typically 1920x1080 or similar, so ~170 tokens per image
TOKENS_PER_IMAGE = 170  # Conservative estimate for high-res frames
PROMPT_BASE_TOKENS = 1000  # Storyboard prompt
RESPONSE_TOKENS = 2000  # Average JSON response per ad

MAX_FRAMES_PER_AD = 24  # Gemini API limit

def calculate_storyboard_cost(num_ads, frames_per_ad, model_input_rate, model_output_rate):
    """Calculate cost for storyboard analysis."""
    # Input tokens: prompt + images
    input_tokens_per_ad = PROMPT_BASE_TOKENS + (frames_per_ad * TOKENS_PER_IMAGE)
    input_tokens_total = num_ads * input_tokens_per_ad
    
    # Output tokens: JSON response
    output_tokens_per_ad = RESPONSE_TOKENS
    output_tokens_total = num_ads * output_tokens_per_ad
    
    # Costs
    input_cost = (input_tokens_total / 1_000_000) * model_input_rate
    output_cost = (output_tokens_total / 1_000_000) * model_output_rate
    
    return {
        'input_tokens': input_tokens_total,
        'output_tokens': output_tokens_total,
        'input_cost': input_cost,
        'output_cost': output_cost,
        'total_cost': input_cost + output_cost,
        'cost_per_ad': (input_cost + output_cost) / num_ads if num_ads > 0 else 0
    }

def calculate_video_analysis_cost(num_ads, avg_duration_seconds):
    """
    Calculate cost for whole video analysis (if Gemini supports it).
    Note: Gemini may not support direct video input - this is theoretical.
    """
    # If Gemini supported video directly:
    # Video tokens are typically much higher - ~10k tokens per second of video
    # But this is speculative - Gemini may not support this yet
    tokens_per_second = 10000
    input_tokens_per_ad = PROMPT_BASE_TOKENS + (avg_duration_seconds * tokens_per_second)
    input_tokens_total = num_ads * input_tokens_per_ad
    
    output_tokens_per_ad = RESPONSE_TOKENS * 2  # More detailed for full video
    output_tokens_total = num_ads * output_tokens_per_ad
    
    # Using Gemini 3 Pro pricing (would need Pro for video analysis)
    input_cost = (input_tokens_total / 1_000_000) * GEMINI_3_PRO_INPUT
    output_cost = (output_tokens_total / 1_000_000) * GEMINI_3_PRO_OUTPUT
    
    return {
        'input_tokens': input_tokens_total,
        'output_tokens': output_tokens_total,
        'input_cost': input_cost,
        'output_cost': output_cost,
        'total_cost': input_cost + output_cost,
        'cost_per_ad': (input_cost + output_cost) / num_ads if num_ads > 0 else 0
    }

def main():
    client = _get_client()
    
    # Get current stats
    ads_resp = client.table('ads').select('id', count='exact').execute()
    total_ads = ads_resp.count if hasattr(ads_resp, 'count') else len(ads_resp.data or [])
    
    ads_with_duration = client.table('ads').select('duration_seconds').not_.is_('duration_seconds', 'null').limit(100).execute()
    durations = [a.get('duration_seconds', 0) for a in (ads_with_duration.data or [])]
    avg_duration = sum(durations) / len(durations) if durations else 30
    
    # Projected: 20,000 ads (from cost doc)
    projected_ads = 20000
    
    print("=" * 80)
    print("GEMINI VISION MODEL COST COMPARISON")
    print("=" * 80)
    print(f"\nCurrent database: {total_ads} ads")
    print(f"Average duration: {avg_duration:.1f}s")
    print(f"Frames per ad: {MAX_FRAMES_PER_AD} (capped at Gemini limit)")
    print(f"\nProjected scale: {projected_ads:,} ads")
    
    print("\n" + "=" * 80)
    print("OPTION 1: CURRENT SETUP (Gemini 2.5 Flash for all storyboards)")
    print("=" * 80)
    current = calculate_storyboard_cost(
        projected_ads, MAX_FRAMES_PER_AD, 
        GEMINI_25_FLASH_INPUT, GEMINI_25_FLASH_OUTPUT
    )
    print(f"Input tokens: {current['input_tokens']:,}")
    print(f"Output tokens: {current['output_tokens']:,}")
    print(f"Input cost: ${current['input_cost']:.2f}")
    print(f"Output cost: ${current['output_cost']:.2f}")
    print(f"Total cost: ${current['total_cost']:.2f}")
    print(f"Cost per ad: ${current['cost_per_ad']:.4f}")
    
    print("\n" + "=" * 80)
    print("OPTION 2: ALL STORYBOARDS WITH GEMINI 3 PRO")
    print("=" * 80)
    pro_all = calculate_storyboard_cost(
        projected_ads, MAX_FRAMES_PER_AD,
        GEMINI_3_PRO_INPUT, GEMINI_3_PRO_OUTPUT
    )
    print(f"Input tokens: {pro_all['input_tokens']:,}")
    print(f"Output tokens: {pro_all['output_tokens']:,}")
    print(f"Input cost: ${pro_all['input_cost']:.2f}")
    print(f"Output cost: ${pro_all['output_cost']:.2f}")
    print(f"Total cost: ${pro_all['total_cost']:.2f}")
    print(f"Cost per ad: ${pro_all['cost_per_ad']:.4f}")
    print(f"\n⚠️  Increase over current: ${pro_all['total_cost'] - current['total_cost']:.2f}")
    print(f"   ({((pro_all['total_cost'] / current['total_cost']) - 1) * 100:.1f}% more expensive)")
    
    print("\n" + "=" * 80)
    print("OPTION 3: WHOLE VIDEO ANALYSIS (Gemini 3 Pro - THEORETICAL)")
    print("=" * 80)
    print("⚠️  NOTE: Gemini may not support direct video input yet.")
    print("   This calculation assumes video analysis is possible.")
    print("   Actual implementation may require frame extraction anyway.\n")
    
    video_analysis = calculate_video_analysis_cost(projected_ads, avg_duration)
    print(f"Input tokens: {video_analysis['input_tokens']:,}")
    print(f"Output tokens: {video_analysis['output_tokens']:,}")
    print(f"Input cost: ${video_analysis['input_cost']:.2f}")
    print(f"Output cost: ${video_analysis['output_cost']:.2f}")
    print(f"Total cost: ${video_analysis['total_cost']:.2f}")
    print(f"Cost per ad: ${video_analysis['cost_per_ad']:.4f}")
    print(f"\n⚠️  Increase over current: ${video_analysis['total_cost'] - current['total_cost']:.2f}")
    print(f"   ({((video_analysis['total_cost'] / current['total_cost']) - 1) * 100:.1f}% more expensive)")
    
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"\n{'Model':<30} {'Total Cost':<15} {'Cost/Ad':<15}")
    print("-" * 60)
    print(f"{'Gemini 2.5 Flash (Current)':<30} ${current['total_cost']:<14.2f} ${current['cost_per_ad']:<14.4f}")
    print(f"{'Gemini 3 Pro (All Ads)':<30} ${pro_all['total_cost']:<14.2f} ${pro_all['cost_per_ad']:<14.4f}")
    print(f"{'Gemini 3 Pro (Video - Theoretical)':<30} ${video_analysis['total_cost']:<14.2f} ${video_analysis['cost_per_ad']:<14.4f}")
    
    print("\n" + "=" * 80)
    print("RECOMMENDATION")
    print("=" * 80)
    print("\n✅ Keep Gemini 2.5 Flash for regular storyboards:")
    print(f"   - Cost-effective: ${current['total_cost']:.2f} for {projected_ads:,} ads")
    print(f"   - Good quality: Sufficient for shot detection and brand capture")
    print(f"   - Fast processing: Lower latency")
    print("\n✅ Use Gemini 3 Pro selectively:")
    print("   - Hero ads (top 10% by views) - already implemented")
    print("   - Deep analysis when needed")
    print(f"   - Estimated cost: ~${pro_all['cost_per_ad'] * projected_ads * 0.1:.2f} for 10% hero ads")
    
    print("\n❌ Whole video analysis:")
    print("   - May not be supported by Gemini API")
    print("   - Much more expensive: ${video_analysis['total_cost']:.2f}")
    print("   - Frame extraction likely still needed")
    print("   - Not recommended unless Gemini adds native video support")

if __name__ == "__main__":
    main()


