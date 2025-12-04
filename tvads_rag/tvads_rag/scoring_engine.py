"""
Toxic Ad Detector - Scoring Engine

Calculates a "Toxicity Score" (0-100) for video advertisements based on:
1. Physiological Harm: Sensory assault (strobes, loud audio, hyper-stimulation)
2. Psychological Manipulation: Dark patterns (false urgency, shaming, hidden costs)
3. Regulatory Risk: Safety standard violations (GARM, missing disclaimers)

The output is a "Nutrition Label" style report explaining why an ad may be harmful.

AI Enhancement:
- Uses Gemini 2.5 Flash for advanced dark pattern detection beyond regex
- Detects subtle manipulation, implied urgency, and emotional exploitation
- Falls back to regex-only if AI unavailable
"""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("tvads_rag.scoring_engine")

# ---------------------------------------------------------------------------
# Gemini AI Integration (optional import)
# ---------------------------------------------------------------------------

try:
    from google import genai
    from google.genai import types
    GENAI_AVAILABLE = True
except ImportError:
    genai = None
    types = None
    GENAI_AVAILABLE = False

# ---------------------------------------------------------------------------
# Tunable Weights (adjust sensitivity without rewriting logic)
# ---------------------------------------------------------------------------

# Category weights (must sum to 1.0)
WEIGHT_PHYSIOLOGICAL = 0.40
WEIGHT_PSYCHOLOGICAL = 0.40
WEIGHT_REGULATORY = 0.20

# Physiological thresholds
CUTS_PER_MINUTE_THRESHOLD = 80       # Dopamine overload threshold
LOUDNESS_LU_THRESHOLD = -10          # LUFS threshold (loudness war)
BRIGHTNESS_VARIANCE_THRESHOLD = 0.8  # Strobe/flash detection

# Physiological point values
POINTS_HIGH_CUTS = 20                # Points for exceeding cut threshold
POINTS_LOUD_AUDIO = 30               # Points for exceeding loudness threshold
POINTS_PHOTOSENSITIVITY = 50         # Auto high-risk for seizure potential

# Psychological thresholds
CLAIM_DENSITY_THRESHOLD = 6          # Claims per minute (Gish Gallop)
DARK_PATTERN_POINTS = 10             # Points per dark pattern category
DARK_PATTERN_CAP = 30                # Maximum points from dark patterns
POINTS_HIGH_CLAIM_DENSITY = 20       # Points for claim overload

# Regulatory point values
POINTS_GARM_HIGH_RISK = 50           # GARM category high risk
POINTS_MISSING_DISCLAIMER = 50       # Missing required disclaimers

# Risk level thresholds
RISK_LOW_MAX = 30
RISK_MEDIUM_MAX = 60

# AI enhancement settings
AI_CONFIDENCE_THRESHOLD = 0.6  # Minimum confidence to count AI-detected pattern
AI_MANIPULATION_SCORE_WEIGHT = 15  # Points added based on AI manipulation score

# ---------------------------------------------------------------------------
# Gemini AI Prompt for Dark Pattern Detection
# ---------------------------------------------------------------------------

