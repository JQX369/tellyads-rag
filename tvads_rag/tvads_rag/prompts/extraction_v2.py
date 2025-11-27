"""
TellyAds Creative Intelligence Extraction Prompt v2.0

This module contains the comprehensive 22-section extraction prompt for analyzing
TV/video advertisements. It extracts structured metadata including impact scores,
emotional metrics, effectiveness drivers, and more.
"""

EXTRACTION_V2_SYSTEM_PROMPT = """You are an expert advertising analyst extracting structured data from TV/video advertisements for a creative intelligence database. Analyze the provided video frames, audio transcript, and any metadata to extract the following fields.

## EXTRACTION RULES

1. Use `null` for any field you cannot confidently determine
2. All timestamps are in seconds (float, 1 decimal place)
3. All scores are 0.0-1.0 unless otherwise specified (impact_scores use 0-10)
4. Be specific and evidence-based - cite frame numbers or timestamps
5. When uncertain between two values, choose the more conservative option
6. Return ONLY valid JSON - no markdown fences, no prose before/after
7. Ensure all arrays contain at least one element where data exists, or empty [] if none

## SCORING GUIDE (0-10 for impact_scores):
| Score | Meaning |
|-------|---------|
| 0-2 | Poor - significant issues, likely to underperform |
| 2-4 | Below average - notable weaknesses |
| 4-6 | Average - competent but unremarkable |
| 6-8 | Good - strong execution with minor gaps |
| 8-10 | Exceptional - best-in-class creative |

## CONFIDENCE SCORING (0.0-1.0):
| Score | Meaning |
|-------|---------|
| 0.0-0.3 | Low confidence - limited evidence |
| 0.3-0.6 | Moderate confidence - some supporting evidence |
| 0.6-0.8 | Good confidence - clear evidence |
| 0.8-1.0 | High confidence - strong, unambiguous evidence |
"""

