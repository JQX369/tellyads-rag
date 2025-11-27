"""Quick script to check extraction v2.0 results."""
import json
import os
os.environ['DB_BACKEND'] = 'http'  # Use Supabase HTTP API

from tvads_rag.tvads_rag.supabase_db import _get_client

client = _get_client()
resp = client.table('ads').select('*').order('created_at', desc=True).limit(2).execute()
ads = resp.data or []

for ad in ads:
    print('='*80)
    print(f"AD: {ad['external_id']}")
    print(f"Brand: {ad['brand_name']} | Category: {ad['product_category']}")
    print(f"Duration: {ad['duration_seconds']}s | Extraction: v{ad.get('extraction_version', 'N/A')}")
    print(f"Summary: {ad['one_line_summary']}")
    print()
    
    # Check impact scores
    impact = ad.get('impact_scores')
    if impact:
        print('IMPACT SCORES:')
        for key in ['overall_impact', 'pulse_score', 'echo_score', 'hook_power', 'brand_integration', 'emotional_resonance', 'clarity_score', 'distinctiveness']:
            if key in impact:
                score_data = impact[key]
                if isinstance(score_data, dict):
                    print(f"  {key}: {score_data.get('score', 'N/A')}/10 (conf: {score_data.get('confidence', 'N/A')})")
    else:
        print('IMPACT SCORES: Not extracted')
    print()
    
    # Check emotional metrics
    emotional = ad.get('emotional_metrics')
    if emotional:
        print('EMOTIONAL METRICS:')
        timeline = emotional.get('emotional_timeline', {})
        if timeline:
            print(f"  Arc: {timeline.get('arc_shape', 'N/A')} | Peak: {timeline.get('peak_emotion', 'N/A')} @ {timeline.get('peak_moment_s', 'N/A')}s")
            readings = timeline.get('readings', [])
            print(f"  Readings: {len(readings)} data points")
        brain = emotional.get('brain_balance', {})
        if brain:
            print(f"  Brain Balance: Emotional={brain.get('emotional_appeal_score', 'N/A')}/10, Rational={brain.get('rational_appeal_score', 'N/A')}/10 ({brain.get('balance_type', 'N/A')})")
    else:
        print('EMOTIONAL METRICS: Not extracted')
    print()
    
    # Check effectiveness
    eff = ad.get('effectiveness')
    if eff:
        print('EFFECTIVENESS:')
        drivers = eff.get('effectiveness_drivers', {})
        if drivers:
            strengths = drivers.get('strengths', [])
            weaknesses = drivers.get('weaknesses', [])
            print(f"  Strengths: {len(strengths)} | Weaknesses: {len(weaknesses)}")
            for s in strengths[:2]:
                print(f"    + {s.get('driver', '')} ({s.get('impact', '')})")
            for w in weaknesses[:2]:
                print(f"    - {w.get('driver', '')} ({w.get('impact', '')})")
        memorability = eff.get('memorability', {})
        if memorability:
            print(f"  Memorability: {memorability.get('overall_memorability_score', 'N/A')}/10")
            elements = memorability.get('memorable_elements', [])
            for e in elements[:2]:
                linked = 'brand-linked' if e.get('brand_linked') else 'not linked'
                print(f"    * {e.get('element', '')} ({linked})")
    else:
        print('EFFECTIVENESS: Not extracted')
    print()
    
    # Check creative DNA
    dna = ad.get('creative_dna')
    if dna:
        print('CREATIVE DNA:')
        print(f"  Archetype: {dna.get('archetype', 'N/A')}")
        print(f"  Hook: {dna.get('hook_type', 'N/A')}")
        print(f"  Structure: {dna.get('narrative_structure', 'N/A')}")
        devices = dna.get('persuasion_devices', [])
        if devices:
            print(f"  Persuasion: {devices[:4]}")
    else:
        print('CREATIVE DNA: Not extracted')
    print()
    
    # Check CTA/Offer
    cta = ad.get('cta_offer')
    if cta:
        print('CTA/OFFER:')
        print(f"  Has CTA: {cta.get('has_cta', False)} | Type: {cta.get('cta_type', 'none')}")
        print(f"  Has Offer: {cta.get('has_offer', False)} | Urgency: {cta.get('urgency_present', False)}")
        if cta.get('cta_text'):
            print(f"  CTA Text: {cta.get('cta_text')}")
        if cta.get('offer_summary'):
            print(f"  Offer: {cta.get('offer_summary')}")
    else:
        print('CTA/OFFER: Not extracted')
    print()
    
    # Check compliance
    compliance = ad.get('claims_compliance')
    if compliance:
        print('COMPLIANCE:')
        print(f"  Overall Risk: {compliance.get('overall_risk', 'N/A')}")
        print(f"  Clearcast Ready: {compliance.get('clearcast_readiness', 'N/A')}/10")
        issues = compliance.get('potential_issues', [])
        if issues:
            print(f"  Issues: {len(issues)}")
            for i in issues[:2]:
                print(f"    ! {i.get('issue_type', '')}: {i.get('description', '')[:60]}...")
    else:
        print('COMPLIANCE: Not extracted')
    print()
    
    # Check if full analysis_json has all 22 sections
    analysis = ad.get('analysis_json')
    if analysis:
        sections = list(analysis.keys())
        expected = ['core_metadata', 'campaign_strategy', 'creative_flags', 'creative_attributes', 
                   'impact_scores', 'emotional_timeline', 'attention_dynamics', 'creative_dna',
                   'brain_balance', 'brand_presence', 'distinctive_assets', 'characters',
                   'cta_offer', 'audio_fingerprint', 'segments', 'storyboard', 'claims', 'supers',
                   'compliance_assessment', 'effectiveness_drivers', 'competitive_context', 'memorability']
        
        present = [s for s in expected if s in sections]
        missing = [s for s in expected if s not in sections]
        print(f"SECTIONS PRESENT: {len(present)}/22")
        if missing:
            print(f"  Missing: {missing}")
    print()