DARK_PATTERN_AI_PROMPT = """You are an ethics engineer analyzing advertising content for manipulative "dark patterns" and psychological manipulation tactics.

Analyze the following advertisement transcript and identify ANY manipulative language or tactics.

## Categories to Detect:

1. **false_scarcity** - Fake urgency, artificial limited availability
   - "Only X left", "Selling out fast", "Limited time offer"
   - Implied scarcity without evidence
   
2. **shaming** - Guilt, embarrassment, or shame-based appeals
   - "Don't be stupid", "If you care about your family"
   - Implying the viewer is inadequate without the product
   
3. **forced_continuity** - Hidden subscriptions, auto-renewal traps
   - "Free trial", "Auto-ship", "Cancel anytime*"
   - Asterisks or fine print indicators
   
4. **fear_appeal** - Exploiting anxiety, fear, or insecurity
   - Health scares, safety threats, FOMO
   - "Before it's too late", "Protect your family"
   
5. **emotional_manipulation** - Exploiting emotions for compliance
   - Guilt trips, playing on sympathy
   - Manufactured emotional moments
   
6. **unsubstantiated_claims** - Too good to be true, misleading
   - "Guaranteed results", "Proven to work"
   - Claims without evidence

## Transcript to Analyze:
\"\"\"
{transcript}
\"\"\"

## Response Format (STRICT JSON, no markdown):
{{
  "dark_patterns": [
    {{
      "category": "category_id",
      "text": "exact quote from transcript",
      "confidence": 0.0-1.0,
      "reasoning": "brief explanation"
    }}
  ],
  "manipulation_score": 0.0-1.0,
  "subtle_patterns": ["implied tactics not explicit in text"],
  "fear_appeals": ["specific fear-based elements"],
  "unsubstantiated_claims": ["claims that may be misleading"],
  "overall_assessment": "One sentence summary of manipulation level"
}}

Be thorough but avoid false positives. Only flag genuine manipulation with confidence > 0.5.
Return empty arrays if no patterns found. Always return valid JSON."""

# ---------------------------------------------------------------------------
# Dark Pattern Definitions (Regex-based detection)
# ---------------------------------------------------------------------------

DARK_PATTERN_CATEGORIES = {
    "false_scarcity": {
        "label": "False Scarcity",
        "patterns": [
            r"\bonly\s+\d+\s+left\b",
            r"\bselling\s+out\s*(fast)?\b",
            r"\bexpires?\s+(soon|today|tonight|now)\b",
            r"\blimited\s+(time|offer|quantity|stock)\b",
            r"\bact\s+(now|fast|quickly)\b",
            r"\bdon'?t\s+miss\s+(out|this)\b",
            r"\bhurry\b",
            r"\bwhile\s+(supplies|stocks?)\s+last\b",
            r"\b(last|final)\s+chance\b",
            r"\bending\s+soon\b",
            r"\btoday\s+only\b",
            r"\b(few|limited)\s+(spots?|seats?|items?)\s+(left|remaining|available)\b",
        ],
    },
    "shaming": {
        "label": "Shaming",
        "patterns": [
            r"\bdon'?t\s+be\s+(stupid|dumb|foolish|an?\s+idiot)\b",
            r"\bif\s+you\s+(really\s+)?care\s+about\b",
            r"\byou\s+deserve\s+(better|more|this)\b",
            r"\baren'?t\s+you\s+tired\s+of\b",
            r"\bstop\s+(being|looking)\s+(broke|poor|fat|ugly|tired)\b",
            r"\bembarrass(ed|ing)?\b",
            r"\bdon'?t\s+let\s+(them|others|people)\s+(see|know|think)\b",
            r"\b(real|smart|good)\s+(men|women|parents|people)\s+(know|use|buy)\b",
            r"\bwhat\s+are\s+you\s+waiting\s+for\b",
            r"\byou'?re\s+(still|really)\s+(using|doing|buying)\b",
        ],
    },
    "forced_continuity": {
        "label": "Forced Continuity",
        "patterns": [
            r"\bfree\s+trial\s*\*?\b",
            r"\bauto[-\s]?(ship|renew|bill)\b",
            r"\bcancel\s+an?y?\s*time\b",
            r"\bno\s+commitment\s*\*?\b",
            r"\bno\s+strings\s+attached\b",
            r"\bjust\s+pay\s+(shipping|s&h|handling)\b",
            r"\b(easy|simple)\s+to\s+cancel\b",
            r"\brisk[-\s]?free\s*\*?\b",
            r"\bmoney[-\s]?back\s+guarantee\s*\*?\b",
            r"\bsubscription\s+(may|will)\s+(continue|renew)\b",
            r"\bafter\s+(your\s+)?trial\b",
        ],
    },
}