EXTRACTION_V2_USER_TEMPLATE = '''## Input Data

**Transcript:**
{transcript_text}

**Timestamped Segments:**
{segments_json}

## Required Output Schema

Return a single valid JSON object with ALL 22 sections below. Structure your response as:

{{
  "extraction_version": "2.0",
  "extraction_timestamp": "<ISO 8601 - use current time>",
  "confidence_overall": <0.0-1.0>,

  "core_metadata": {{
    "duration_seconds": <float>,
    "brand_name": "<string - exact brand name as spoken/displayed>",
    "product_name": "<string or null>",
    "product_category": "<FMCG|Automotive|Finance|Retail|Tech|Telecom|Entertainment|Travel|Pharma|Alcohol|Gambling|Charity|Government|B2B|Other>",
    "product_subcategory": "<string - be specific, e.g., 'SUV', 'Credit Card', 'Soft Drink'>",
    "country": "<ISO 3166-1 alpha-2, e.g., 'GB', 'US'>",
    "language": "<ISO 639-1, e.g., 'en'>",
    "year": <int or null if unknown>
  }},

  "campaign_strategy": {{
    "objective": "<brand_awareness|consideration|conversion|retention|reactivation|launch|seasonal|crisis>",
    "funnel_stage": "<top|middle|bottom|full_funnel>",
    "primary_kpi": "<reach|awareness|consideration|traffic|leads|sales|app_installs|sign_ups|other>",
    "format_type": "<hero_film|cutdown|social_edit|response|infomercial|sponsorship|ident>",
    "primary_setting": "<studio|location_indoor|location_outdoor|cgi|mixed|animation|stock>"
  }},

  "creative_flags": {{
    "has_voiceover": <bool>,
    "has_dialogue": <bool>,
    "has_on_screen_text": <bool>,
    "has_celebrity": <bool>,
    "has_ugc_style": <bool>,
    "has_supers": <bool>,
    "has_price_claims": <bool>,
    "has_risk_disclaimer": <bool>,
    "has_story_arc": <bool>,
    "has_humor": <bool>,
    "has_animals": <bool>,
    "has_children": <bool>,
    "has_music_with_lyrics": <bool>,
    "uses_nostalgia": <bool>,
    "uses_cultural_moment": <bool>,
    "regulator_sensitive": <bool>,
    "regulator_categories": ["<alcohol|gambling|finance|pharma|food_health|children|environment|none>"]
  }},

  "creative_attributes": {{
    "music_style": "<upbeat|dramatic|emotional|comedic|ambient|none|branded_jingle>",
    "editing_pace": "<rapid|moderate|slow|mixed|static>",
    "colour_mood": "<warm|cool|neutral|vibrant|muted|high_contrast|monochrome>",
    "visual_style": "<cinematic|documentary|animated|mixed_media|minimalist|maximalist|retro|futuristic>",
    "tone": "<serious|playful|inspirational|urgent|informative|provocative|heartwarming|edgy>",
    "overall_structure": "<linear_narrative|problem_solution|montage|testimonial|comparison|demo|slice_of_life|abstract>",
    "one_line_summary": "<string - max 100 chars, capture the core idea>",
    "story_summary": "<string - 2-3 sentences describing the narrative arc>"
  }},

  "impact_scores": {{
    "overall_impact": {{
      "score": <0.0-10.0, 1 decimal>,
      "confidence": <0.0-1.0>,
      "rationale": "<1-2 sentences explaining the score>"
    }},
    "pulse_score": {{
      "score": <0.0-10.0>,
      "description": "Short-term response potential - likelihood of immediate action/engagement",
      "confidence": <0.0-1.0>,
      "evidence": "<specific elements driving short-term response>"
    }},
    "echo_score": {{
      "score": <0.0-10.0>,
      "description": "Long-term brand building potential - memorability and brand equity contribution",
      "confidence": <0.0-1.0>,
      "evidence": "<specific elements driving long-term recall>"
    }},
    "hook_power": {{
      "score": <0.0-10.0>,
      "description": "First 3 seconds effectiveness - will viewers keep watching?",
      "hook_technique": "<curiosity|shock|beauty|humor|celebrity|action|question|mystery|relatable_moment>",
      "confidence": <0.0-1.0>
    }},
    "brand_integration": {{
      "score": <0.0-10.0>,
      "description": "How naturally and effectively is the brand woven into the creative?",
      "integration_style": "<hero|supporting|subtle|forced|absent_until_end>",
      "confidence": <0.0-1.0>
    }},
    "emotional_resonance": {{
      "score": <0.0-10.0>,
      "description": "Strength of emotional connection created",
      "primary_emotion": "<joy|surprise|trust|anticipation|sadness|fear|anger|disgust|neutral>",
      "emotional_authenticity": <0.0-1.0>,
      "confidence": <0.0-1.0>
    }},
    "clarity_score": {{
      "score": <0.0-10.0>,
      "description": "How clear is the message? Would a viewer understand the point?",
      "main_message": "<string - what should the viewer take away?>",
      "confidence": <0.0-1.0>
    }},
    "distinctiveness": {{
      "score": <0.0-10.0>,
      "description": "How unique is this vs category conventions? Would it stand out?",
      "distinctive_elements": ["<list of 1-3 standout creative choices>"],
      "confidence": <0.0-1.0>
    }}
  }},

  "emotional_timeline": {{
    "readings": [
      {{
        "t_s": <float - timestamp in seconds>,
        "dominant_emotion": "<joy|surprise|trust|anticipation|sadness|fear|anger|disgust|neutral>",
        "intensity": <0.0-1.0>,
        "valence": <-1.0 to 1.0, negative to positive>,
        "arousal": <0.0-1.0, calm to excited>
      }}
    ],
    "arc_shape": "<flat|rising|falling|peak_early|peak_late|peak_middle|u_shape|inverted_u|rollercoaster>",
    "peak_moment_s": <float>,
    "peak_emotion": "<emotion at peak>",
    "average_intensity": <0.0-1.0>,
    "positive_ratio": <0.0-1.0, proportion of positive emotional moments>
  }},

  "attention_dynamics": {{
    "predicted_completion_rate": <0.0-1.0>,
    "skip_risk_zones": [
      {{
        "t_start_s": <float>,
        "t_end_s": <float>,
        "risk_level": "<low|medium|high>",
        "reason": "<why viewers might disengage here>"
      }}
    ],
    "attention_peaks": [
      {{
        "t_s": <float>,
        "trigger": "<what grabs attention here>"
      }}
    ],
    "cognitive_load": "<low|moderate|high|overwhelming>",
    "pacing_assessment": "<too_slow|just_right|too_fast|inconsistent>"
  }},

  "creative_dna": {{
    "archetype": "<hero|explorer|sage|innocent|jester|magician|ruler|caregiver|creator|lover|outlaw|everyman>",
    "persuasion_devices": ["<social_proof|scarcity|authority|reciprocity|commitment|liking|unity|fear_appeal|humor|nostalgia|aspiration|problem_solution|demonstration|comparison|testimonial|storytelling|shock|curiosity>"],
    "hook_type": "<question|statement|visual_spectacle|celebrity|conflict|mystery|relatable_situation|shocking_stat|humor|beauty|action>",
    "narrative_structure": "<three_act|problem_solution|day_in_life|before_after|testimonial|anthology|circular|linear|non_linear>",
    "pacing_notes": "<string describing rhythm and edit style>",
    "distinctive_creative_choices": ["<list 2-5 specific creative decisions that make this ad unique>"]
  }},

  "brain_balance": {{
    "emotional_appeal_score": <0.0-10.0>,
    "rational_appeal_score": <0.0-10.0>,
    "balance_type": "<emotional_dominant|rational_dominant|balanced>",
    "emotional_elements": {{
      "has_characters_with_personality": <bool>,
      "has_relatable_situation": <bool>,
      "has_music_enhancing_emotion": <bool>,
      "has_visual_metaphor": <bool>,
      "has_humor_or_wit": <bool>,
      "has_human_connection": <bool>,
      "dialogue_between_characters": <bool>,
      "shows_consequence_or_payoff": <bool>
    }},
    "rational_elements": {{
      "has_product_demonstration": <bool>,
      "has_feature_callouts": <bool>,
      "has_price_or_offer": <bool>,
      "has_statistics_or_claims": <bool>,
      "has_direct_address_to_camera": <bool>,
      "has_comparison_to_competitor": <bool>,
      "has_instructional_content": <bool>,
      "has_urgency_messaging": <bool>
    }}
  }},

  "brand_presence": {{
    "first_appearance_s": <float or null>,
    "first_appearance_type": "<logo|product|name_mention|pack_shot|character|tagline|none>",
    "total_screen_time_pct": <0.0-1.0>,
    "mentions": [
      {{
        "t_s": <float>,
        "type": "<verbal|visual|both>",
        "prominence": "<subtle|moderate|prominent>",
        "context": "<string - how brand appears>"
      }}
    ],
    "logo_appearances": [
      {{
        "t_start_s": <float>,
        "t_end_s": <float>,
        "position": "<top_left|top_right|bottom_left|bottom_right|center|full_screen>",
        "size": "<small|medium|large|full>"
      }}
    ],
    "brand_frequency_score": <0.0-10.0>,
    "brand_integration_naturalness": <0.0-10.0>,
    "late_reveal": <bool, true if brand only appears in final 20%>,
    "sonic_branding_present": <bool>,
    "tagline_used": "<string or null>",
    "tagline_timestamp_s": <float or null>
  }},

  "distinctive_assets": [
    {{
      "asset_type": "<character|mascot|sonic|visual_style|tagline|colour|typography|animation_style|celebrity|jingle|sound_effect>",
      "description": "<string>",
      "recognition_potential": <0.0-1.0>,
      "brand_linkage": <0.0-1.0, how strongly does this asset connect to the brand?>,
      "appearances_s": [<list of timestamps>],
      "is_ownable": <bool, could only this brand use this?>
    }}
  ],

  "characters": [
    {{
      "role": "<protagonist|supporting|background|voiceover_only>",
      "screen_time_pct": <0.0-1.0>,
      "gender": "<male|female|non_binary|unclear>",
      "age_bracket": "<child|teen|18_24|25_34|35_44|45_54|55_64|65_plus|ageless>",
      "ethnicity": "<string or 'diverse_cast'>",
      "is_celebrity": <bool>,
      "celebrity_name": "<string or null>",
      "character_type": "<relatable_everyman|aspirational|expert|authority|comedic|villain|mascot|real_person>",
      "relatability_score": <0.0-10.0>,
      "likability_score": <0.0-10.0>
    }}
  ],

  "cta_offer": {{
    "has_cta": <bool>,
    "cta_type": "<visit_website|call_now|buy_now|learn_more|download_app|sign_up|visit_store|search|hashtag|none>",
    "cta_text": "<exact text or null>",
    "cta_timestamp_s": <float or null>,
    "cta_duration_s": <float>,
    "cta_prominence": "<subtle|moderate|strong|overwhelming>",
    "has_offer": <bool>,
    "offer_summary": "<string or null>",
    "price_shown": "<string or null>",
    "urgency_present": <bool>,
    "urgency_type": "<limited_time|limited_stock|seasonal|none>",
    "deadline_mentioned": "<string or null>",
    "terms_visible": <bool>,
    "endcard_present": <bool>,
    "endcard_start_s": <float or null>,
    "endcard_duration_s": <float or null>,
    "endcard_elements": ["<logo|url|phone|social|qr|tagline|offer>"]
  }},

  "audio_fingerprint": {{
    "voiceover": {{
      "present": <bool>,
      "gender": "<male|female|mixed|unclear>",
      "age_vibe": "<young|middle|mature|ageless>",
      "accent": "<string, e.g., 'British RP', 'American neutral', 'Scottish'>",
      "energy": "<calm|moderate|energetic|intense>",
      "pace": "<slow|moderate|fast>",
      "tone": "<authoritative|friendly|urgent|comedic|sincere|mysterious>"
    }},
    "dialogue": {{
      "present": <bool>,
      "style": "<natural|scripted|improvised>",
      "key_lines": ["<memorable dialogue snippets>"]
    }},
    "music": {{
      "present": <bool>,
      "type": "<original|licensed|stock|jingle>",
      "genre": "<string>",
      "energy_curve": "<builds|fades|steady|peaks_and_valleys>",
      "bpm_estimate": <int or null>,
      "has_lyrics": <bool>,
      "emotional_fit": <0.0-10.0>
    }},
    "sfx": {{
      "present": <bool>,
      "notable_sounds": ["<list key sound effects>"]
    }},
    "silence_moments": [
      {{
        "t_start_s": <float>,
        "t_end_s": <float>,
        "purpose": "<dramatic_pause|transition|intentional_contrast|technical_issue>"
      }}
    ],
    "audio_quality_score": <0.0-10.0>
  }},

  "segments": [
    {{
      "segment_index": <int, starting at 0>,
      "segment_type": "<hook|setup|conflict|resolution|cta|transition>",
      "aida_stage": "<attention|interest|desire|action|mixed>",
      "start_s": <float>,
      "end_s": <float>,
      "duration_s": <float>,
      "dominant_emotion": "<emotion>",
      "transcript_excerpt": "<key dialogue/VO in this segment>",
      "visual_summary": "<1-2 sentences describing visuals>",
      "purpose": "<what is this segment trying to achieve?>"
    }}
  ],

  "storyboard": [
    {{
      "shot_index": <int>,
      "start_s": <float>,
      "end_s": <float>,
      "duration_s": <float>,
      "shot_type": "<wide|medium|close_up|extreme_close_up|aerial|pov|over_shoulder|two_shot|group>",
      "camera_movement": "<static|pan|tilt|zoom|dolly|handheld|crane|drone|steadicam>",
      "location": "<string - describe setting>",
      "lighting": "<natural|studio|dramatic|low_key|high_key|mixed>",
      "key_subjects": ["<what/who is in frame>"],
      "action": "<what happens in this shot>",
      "on_screen_text": "<any supers/text visible, or null>",
      "audio_element": "<VO|dialogue|music|sfx|silence>",
      "mood": "<string - emotional tone of shot>",
      "transition_out": "<cut|dissolve|fade|wipe|match_cut|none>"
    }}
  ],

  "claims": [
    {{
      "text": "<exact claim text>",
      "claim_type": "<performance|quality|price|comparison|testimonial|statistic|environmental|health|safety|general>",
      "delivery": "<spoken|on_screen|both>",
      "timestamp_s": <float>,
      "is_comparative": <bool>,
      "is_superlative": <bool>,
      "likely_needs_substantiation": <bool>,
      "risk_level": "<low|medium|high>",
      "suggested_qualifier": "<string or null>"
    }}
  ],

  "supers": [
    {{
      "text": "<exact super text>",
      "super_type": "<legal|disclaimer|offer|contact|social|hashtag|product_info|other>",
      "start_s": <float>,
      "end_s": <float>,
      "duration_s": <float>,
      "position": "<top|middle|bottom|full_screen>",
      "legibility_score": <0.0-10.0>,
      "reading_time_adequate": <bool>
    }}
  ],

  "compliance_assessment": {{
    "overall_risk": "<low|medium|high|critical>",
    "regulated_category_flags": ["<alcohol|gambling|finance|pharma|food_health_claims|children|environment|none>"],
    "potential_issues": [
      {{
        "issue_type": "<misleading_claim|missing_disclaimer|unsuitable_for_audience|taste_and_decency|comparative_advertising|environmental_claim|health_claim|price_claim|other>",
        "description": "<what the issue is>",
        "timestamp_s": <float or null>,
        "evidence": "<specific text or visual>",
        "risk_level": "<low|medium|high>",
        "suggested_fix": "<how to address>"
      }}
    ],
    "required_disclaimers": [
      {{
        "disclaimer_type": "<string>",
        "present": <bool>,
        "adequate": <bool>,
        "suggested_text": "<string if not adequate>"
      }}
    ],
    "clearcast_readiness": <0.0-10.0>,
    "clearcast_notes": "<summary of likely clearance issues>"
  }},

  "effectiveness_drivers": {{
    "strengths": [
      {{
        "driver": "<string - what's working>",
        "impact": "<high|medium|low>",
        "evidence": "<specific frame/timestamp/element>",
        "recommendation": "<how to amplify this strength>"
      }}
    ],
    "weaknesses": [
      {{
        "driver": "<string - what's not working>",
        "impact": "<high|medium|low>",
        "evidence": "<specific frame/timestamp/element>",
        "fix_suggestion": "<specific actionable fix>",
        "fix_difficulty": "<easy|moderate|hard|requires_reshoot>"
      }}
    ],
    "optimization_opportunities": [
      {{
        "opportunity": "<string>",
        "potential_impact": "<string - estimated improvement>",
        "implementation": "<how to do it>"
      }}
    ],
    "ab_test_suggestions": [
      {{
        "element_to_test": "<string>",
        "variant_a": "<current approach>",
        "variant_b": "<suggested alternative>",
        "hypothesis": "<why this might improve performance>"
      }}
    ]
  }},

  "competitive_context": {{
    "category_conventions_followed": ["<list conventions this ad follows>"],
    "category_conventions_broken": ["<list conventions this ad breaks>"],
    "differentiation_strategy": "<what makes this stand out from competitors?>",
    "competitive_vulnerability": "<where could competitors easily beat this?>",
    "share_of_voice_potential": "<low|medium|high> - will this cut through?"
  }},

  "memorability": {{
    "overall_memorability_score": <0.0-10.0>,
    "predicted_recall_24h": <0.0-1.0>,
    "predicted_recall_7d": <0.0-1.0>,
    "memorable_elements": [
      {{
        "element": "<what will people remember>",
        "memorability_score": <0.0-10.0>,
        "brand_linked": <bool, will they remember the BRAND or just the element?>
      }}
    ],
    "forgettable_elements": [
      {{
        "element": "<what will people forget>",
        "reason": "<why it won't stick>"
      }}
    ],
    "distinctiveness_vs_category": <0.0-10.0>,
    "potential_for_cultural_impact": "<none|low|medium|high|viral_potential>"
  }},

  "raw_data": {{
    "full_transcript": "<complete spoken word transcript with timestamps>",
    "all_on_screen_text": ["<list all text that appears on screen>"],
    "frame_descriptions": [
      {{
        "frame_index": <int>,
        "timestamp_s": <float>,
        "description": "<detailed description of frame>"
      }}
    ]
  }}
}}

## QUALITY CHECKLIST (verify before returning):
- All scores use the correct scale (0-10 or 0-1 as specified)
- All timestamps are in seconds (floats)
- impact_scores all have rationale/evidence
- emotional_timeline has at least 1 reading per 5 seconds
- storyboard covers all shots (no gaps)
- claims are verbatim text from the ad
- effectiveness_drivers has both strengths AND weaknesses
- No fields are empty arrays when data exists
- JSON is valid and parseable
'''

# Default values for normalisation
DEFAULT_SECTIONS = {
    "core_metadata": {
        "duration_seconds": None,
        "brand_name": None,
        "product_name": None,
        "product_category": None,
        "product_subcategory": None,
        "country": None,
        "language": None,
        "year": None,
    },
    "campaign_strategy": {
        "objective": None,
        "funnel_stage": None,
        "primary_kpi": None,
        "format_type": None,
        "primary_setting": None,
    },
    "creative_flags": {
        "has_voiceover": False,
        "has_dialogue": False,
        "has_on_screen_text": False,
        "has_celebrity": False,
        "has_ugc_style": False,
        "has_supers": False,
        "has_price_claims": False,
        "has_risk_disclaimer": False,
        "has_story_arc": False,
        "has_humor": False,
        "has_animals": False,
        "has_children": False,
        "has_music_with_lyrics": False,
        "uses_nostalgia": False,
        "uses_cultural_moment": False,
        "regulator_sensitive": False,
        "regulator_categories": [],
    },
    "creative_attributes": {
        "music_style": None,
        "editing_pace": None,
        "colour_mood": None,
        "visual_style": None,
        "tone": None,
        "overall_structure": None,
        "one_line_summary": None,
        "story_summary": None,
    },
    "impact_scores": {
        "overall_impact": {"score": 5.0, "confidence": 0.5, "rationale": "Unable to assess"},
        "pulse_score": {"score": 5.0, "description": "", "confidence": 0.5, "evidence": ""},
        "echo_score": {"score": 5.0, "description": "", "confidence": 0.5, "evidence": ""},
        "hook_power": {"score": 5.0, "description": "", "hook_technique": "unknown", "confidence": 0.5},
        "brand_integration": {"score": 5.0, "description": "", "integration_style": "unknown", "confidence": 0.5},
        "emotional_resonance": {"score": 5.0, "description": "", "primary_emotion": "neutral", "emotional_authenticity": 0.5, "confidence": 0.5},
        "clarity_score": {"score": 5.0, "description": "", "main_message": "", "confidence": 0.5},
        "distinctiveness": {"score": 5.0, "description": "", "distinctive_elements": [], "confidence": 0.5},
    },
    "emotional_timeline": {
        "readings": [],
        "arc_shape": "flat",
        "peak_moment_s": None,
        "peak_emotion": "neutral",
        "average_intensity": 0.5,
        "positive_ratio": 0.5,
    },
    "attention_dynamics": {
        "predicted_completion_rate": 0.5,
        "skip_risk_zones": [],
        "attention_peaks": [],
        "cognitive_load": "moderate",
        "pacing_assessment": "just_right",
    },
    "creative_dna": {
        "archetype": "everyman",
        "persuasion_devices": [],
        "hook_type": None,
        "narrative_structure": "linear",
        "pacing_notes": None,
        "distinctive_creative_choices": [],
    },
    "brain_balance": {
        "emotional_appeal_score": 5.0,
        "rational_appeal_score": 5.0,
        "balance_type": "balanced",
        "emotional_elements": {
            "has_characters_with_personality": False,
            "has_relatable_situation": False,
            "has_music_enhancing_emotion": False,
            "has_visual_metaphor": False,
            "has_humor_or_wit": False,
            "has_human_connection": False,
            "dialogue_between_characters": False,
            "shows_consequence_or_payoff": False,
        },
        "rational_elements": {
            "has_product_demonstration": False,
            "has_feature_callouts": False,
            "has_price_or_offer": False,
            "has_statistics_or_claims": False,
            "has_direct_address_to_camera": False,
            "has_comparison_to_competitor": False,
            "has_instructional_content": False,
            "has_urgency_messaging": False,
        },
    },
    "brand_presence": {
        "first_appearance_s": None,
        "first_appearance_type": "none",
        "total_screen_time_pct": 0.0,
        "mentions": [],
        "logo_appearances": [],
        "brand_frequency_score": 0.0,
        "brand_integration_naturalness": 5.0,
        "late_reveal": False,
        "sonic_branding_present": False,
        "tagline_used": None,
        "tagline_timestamp_s": None,
    },
    "distinctive_assets": [],
    "characters": [],
    "cta_offer": {
        "has_cta": False,
        "cta_type": "none",
        "cta_text": None,
        "cta_timestamp_s": None,
        "cta_duration_s": 0.0,
        "cta_prominence": "subtle",
        "has_offer": False,
        "offer_summary": None,
        "price_shown": None,
        "urgency_present": False,
        "urgency_type": "none",
        "deadline_mentioned": None,
        "terms_visible": False,
        "endcard_present": False,
        "endcard_start_s": None,
        "endcard_duration_s": None,
        "endcard_elements": [],
    },
    "audio_fingerprint": {
        "voiceover": {"present": False, "gender": None, "age_vibe": None, "accent": None, "energy": None, "pace": None, "tone": None},
        "dialogue": {"present": False, "style": None, "key_lines": []},
        "music": {"present": False, "type": None, "genre": None, "energy_curve": None, "bpm_estimate": None, "has_lyrics": False, "emotional_fit": 5.0},
        "sfx": {"present": False, "notable_sounds": []},
        "silence_moments": [],
        "audio_quality_score": 5.0,
    },
    "segments": [],
    "storyboard": [],
    "claims": [],
    "supers": [],
    "compliance_assessment": {
        "overall_risk": "low",
        "regulated_category_flags": [],
        "potential_issues": [],
        "required_disclaimers": [],
        "clearcast_readiness": 5.0,
        "clearcast_notes": None,
    },
    "effectiveness_drivers": {
        "strengths": [],
        "weaknesses": [],
        "optimization_opportunities": [],
        "ab_test_suggestions": [],
    },
    "competitive_context": {
        "category_conventions_followed": [],
        "category_conventions_broken": [],
        "differentiation_strategy": None,
        "competitive_vulnerability": None,
        "share_of_voice_potential": "medium",
    },
    "memorability": {
        "overall_memorability_score": 5.0,
        "predicted_recall_24h": 0.5,
        "predicted_recall_7d": 0.3,
        "memorable_elements": [],
        "forgettable_elements": [],
        "distinctiveness_vs_category": 5.0,
        "potential_for_cultural_impact": "low",
    },
    "raw_data": {
        "full_transcript": "",
        "all_on_screen_text": [],
        "frame_descriptions": [],
    },
}


def deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge override into base, preserving base defaults where override is None."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        elif value is not None:
            result[key] = value
    return result


__all__ = [
    "EXTRACTION_V2_SYSTEM_PROMPT",
    "EXTRACTION_V2_USER_TEMPLATE",
    "DEFAULT_SECTIONS",
    "deep_merge",
]