# ---------------------------------------------------------------------------
# Recommendation Templates
# ---------------------------------------------------------------------------

RECOMMENDATIONS = {
    "critical": "DO NOT RUN. This ad poses serious risks and requires major revisions.",
    "high": "HIGH RISK. Review flagged issues before publication. Editing recommended.",
    "medium": "MODERATE RISK. Address flagged concerns. May require minor adjustments.",
    "low": "LOW RISK. Ad appears compliant. Minor improvements may enhance viewer experience.",
}

# ---------------------------------------------------------------------------
# ToxicityScorer Class
# ---------------------------------------------------------------------------

class ToxicityScorer:
    """
    Calculates a Toxicity Score (0-100) for video advertisements.
    
    The scorer analyzes three pillars of potential harm:
    1. Physiological: Sensory assault metrics
    2. Psychological: Dark pattern manipulation (regex + AI)
    3. Regulatory: Compliance and safety standards
    
    AI Enhancement:
    - Uses Gemini 2.5 Flash for contextual dark pattern detection
    - Detects subtle manipulation that regex misses
    - Falls back to regex-only if AI unavailable
    
    Usage:
        scorer = ToxicityScorer(analysis_data={
            "visual_physics": {"cuts_per_minute": 85, ...},
            "audio_physics": {"loudness_db": -8, ...},
            "transcript": "Only 2 left! Act now...",
            "claims": [...],
            "garm_risk_level": "Medium",
        })
        report = scorer.calculate_toxicity()
    """
    
    def __init__(self, analysis_data: Dict[str, Any], use_ai: Optional[bool] = None):
        """
        Initialize the scorer with analysis data.
        
        Args:
            analysis_data: Combined output from physics_engine and analysis modules
            use_ai: Override AI usage (None = use config, True/False = force)
        """
        self.data = analysis_data
        
        # Extract sub-dictionaries safely
        self.visual_physics = analysis_data.get("visual_physics") or {}
        self.audio_physics = analysis_data.get("audio_physics") or {}
        self.transcript = analysis_data.get("transcript") or ""
        self.claims = analysis_data.get("claims") or []
        self.duration_seconds = analysis_data.get("duration_seconds") or 30
        
        # Regulatory inputs
        self.garm_risk_level = analysis_data.get("garm_risk_level") or "Unknown"
        self.required_disclaimers = analysis_data.get("required_disclaimers") or []
        self.present_disclaimers = analysis_data.get("present_disclaimers") or []
        
        # AI configuration
        self._use_ai = use_ai
        self._ai_config = None
        self._ai_client = None
        
        # Cache for dark patterns (computed once)
        self._dark_patterns_cache: Optional[List[Dict]] = None
        self._ai_analysis_cache: Optional[Dict] = None
    
    def _should_use_ai(self) -> bool:
        """Determine if AI should be used for analysis."""
        if self._use_ai is not None:
            return self._use_ai and GENAI_AVAILABLE
        
        # Check config
        try:
            from .config import get_toxicity_config, is_toxicity_ai_enabled
            return is_toxicity_ai_enabled()
        except Exception:
            return False
    
    def _get_ai_client(self):
        """Get or create the Gemini client."""
        if self._ai_client is not None:
            return self._ai_client
        
        if not GENAI_AVAILABLE:
            return None
        
        try:
            from .config import get_toxicity_config
            config = get_toxicity_config()
            if not config.api_key:
                return None
            
            self._ai_config = config
            self._ai_client = genai.Client(api_key=config.api_key)
            return self._ai_client
        except Exception as e:
            logger.warning("Failed to initialize Gemini client: %s", str(e)[:100])
            return None
    
    def detect_dark_patterns_ai(self, transcript_text: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Use Gemini 2.5 Flash to detect dark patterns with contextual understanding.
        
        Args:
            transcript_text: Text to analyze. Uses self.transcript if not provided.
        
        Returns:
            Dict with AI-detected patterns, confidence scores, and manipulation metrics.
            Returns None if AI unavailable or fails.
        """
        if self._ai_analysis_cache is not None:
            return self._ai_analysis_cache
        
        text = transcript_text if transcript_text is not None else self.transcript
        
        if not text or not text.strip():
            return None
        
        if not self._should_use_ai():
            return None
        
        client = self._get_ai_client()
        if not client:
            return None
        
        try:
            # Build prompt
            prompt = DARK_PATTERN_AI_PROMPT.format(transcript=text)
            
            # Get model name
            model_name = self._ai_config.model_name if self._ai_config else "gemini-2.5-flash"
            
            logger.debug("Running AI dark pattern detection with %s", model_name)
            
            # Call Gemini
            response = client.models.generate_content(
                model=model_name,
                contents=[types.Part.from_text(text=prompt)],
            )
            
            # Check for blocked response
            if hasattr(response, "candidates") and response.candidates:
                candidate = response.candidates[0]
                if hasattr(candidate, "finish_reason"):
                    finish_reason = str(candidate.finish_reason).upper()
                    if "SAFETY" in finish_reason or "BLOCKED" in finish_reason:
                        logger.warning("AI analysis blocked by safety filter: %s", finish_reason)
                        return None
            
            raw = getattr(response, "text", None) or ""
            
            if not raw.strip():
                logger.warning("AI returned empty response for dark pattern detection")
                return None
            
            # Parse JSON response
            result = self._parse_ai_response(raw, model_name)
            self._ai_analysis_cache = result
            return result
            
        except Exception as e:
            logger.warning("AI dark pattern detection failed: %s", str(e)[:100])
            return None
    
    def _parse_ai_response(self, raw: str, model_name: str) -> Optional[Dict[str, Any]]:
        """Parse the AI response JSON."""
        # Strip markdown fences if present
        text = raw.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines)
        
        try:
            result = json.loads(text)
            result["ai_model"] = model_name
            result["analysis_confidence"] = 1.0
            return result
        except json.JSONDecodeError as e:
            logger.warning("Failed to parse AI response as JSON: %s", str(e)[:50])
            
            # Try to extract partial data
            try:
                # Find JSON object in response
                start = text.find("{")
                end = text.rfind("}") + 1
                if start >= 0 and end > start:
                    partial = json.loads(text[start:end])
                    partial["ai_model"] = model_name
                    partial["analysis_confidence"] = 0.7  # Lower confidence for partial parse
                    return partial
            except Exception:
                pass
            
            return None
    
    def detect_dark_patterns(self, transcript_text: Optional[str] = None) -> List[Dict[str, str]]:
        """
        Scan transcript for manipulative language patterns.
        
        Args:
            transcript_text: Text to analyze. Uses self.transcript if not provided.
        
        Returns:
            List of detected patterns with category and matched text.
            Example: [{"category": "false_scarcity", "label": "False Scarcity", "matched_text": "only 2 left"}]
        """
        text = transcript_text if transcript_text is not None else self.transcript
        
        if not text:
            return []
        
        # Normalize text for matching
        text_lower = text.lower()
        
        detected = []
        seen_categories = set()  # Track unique categories
        
        for category_id, category_def in DARK_PATTERN_CATEGORIES.items():
            for pattern in category_def["patterns"]:
                matches = re.findall(pattern, text_lower, re.IGNORECASE)
                if matches:
                    for match in matches:
                        # Get the actual matched text (handle groups)
                        matched_text = match if isinstance(match, str) else match[0] if match else ""
                        if matched_text:
                            detected.append({
                                "category": category_id,
                                "label": category_def["label"],
                                "matched_text": matched_text.strip(),
                            })
                    seen_categories.add(category_id)
        
        return detected
    
    def score_physiological(self) -> Dict[str, Any]:
        """
        Calculate physiological harm score based on sensory assault metrics.
        
        Returns:
            Dict with score (0-100) and list of flags explaining the score.
        """
        score = 0
        flags = []
        
        # Check cuts per minute (dopamine overload)
        cuts_per_min = self.visual_physics.get("cuts_per_minute") or 0
        if cuts_per_min > CUTS_PER_MINUTE_THRESHOLD:
            score += POINTS_HIGH_CUTS
            flags.append(f"Rapid Cuts ({cuts_per_min:.0f}/min exceeds {CUTS_PER_MINUTE_THRESHOLD})")
        
        # Check loudness (loudness war violation)
        # Handle both loudness_db and loudness_lu naming conventions
        loudness = (
            self.audio_physics.get("loudness_lu") or
            self.audio_physics.get("loudness_db") or
            self.audio_physics.get("loudness") or
            -24  # Default to compliant value if missing
        )
        if loudness > LOUDNESS_LU_THRESHOLD:
            score += POINTS_LOUD_AUDIO
            flags.append(f"Extreme Loudness ({loudness:.1f} LUFS exceeds {LOUDNESS_LU_THRESHOLD})")
        
        # Check photosensitivity (strobe/flash risk)
        photosensitivity_fail = self.visual_physics.get("photosensitivity_fail", False)
        brightness_variance = self.visual_physics.get("brightness_variance") or 0
        
        if photosensitivity_fail:
            score += POINTS_PHOTOSENSITIVITY
            flags.append("Seizure Risk (Photosensitivity test failed)")
        elif brightness_variance > BRIGHTNESS_VARIANCE_THRESHOLD:
            # High brightness variance can indicate strobe effects
            score += POINTS_PHOTOSENSITIVITY // 2  # Half points for high variance
            flags.append(f"Flash Warning (Brightness variance {brightness_variance:.2f})")
        
        # Check motion energy (hyper-stimulation)
        motion_score = self.visual_physics.get("motion_energy_score") or 0
        if motion_score > 0.9:  # Very high motion
            score += 10
            flags.append(f"Hyper-Stimulation (Motion score {motion_score:.2f})")
        
        return {
            "score": min(score, 100),  # Cap at 100
            "flags": flags,
        }
    
    def score_psychological(self) -> Dict[str, Any]:
        """
        Calculate psychological manipulation score based on dark patterns and claim density.
        
        Uses hybrid approach:
        1. Regex detection for known patterns
        2. AI detection for contextual/subtle manipulation (if enabled)
        3. Combines results without double-counting
        
        Returns:
            Dict with score (0-100), list of flags, and AI analysis if available.
        """
        score = 0
        flags = []
        ai_analysis = None
        
        # Step 1: Regex-based detection
        if self._dark_patterns_cache is None:
            self._dark_patterns_cache = self.detect_dark_patterns()
        
        regex_patterns = self._dark_patterns_cache
        regex_categories = set(p["category"] for p in regex_patterns)
        
        # Step 2: AI-based detection (if enabled)
        ai_categories = set()
        ai_subtle_patterns = []
        ai_manipulation_score = 0.0
        
        if self._should_use_ai():
            ai_analysis = self.detect_dark_patterns_ai()
            
            if ai_analysis:
                # Extract high-confidence AI patterns
                for pattern in ai_analysis.get("dark_patterns", []):
                    confidence = pattern.get("confidence", 0)
                    if confidence >= AI_CONFIDENCE_THRESHOLD:
                        ai_categories.add(pattern.get("category", "unknown"))
                
                # Get subtle patterns (AI-only detection)
                ai_subtle_patterns = ai_analysis.get("subtle_patterns", [])
                
                # Get manipulation score
                ai_manipulation_score = ai_analysis.get("manipulation_score", 0)
        
        # Step 3: Combine results (union of categories)
        all_categories = regex_categories | ai_categories
        num_categories = len(all_categories)
        
        if num_categories > 0:
            pattern_points = min(num_categories * DARK_PATTERN_POINTS, DARK_PATTERN_CAP)
            score += pattern_points
            
            # Add flag for each category found
            for cat_id in all_categories:
                if cat_id in DARK_PATTERN_CATEGORIES:
                    label = DARK_PATTERN_CATEGORIES[cat_id]["label"]
                else:
                    # AI-detected category not in regex list
                    label = cat_id.replace("_", " ").title()
                
                source = ""
                if cat_id in regex_categories and cat_id in ai_categories:
                    source = " (Regex+AI)"
                elif cat_id in ai_categories:
                    source = " (AI)"
                
                flags.append(f"{label} Detected{source}")
        
        # Step 4: Add points for AI-detected subtle patterns
        if ai_subtle_patterns:
            subtle_points = min(len(ai_subtle_patterns) * 5, 15)  # Cap at 15
            score += subtle_points
            flags.append(f"Subtle Manipulation (AI: {', '.join(ai_subtle_patterns[:3])})")
        
        # Step 5: Add points based on AI manipulation score
        if ai_manipulation_score > 0.5:
            manipulation_points = int(ai_manipulation_score * AI_MANIPULATION_SCORE_WEIGHT)
            score += manipulation_points
            if ai_manipulation_score > 0.75:
                flags.append(f"High Manipulation Score (AI: {ai_manipulation_score:.0%})")
        
        # Step 6: Check claim density (Gish Gallop)
        duration_minutes = max(self.duration_seconds / 60, 0.25)  # Min 15 seconds
        num_claims = len(self.claims)
        claim_density = num_claims / duration_minutes
        
        if claim_density > CLAIM_DENSITY_THRESHOLD:
            score += POINTS_HIGH_CLAIM_DENSITY
            flags.append(f"Claim Overload ({claim_density:.1f} claims/min exceeds {CLAIM_DENSITY_THRESHOLD})")
        
        result = {
            "score": min(score, 100),  # Cap at 100
            "flags": flags,
        }
        
        # Include AI analysis metadata if available
        if ai_analysis:
            result["ai_analysis"] = {
                "model": ai_analysis.get("ai_model", "unknown"),
                "manipulation_score": ai_manipulation_score,
                "subtle_patterns": ai_subtle_patterns,
                "fear_appeals": ai_analysis.get("fear_appeals", []),
                "unsubstantiated_claims": ai_analysis.get("unsubstantiated_claims", []),
                "overall_assessment": ai_analysis.get("overall_assessment", ""),
            }
        
        return result
    
    def score_regulatory(self) -> Dict[str, Any]:
        """
        Calculate regulatory risk score based on GARM compliance and disclaimers.
        
        Returns:
            Dict with score (0-100) and list of flags explaining the score.
        """
        score = 0
        flags = []
        
        # Check GARM risk level
        garm_level = (self.garm_risk_level or "").lower()
        if garm_level == "high":
            score += POINTS_GARM_HIGH_RISK
            flags.append("GARM High Risk Category")
        elif garm_level == "medium":
            score += POINTS_GARM_HIGH_RISK // 2
            flags.append("GARM Medium Risk Category")
        
        # Check missing disclaimers
        if self.required_disclaimers:
            present_set = set(d.lower() for d in self.present_disclaimers)
            missing = [d for d in self.required_disclaimers if d.lower() not in present_set]
            
            if missing:
                score += POINTS_MISSING_DISCLAIMER
                flags.append(f"Missing Disclaimers: {', '.join(missing[:3])}")
        
        # Check for regulated product categories that need disclaimers
        regulated_keywords = {
            "pharma": ["side effects", "consult your doctor", "fda"],
            "alcohol": ["drink responsibly", "21+", "legal drinking age"],
            "gambling": ["gamble responsibly", "18+", "21+"],
            "financial": ["past performance", "risk of loss", "fdic"],
        }
        
        transcript_lower = self.transcript.lower()
        for category, keywords in regulated_keywords.items():
            # Check if ad seems to be in regulated category
            category_indicators = {
                "pharma": ["medication", "prescription", "drug", "treatment"],
                "alcohol": ["beer", "wine", "vodka", "whiskey", "liquor"],
                "gambling": ["bet", "casino", "poker", "slots", "wager"],
                "financial": ["invest", "stock", "loan", "credit", "mortgage"],
            }
            
            if any(ind in transcript_lower for ind in category_indicators.get(category, [])):
                # Check if required disclaimers are present
                if not any(kw in transcript_lower for kw in keywords):
                    score += 15
                    flags.append(f"{category.title()} Disclaimer May Be Required")
        
        return {
            "score": min(score, 100),  # Cap at 100
            "flags": flags,
        }
    
    def _generate_recommendation(self, total_score: int, breakdown: Dict) -> str:
        """Generate a human-readable recommendation based on the score and flags."""
        
        # Check for critical issues first
        physio_flags = breakdown["physiological"]["flags"]
        if any("Seizure" in f for f in physio_flags):
            return RECOMMENDATIONS["critical"] + " Remove strobe/flash effects immediately."
        
        # Generate recommendation based on risk level
        if total_score > 80:
            return RECOMMENDATIONS["critical"]
        elif total_score > RISK_MEDIUM_MAX:
            # Build specific advice
            advice = [RECOMMENDATIONS["high"]]
            if breakdown["physiological"]["score"] > 30:
                advice.append("Consider reducing cuts or audio levels.")
            if breakdown["psychological"]["score"] > 20:
                advice.append("Review language for manipulative patterns.")
            if breakdown["regulatory"]["score"] > 30:
                advice.append("Verify compliance requirements are met.")
            return " ".join(advice)
        elif total_score > RISK_LOW_MAX:
            return RECOMMENDATIONS["medium"]
        else:
            return RECOMMENDATIONS["low"]
    
    def _get_risk_level(self, score: int) -> str:
        """Convert numeric score to risk level label."""
        if score <= RISK_LOW_MAX:
            return "LOW"
        elif score <= RISK_MEDIUM_MAX:
            return "MEDIUM"
        else:
            return "HIGH"
    
    def calculate_toxicity(self) -> Dict[str, Any]:
        """
        Calculate the complete toxicity report.
        
        This is the main entry point for scoring an ad.
        
        Returns:
            Toxicity report with score, risk level, breakdown, patterns, and recommendation.
            If AI is enabled, includes AI analysis details.
        """
        # Calculate component scores
        physio = self.score_physiological()
        psycho = self.score_psychological()
        regulatory = self.score_regulatory()
        
        # Calculate weighted total score
        weighted_physio = physio["score"] * WEIGHT_PHYSIOLOGICAL
        weighted_psycho = psycho["score"] * WEIGHT_PSYCHOLOGICAL
        weighted_regulatory = regulatory["score"] * WEIGHT_REGULATORY
        
        total_score = int(round(weighted_physio + weighted_psycho + weighted_regulatory))
        total_score = min(max(total_score, 0), 100)  # Clamp 0-100
        
        # Get dark patterns for output
        if self._dark_patterns_cache is None:
            self._dark_patterns_cache = self.detect_dark_patterns()
        
        # Combine regex matches with AI-detected patterns
        dark_patterns_list = [p["matched_text"] for p in self._dark_patterns_cache]
        
        # Add AI-detected patterns if available
        if self._ai_analysis_cache:
            ai_patterns = self._ai_analysis_cache.get("dark_patterns", [])
            for p in ai_patterns:
                if p.get("confidence", 0) >= AI_CONFIDENCE_THRESHOLD:
                    text = p.get("text", "")
                    if text and text not in dark_patterns_list:
                        dark_patterns_list.append(text)
        
        # Build breakdown
        breakdown = {
            "physiological": physio,
            "psychological": psycho,
            "regulatory": regulatory,
        }
        
        # Generate recommendation
        recommendation = self._generate_recommendation(total_score, breakdown)
        
        result = {
            "toxic_score": total_score,
            "risk_level": self._get_risk_level(total_score),
            "breakdown": breakdown,
            "dark_patterns_detected": dark_patterns_list,
            "recommendation": recommendation,
            "metadata": {
                "weights": {
                    "physiological": WEIGHT_PHYSIOLOGICAL,
                    "psychological": WEIGHT_PSYCHOLOGICAL,
                    "regulatory": WEIGHT_REGULATORY,
                },
                "duration_seconds": self.duration_seconds,
                "claims_count": len(self.claims),
                "ai_enabled": self._should_use_ai(),
            },
        }
        
        # Add AI analysis summary if available
        if self._ai_analysis_cache:
            result["ai_analysis"] = {
                "model": self._ai_analysis_cache.get("ai_model", "unknown"),
                "manipulation_score": self._ai_analysis_cache.get("manipulation_score", 0),
                "overall_assessment": self._ai_analysis_cache.get("overall_assessment", ""),
                "subtle_patterns": self._ai_analysis_cache.get("subtle_patterns", []),
                "fear_appeals": self._ai_analysis_cache.get("fear_appeals", []),
                "unsubstantiated_claims": self._ai_analysis_cache.get("unsubstantiated_claims", []),
            }
        
        return result


# ---------------------------------------------------------------------------
# Convenience Functions
# ---------------------------------------------------------------------------

def score_ad_toxicity(
    analysis_data: Dict[str, Any],
    use_ai: Optional[bool] = None
) -> Dict[str, Any]:
    """
    Convenience function to score ad toxicity.
    
    Args:
        analysis_data: Combined output from physics_engine and analysis modules
        use_ai: Override AI usage (None = use config, True/False = force)
    
    Returns:
        Toxicity report dictionary with AI analysis if enabled
    """
    scorer = ToxicityScorer(analysis_data, use_ai=use_ai)
    return scorer.calculate_toxicity()


def score_ad_toxicity_ai(analysis_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Score ad toxicity with AI enhancement forced on.
    
    Args:
        analysis_data: Combined output from physics_engine and analysis modules
    
    Returns:
        Toxicity report dictionary with AI analysis
    
    Raises:
        RuntimeError: If AI (Gemini) is not available
    """
    if not GENAI_AVAILABLE:
        raise RuntimeError(
            "google-genai package is not installed. "
            "Install with: pip install google-genai"
        )
    
    scorer = ToxicityScorer(analysis_data, use_ai=True)
    return scorer.calculate_toxicity()


def score_ad_toxicity_regex_only(analysis_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Score ad toxicity with regex-only detection (no AI).
    
    Args:
        analysis_data: Combined output from physics_engine and analysis modules
    
    Returns:
        Toxicity report dictionary without AI analysis
    """
    scorer = ToxicityScorer(analysis_data, use_ai=False)
    return scorer.calculate_toxicity()


def is_ad_safe(
    analysis_data: Dict[str, Any],
    threshold: int = RISK_LOW_MAX,
    use_ai: Optional[bool] = None
) -> Tuple[bool, Dict]:
    """
    Quick check if an ad is considered safe.
    
    Args:
        analysis_data: Combined output from physics_engine and analysis modules
        threshold: Maximum acceptable toxicity score (default: 30)
        use_ai: Override AI usage (None = use config, True/False = force)
    
    Returns:
        Tuple of (is_safe: bool, report: dict)
    """
    report = score_ad_toxicity(analysis_data, use_ai=use_ai)
    return report["toxic_score"] <= threshold, report

