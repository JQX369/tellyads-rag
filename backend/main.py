from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import os
import hmac
import secrets
from pathlib import Path
import json
import logging
from tvads_rag.tvads_rag import retrieval, db_backend

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("api")

app = FastAPI(
    title="TellyAds RAG API",
    description="Semantic Search API for TellyAds Archive",
    version="1.0.0"
)

# Configure CORS
origins = [
    "http://localhost:3000",
    "https://tellyads.com",
    "https://www.tellyads.com",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Models ---

class SearchRequest(BaseModel):
    query: str
    limit: int = 20
    offset: int = 0

class InteractionRequest(BaseModel):
    session_id: str

class TagSuggestionRequest(BaseModel):
    session_id: str
    tag: str

class TagModerationRequest(BaseModel):
    status: str  # 'approved', 'rejected', 'spam'
    reason: Optional[str] = None

class ReasonSubmissionRequest(BaseModel):
    session_id: str
    reasons: List[str]  # e.g., ['funny', 'clever_idea', 'emotional']
    reaction_type: str = 'like'  # 'like' or 'save'

class SearchResult(BaseModel):
    id: str
    external_id: str
    brand_name: Optional[str] = None
    product_name: Optional[str] = None
    text: Optional[str] = None
    score: Optional[float] = None
    meta: Optional[Dict[str, Any]] = None
    item_type: str

class AdDetail(BaseModel):
    id: str
    external_id: str
    brand_name: Optional[str] = None
    product_name: Optional[str] = None
    description: Optional[str] = None
    duration_seconds: Optional[float] = None
    year: Optional[int] = None
    analysis: Optional[Dict[str, Any]] = None
    impact_scores: Optional[Dict[str, Any]] = None
    video_url: Optional[str] = None
    image_url: Optional[str] = None
    # Toxicity fields
    toxicity_total: Optional[float] = None
    toxicity_risk_level: Optional[str] = None
    toxicity_labels: Optional[List[str]] = None

from backend.csv_parser import get_video_url_from_csv, get_image_url_from_csv

# --- Endpoints ---

@app.get("/api/status")
async def get_status():
    """System health check"""
    try:
        # Check DB connection by running a simple query
        if db_backend.ad_exists(external_id="check_connection"):
            pass 
        return {"status": "online", "db": "connected", "version": "1.0.0"}
    except Exception as e:
        logger.error(f"Status check failed: {e}")
        return {"status": "degraded", "error": str(e)}

@app.post("/api/search", response_model=List[SearchResult])
async def search_ads(request: SearchRequest):
    """Semantic/Hybrid search endpoint"""
    try:
        results = retrieval.retrieve_with_rerank(
            request.query, 
            final_k=request.limit
        )
        
        response = []
        for r in results:
            response.append(SearchResult(
                id=str(r.get("ad_id", "")), # Assuming ad_id is available in retrieval result
                external_id=r.get("external_id", "Unknown"), # Need to ensure retrieval returns this
                brand_name=r.get("brand_name"),
                product_name=r.get("product_name"),
                text=r.get("text"),
                score=r.get("rerank_score") or r.get("rrf_score"),
                meta=r.get("meta"),
                item_type=r.get("item_type", "unknown")
            ))
        return response
    except Exception as e:
        logger.error(f"Search failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/ads/{external_id}", response_model=AdDetail)
async def get_ad_detail(external_id: str):
    """Get detailed ad metadata"""
    try:
        # We need a function to get ad by external_id. 
        # db_backend.ad_exists checks existence, but we need retrieval.
        # Assuming we can query by external_id directly via DB connection or helper.
        
        # For now, using a direct DB query approach as db_backend might not have a "get_by_external_id" exposed yet.
        # Ideally, add `get_ad_by_external_id` to db_backend.py
        
        conn = db_backend.get_connection()
        if not conn:
             raise HTTPException(status_code=503, detail="Database unavailable")
             
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT * FROM ads WHERE external_id = %s", 
                    (external_id,)
                )
                row = cur.fetchone()
                if not row:
                    raise HTTPException(status_code=404, detail="Ad not found")
                
                # Convert row to dict
                ad_data = dict(row)
                
                return AdDetail(
                    id=str(ad_data.get("id")),
                    external_id=ad_data.get("external_id"),
                    brand_name=ad_data.get("brand_name"),
                    product_name=ad_data.get("product_name"),
                    description=ad_data.get("one_line_summary"),
                    duration_seconds=ad_data.get("duration_seconds"),
                    year=ad_data.get("year"),
                    analysis=ad_data.get("analysis_json"),
                    impact_scores=ad_data.get("impact_scores"),
                    video_url=get_video_url_from_csv(external_id),
                    image_url=get_image_url_from_csv(external_id),
                    # Toxicity fields
                    toxicity_total=ad_data.get("toxicity_total"),
                    toxicity_risk_level=ad_data.get("toxicity_risk_level"),
                    toxicity_labels=ad_data.get("toxicity_labels") or [],
                )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get ad detail failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/ads/{external_id}/similar")
async def get_similar_ads(external_id: str, limit: int = 5):
    """Get similar ads based on content"""
    # Placeholder: In a real implementation, this would use the embedding of the current ad 
    # to find nearest neighbors.
    # For MVP, we might perform a text search using the ad's summary or brand.
    
    try:
        # Fetch ad summary to use as query
        conn = db_backend.get_connection()
        query_text = ""
        with conn:
             with conn.cursor() as cur:
                cur.execute("SELECT one_line_summary, brand_name FROM ads WHERE external_id = %s", (external_id,))
                row = cur.fetchone()
                if row:
                    query_text = f"{row['brand_name']} {row['one_line_summary']}"
        
        if not query_text:
            return []

        results = retrieval.retrieve_with_rerank(query_text, final_k=limit)
        # Filter out the ad itself if present
        filtered = [r for r in results if r.get("external_id") != external_id]
        return filtered[:limit]
        
    except Exception as e:
        logger.error(f"Similar ads failed: {e}")
        return []

@app.get("/api/recent")
async def get_recent_ads(
    limit: int = 20,
    offset: int = 0,
    max_toxicity: Optional[float] = Query(None, description="Max toxicity score (0-100)"),
    risk_level: Optional[str] = Query(None, description="Filter by risk level: LOW, MEDIUM, HIGH"),
    has_toxicity: Optional[bool] = Query(None, description="Filter to ads with toxicity scoring"),
):
    """Get recently indexed ads with optional toxicity filtering"""
    try:
        conn = db_backend.get_connection()
        with conn:
            with conn.cursor() as cur:
                # Build query with toxicity filters
                query = """
                    SELECT external_id, brand_name, product_name, one_line_summary,
                           created_at, toxicity_total, toxicity_risk_level
                    FROM ads
                    WHERE 1=1
                """
                params = []

                # Apply toxicity filters
                if max_toxicity is not None:
                    query += " AND (toxicity_total IS NULL OR toxicity_total <= %s)"
                    params.append(max_toxicity)

                if risk_level is not None:
                    query += " AND toxicity_risk_level = %s"
                    params.append(risk_level.upper())

                if has_toxicity is True:
                    query += " AND toxicity_total IS NOT NULL"
                elif has_toxicity is False:
                    query += " AND toxicity_total IS NULL"

                query += " ORDER BY created_at DESC LIMIT %s OFFSET %s"
                params.extend([limit, offset])

                cur.execute(query, params)
                rows = cur.fetchall()

                return [
                    {
                        "external_id": r["external_id"],
                        "brand_name": r["brand_name"],
                        "title": r["one_line_summary"],
                        "image_url": get_image_url_from_csv(r["external_id"]),
                        "toxicity_total": r.get("toxicity_total"),
                        "toxicity_risk_level": r.get("toxicity_risk_level"),
                    }
                    for r in rows
                ]
    except Exception as e:
        logger.error(f"Recent ads failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/brands")
async def get_brands():
    """List all brands"""
    try:
        conn = db_backend.get_connection()
        with conn:
            with conn.cursor() as cur:
                cur.execute("SELECT DISTINCT brand_name FROM ads ORDER BY brand_name")
                rows = cur.fetchall()
                return [r["brand_name"] for r in rows if r["brand_name"]]
    except Exception as e:
        logger.error(f"Get brands failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/stats")
async def get_stats():
    """Public stats"""
    try:
        conn = db_backend.get_connection()
        with conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) as count FROM ads")
                ad_count = cur.fetchone()["count"]

                cur.execute("SELECT COUNT(DISTINCT brand_name) as count FROM ads")
                brand_count = cur.fetchone()["count"]

                return {
                    "total_ads": ad_count,
                    "total_brands": brand_count
                }
    except Exception as e:
        logger.error(f"Get stats failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/stats/toxicity")
async def get_toxicity_stats():
    """Toxicity statistics: count by risk level, average score"""
    try:
        conn = db_backend.get_connection()
        with conn:
            with conn.cursor() as cur:
                # Count ads by risk level
                cur.execute("""
                    SELECT
                        toxicity_risk_level,
                        COUNT(*) as count,
                        AVG(toxicity_total) as avg_score
                    FROM ads
                    WHERE toxicity_total IS NOT NULL
                    GROUP BY toxicity_risk_level
                    ORDER BY
                        CASE toxicity_risk_level
                            WHEN 'LOW' THEN 1
                            WHEN 'MEDIUM' THEN 2
                            WHEN 'HIGH' THEN 3
                            ELSE 4
                        END
                """)
                by_risk = cur.fetchall()

                # Count ads with/without toxicity
                cur.execute("""
                    SELECT
                        COUNT(*) FILTER (WHERE toxicity_total IS NOT NULL) as with_toxicity,
                        COUNT(*) FILTER (WHERE toxicity_total IS NULL) as without_toxicity,
                        AVG(toxicity_total) as overall_avg
                    FROM ads
                """)
                summary = cur.fetchone()

                return {
                    "by_risk_level": [
                        {
                            "risk_level": r["toxicity_risk_level"] or "UNKNOWN",
                            "count": r["count"],
                            "avg_score": round(r["avg_score"], 1) if r["avg_score"] else None,
                        }
                        for r in by_risk
                    ],
                    "total_with_toxicity": summary["with_toxicity"],
                    "total_without_toxicity": summary["without_toxicity"],
                    "overall_avg_score": round(summary["overall_avg"], 1) if summary["overall_avg"] else None,
                }
    except Exception as e:
        logger.error(f"Get toxicity stats failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# FEEDBACK SYSTEM ENDPOINTS
# =============================================================================

@app.post("/api/ads/{external_id}/view")
async def record_view(external_id: str, request: InteractionRequest):
    """Record an ad view (rate-limited, increments counter)"""
    try:
        conn = db_backend.get_connection()
        with conn:
            with conn.cursor() as cur:
                # Get ad UUID
                cur.execute("SELECT id FROM ads WHERE external_id = %s", (external_id,))
                row = cur.fetchone()
                if not row:
                    raise HTTPException(status_code=404, detail="Ad not found")
                ad_id = row["id"]

                # Call view recording function
                cur.execute("SELECT fn_record_ad_view(%s, %s)", (ad_id, request.session_id))
                conn.commit()

        return {"status": "recorded"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Record view failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/ads/{external_id}/like")
async def toggle_like(external_id: str, request: InteractionRequest):
    """Toggle like state for an ad"""
    try:
        conn = db_backend.get_connection()
        with conn:
            with conn.cursor() as cur:
                # Get ad UUID
                cur.execute("SELECT id FROM ads WHERE external_id = %s", (external_id,))
                row = cur.fetchone()
                if not row:
                    raise HTTPException(status_code=404, detail="Ad not found")
                ad_id = row["id"]

                # Toggle like
                cur.execute("SELECT fn_toggle_like(%s, %s)", (ad_id, request.session_id))
                result = cur.fetchone()
                conn.commit()

        return {"is_liked": result[0] if result else False}
    except HTTPException:
        raise
    except Exception as e:
        if "Rate limit" in str(e):
            raise HTTPException(status_code=429, detail="Rate limit exceeded")
        logger.error(f"Toggle like failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/ads/{external_id}/save")
async def toggle_save(external_id: str, request: InteractionRequest):
    """Toggle save state for an ad"""
    try:
        conn = db_backend.get_connection()
        with conn:
            with conn.cursor() as cur:
                # Get ad UUID
                cur.execute("SELECT id FROM ads WHERE external_id = %s", (external_id,))
                row = cur.fetchone()
                if not row:
                    raise HTTPException(status_code=404, detail="Ad not found")
                ad_id = row["id"]

                # Toggle save
                cur.execute("SELECT fn_toggle_save(%s, %s)", (ad_id, request.session_id))
                result = cur.fetchone()
                conn.commit()

        return {"is_saved": result[0] if result else False}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Toggle save failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Scoring V2 constants (must match SQL schema_scoring_v2.sql)
REASON_DISPLAY_THRESHOLD = 10  # Min distinct sessions before public reason display


@app.get("/api/ads/{external_id}/feedback")
async def get_ad_feedback(external_id: str, session_id: Optional[str] = None):
    """Get feedback metrics for an ad, optionally with user's reaction state and reasons"""
    try:
        conn = db_backend.get_connection()
        with conn:
            with conn.cursor() as cur:
                # Get ad UUID and feedback agg (including V2 score components)
                cur.execute("""
                    SELECT
                        a.id,
                        COALESCE(f.view_count, 0) as view_count,
                        COALESCE(f.like_count, 0) as like_count,
                        COALESCE(f.save_count, 0) as save_count,
                        COALESCE(f.share_count, 0) as share_count,
                        COALESCE(f.engagement_score, 0) as engagement_score,
                        COALESCE(f.tag_counts, '{}'::jsonb) as tag_counts,
                        COALESCE(f.reason_counts, '{}'::jsonb) as reason_counts,
                        COALESCE(f.distinct_reason_sessions, 0) as distinct_reason_sessions,
                        COALESCE(f.ai_score, 50) as ai_score,
                        COALESCE(f.user_score, 0) as user_score,
                        COALESCE(f.confidence_weight, 0) as confidence_weight,
                        COALESCE(f.final_score, 50) as final_score
                    FROM ads a
                    LEFT JOIN ad_feedback_agg f ON f.ad_id = a.id
                    WHERE a.external_id = %s
                """, (external_id,))
                row = cur.fetchone()
                if not row:
                    raise HTTPException(status_code=404, detail="Ad not found")

                distinct_sessions = row["distinct_reason_sessions"]

                result = {
                    "view_count": row["view_count"],
                    "like_count": row["like_count"],
                    "save_count": row["save_count"],
                    "share_count": row["share_count"],
                    "engagement_score": float(row["engagement_score"]) if row["engagement_score"] else 0,
                    "user_tags": row["tag_counts"] or {},
                    # Scoring V2: AI + User blended
                    "ai_score": float(row["ai_score"]) if row["ai_score"] else 50,
                    "user_score": float(row["user_score"]) if row["user_score"] else 0,
                    "confidence_weight": float(row["confidence_weight"]) if row["confidence_weight"] else 0,
                    "final_score": float(row["final_score"]) if row["final_score"] else 50,
                    # Anti-gaming: only show reason_counts if threshold met
                    "reason_counts": row["reason_counts"] if distinct_sessions >= REASON_DISPLAY_THRESHOLD else {},
                    "distinct_reason_sessions": distinct_sessions,
                    "reason_threshold_met": distinct_sessions >= REASON_DISPLAY_THRESHOLD,
                }

                # Get user's reaction state if session_id provided
                if session_id:
                    cur.execute("""
                        SELECT is_liked, is_saved
                        FROM ad_user_reactions
                        WHERE ad_id = %s AND session_id = %s
                    """, (row["id"], session_id))
                    user_row = cur.fetchone()
                    result["user_reaction"] = {
                        "is_liked": user_row["is_liked"] if user_row else False,
                        "is_saved": user_row["is_saved"] if user_row else False,
                    }

                    # Also get user's submitted reasons
                    cur.execute("""
                        SELECT reason, reaction_type
                        FROM ad_like_reasons
                        WHERE ad_id = %s AND session_id = %s
                    """, (row["id"], session_id))
                    reason_rows = cur.fetchall()
                    result["user_reasons"] = [
                        {"reason": r["reason"], "reaction_type": r["reaction_type"]}
                        for r in reason_rows
                    ]

        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get feedback failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/ads/{external_id}/tags")
async def suggest_tag(external_id: str, request: TagSuggestionRequest):
    """Suggest a tag for an ad (requires moderation)"""
    try:
        conn = db_backend.get_connection()
        with conn:
            with conn.cursor() as cur:
                # Get ad UUID
                cur.execute("SELECT id FROM ads WHERE external_id = %s", (external_id,))
                row = cur.fetchone()
                if not row:
                    raise HTTPException(status_code=404, detail="Ad not found")
                ad_id = row["id"]

                # Suggest tag
                cur.execute(
                    "SELECT fn_suggest_tag(%s, %s, %s)",
                    (ad_id, request.session_id, request.tag)
                )
                result = cur.fetchone()
                conn.commit()

        return {"tag_id": str(result[0]) if result and result[0] else None, "status": "pending"}
    except HTTPException:
        raise
    except Exception as e:
        if "Rate limit" in str(e):
            raise HTTPException(status_code=429, detail="Rate limit exceeded")
        if "Invalid tag" in str(e):
            raise HTTPException(status_code=400, detail="Invalid tag format (2-30 alphanumeric characters)")
        logger.error(f"Suggest tag failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/ads/{external_id}/tags")
async def get_ad_tags(external_id: str):
    """Get approved tags for an ad"""
    try:
        conn = db_backend.get_connection()
        with conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT t.tag, COUNT(*) as count
                    FROM ad_user_tags t
                    JOIN ads a ON a.id = t.ad_id
                    WHERE a.external_id = %s AND t.status = 'approved'
                    GROUP BY t.tag
                    ORDER BY count DESC
                """, (external_id,))
                rows = cur.fetchall()

        return {"tags": [{"tag": r["tag"], "count": r["count"]} for r in rows]}
    except Exception as e:
        logger.error(f"Get tags failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# MICRO-REASONS ENDPOINTS (Why did you like/save this?)
# =============================================================================

# Valid reasons (matches SQL CHECK constraint)
VALID_REASONS = {
    'funny', 'clever_idea', 'emotional', 'great_twist', 'beautiful_visually',
    'memorable_music', 'relatable', 'effective_message', 'nostalgic', 'surprising'
}

# Reason labels for UI
REASON_LABELS = [
    {"reason": "funny", "label": "Funny", "emoji": ""},
    {"reason": "clever_idea", "label": "Clever idea", "emoji": ""},
    {"reason": "emotional", "label": "Emotional", "emoji": ""},
    {"reason": "great_twist", "label": "Great twist/ending", "emoji": ""},
    {"reason": "beautiful_visually", "label": "Beautiful visually", "emoji": ""},
    {"reason": "memorable_music", "label": "Memorable music", "emoji": ""},
    {"reason": "relatable", "label": "Relatable", "emoji": ""},
    {"reason": "effective_message", "label": "Effective message", "emoji": ""},
    {"reason": "nostalgic", "label": "Nostalgic", "emoji": ""},
    {"reason": "surprising", "label": "Surprising", "emoji": ""},
]


@app.get("/api/reason-labels")
async def get_reason_labels():
    """Get predefined reason labels for UI (no auth required)"""
    return {"reasons": REASON_LABELS}


@app.post("/api/ads/{external_id}/reasons")
async def submit_reasons(external_id: str, request: ReasonSubmissionRequest):
    """Submit reasons for why you liked/saved an ad (rate-limited)"""
    # Validate reasons
    invalid_reasons = [r for r in request.reasons if r not in VALID_REASONS]
    if invalid_reasons:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid reasons: {invalid_reasons}. Valid: {list(VALID_REASONS)}"
        )

    if request.reaction_type not in ('like', 'save'):
        raise HTTPException(status_code=400, detail="reaction_type must be 'like' or 'save'")

    if not request.reasons:
        raise HTTPException(status_code=400, detail="At least one reason required")

    try:
        conn = db_backend.get_connection()
        with conn:
            with conn.cursor() as cur:
                # Get ad UUID
                cur.execute("SELECT id FROM ads WHERE external_id = %s", (external_id,))
                row = cur.fetchone()
                if not row:
                    raise HTTPException(status_code=404, detail="Ad not found")
                ad_id = row["id"]

                # Call the helper function
                cur.execute(
                    "SELECT fn_add_reasons(%s, %s, %s, %s)",
                    (ad_id, request.session_id, request.reasons, request.reaction_type)
                )
                result = cur.fetchone()
                conn.commit()

        inserted_count = result[0] if result else 0
        return {
            "status": "recorded",
            "reasons_added": inserted_count,
            "submitted": request.reasons
        }
    except HTTPException:
        raise
    except Exception as e:
        if "Rate limit" in str(e):
            raise HTTPException(status_code=429, detail="Rate limit exceeded")
        logger.error(f"Submit reasons failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/ads/{external_id}/reasons")
async def get_ad_reasons(external_id: str, session_id: Optional[str] = None):
    """Get reason counts for an ad, optionally with user's submitted reasons"""
    try:
        conn = db_backend.get_connection()
        with conn:
            with conn.cursor() as cur:
                # Get ad UUID and reason counts from agg table (V2 scoring)
                cur.execute("""
                    SELECT
                        a.id,
                        COALESCE(f.reason_counts, '{}'::jsonb) as reason_counts,
                        COALESCE(f.distinct_reason_sessions, 0) as distinct_reason_sessions,
                        COALESCE(f.ai_score, 50) as ai_score,
                        COALESCE(f.user_score, 0) as user_score,
                        COALESCE(f.confidence_weight, 0) as confidence_weight,
                        COALESCE(f.final_score, 50) as final_score
                    FROM ads a
                    LEFT JOIN ad_feedback_agg f ON f.ad_id = a.id
                    WHERE a.external_id = %s
                """, (external_id,))
                row = cur.fetchone()
                if not row:
                    raise HTTPException(status_code=404, detail="Ad not found")

                distinct_sessions = row["distinct_reason_sessions"]

                result = {
                    # Anti-gaming: only show reason_counts if threshold met
                    "reason_counts": row["reason_counts"] if distinct_sessions >= REASON_DISPLAY_THRESHOLD else {},
                    "distinct_reason_sessions": distinct_sessions,
                    "reason_threshold_met": distinct_sessions >= REASON_DISPLAY_THRESHOLD,
                    # Scoring V2 components
                    "ai_score": float(row["ai_score"]) if row["ai_score"] else 50,
                    "user_score": float(row["user_score"]) if row["user_score"] else 0,
                    "confidence_weight": float(row["confidence_weight"]) if row["confidence_weight"] else 0,
                    "final_score": float(row["final_score"]) if row["final_score"] else 50,
                }

                # Get user's submitted reasons if session_id provided
                if session_id:
                    cur.execute("""
                        SELECT reason, reaction_type
                        FROM ad_like_reasons
                        WHERE ad_id = %s AND session_id = %s
                    """, (row["id"], session_id))
                    user_rows = cur.fetchall()
                    result["user_reasons"] = [
                        {"reason": r["reason"], "reaction_type": r["reaction_type"]}
                        for r in user_rows
                    ]

        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get reasons failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# SEO-FRIENDLY ADVERT ROUTE (supports /advert/{brand_slug}/{slug})
# =============================================================================

@app.get("/api/advert/{brand_slug}/{slug}")
async def get_ad_by_slug(brand_slug: str, slug: str):
    """Get ad by SEO-friendly URL path (enforces publish gating)"""
    try:
        conn = db_backend.get_connection()
        with conn:
            with conn.cursor() as cur:
                # Editorial lookup with publish gating:
                # - status = 'published'
                # - publish_date IS NULL OR publish_date <= NOW()
                # - is_hidden = false
                cur.execute("""
                    SELECT a.*, e.headline, e.editorial_summary, e.curated_tags,
                           e.override_brand_name, e.override_year, e.override_product_category,
                           e.status, e.publish_date,
                           COALESCE(f.view_count, 0) as view_count,
                           COALESCE(f.like_count, 0) as like_count
                    FROM ad_editorial e
                    JOIN ads a ON a.id = e.ad_id
                    LEFT JOIN ad_feedback_agg f ON f.ad_id = a.id
                    WHERE e.brand_slug = %s
                      AND e.slug = %s
                      AND e.status = 'published'
                      AND e.is_hidden = false
                      AND (e.publish_date IS NULL OR e.publish_date <= NOW())
                """, (brand_slug.lower(), slug.lower()))
                row = cur.fetchone()

                if not row:
                    raise HTTPException(status_code=404, detail="Ad not found")

                ad_data = dict(row)

                return {
                    "id": str(ad_data.get("id")),
                    "external_id": ad_data.get("external_id"),
                    "brand_name": ad_data.get("override_brand_name") or ad_data.get("brand_name"),
                    "product_name": ad_data.get("product_name"),
                    "headline": ad_data.get("headline"),
                    "description": ad_data.get("editorial_summary") or ad_data.get("one_line_summary"),
                    "curated_tags": ad_data.get("curated_tags") or [],
                    "year": ad_data.get("override_year") or ad_data.get("year"),
                    "product_category": ad_data.get("override_product_category") or ad_data.get("product_category"),
                    "duration_seconds": ad_data.get("duration_seconds"),
                    "video_url": get_video_url_from_csv(ad_data.get("external_id")),
                    "image_url": get_image_url_from_csv(ad_data.get("external_id")),
                    "view_count": ad_data.get("view_count", 0),
                    "like_count": ad_data.get("like_count", 0),
                    "impact_scores": ad_data.get("impact_scores"),
                    "analysis": ad_data.get("analysis_json"),
                }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get ad by slug failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# ADMIN: TAG MODERATION ENDPOINTS
# =============================================================================

# Admin API key auth dependency
# Supports key rotation: comma-separated keys in ADMIN_API_KEYS (or single key in ADMIN_API_KEY)
def _get_admin_keys() -> List[str]:
    """Get list of valid admin API keys (supports rotation)"""
    keys_str = os.getenv("ADMIN_API_KEYS") or os.getenv("ADMIN_API_KEY")
    if not keys_str:
        return []
    return [k.strip() for k in keys_str.split(",") if k.strip()]

def verify_admin_key(request: Request):
    """Verify admin API key from header (timing-safe comparison)"""
    valid_keys = _get_admin_keys()
    if not valid_keys:
        raise HTTPException(status_code=503, detail="Admin auth not configured")

    auth_header = request.headers.get("X-Admin-Key") or request.headers.get("Authorization")
    if not auth_header:
        raise HTTPException(status_code=401, detail="Missing admin key")

    # Support both "X-Admin-Key: <key>" and "Authorization: Bearer <key>"
    provided_key = auth_header.replace("Bearer ", "").strip()

    # Timing-safe comparison against all valid keys
    is_valid = any(
        hmac.compare_digest(provided_key.encode(), valid_key.encode())
        for valid_key in valid_keys
    )

    if not is_valid:
        raise HTTPException(status_code=403, detail="Invalid admin key")


@app.get("/api/admin/tags/pending")
async def get_pending_tags(request: Request, limit: int = 50):
    """Get pending tag suggestions for moderation (requires admin key)"""
    verify_admin_key(request)
    try:
        conn = db_backend.get_connection()
        with conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT
                        t.id, t.ad_id, t.tag, t.session_id, t.created_at,
                        a.external_id, a.brand_name, a.product_name
                    FROM ad_user_tags t
                    JOIN ads a ON a.id = t.ad_id
                    WHERE t.status = 'pending'
                    ORDER BY t.created_at ASC
                    LIMIT %s
                """, (limit,))
                rows = cur.fetchall()

        return {
            "pending_count": len(rows),
            "tags": [
                {
                    "id": str(r["id"]),
                    "ad_id": str(r["ad_id"]),
                    "external_id": r["external_id"],
                    "brand_name": r["brand_name"],
                    "tag": r["tag"],
                    "created_at": r["created_at"].isoformat() if r["created_at"] else None,
                }
                for r in rows
            ]
        }
    except Exception as e:
        logger.error(f"Get pending tags failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.patch("/api/admin/tags/{tag_id}")
async def moderate_tag(tag_id: str, body: TagModerationRequest, request: Request):
    """Approve or reject a tag suggestion (requires admin key)"""
    verify_admin_key(request)
    if body.status not in ('approved', 'rejected', 'spam'):
        raise HTTPException(status_code=400, detail="Invalid status")

    try:
        conn = db_backend.get_connection()
        with conn:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE ad_user_tags
                    SET status = %s, moderated_at = now(), rejection_reason = %s
                    WHERE id = %s
                    RETURNING id
                """, (body.status, body.reason, tag_id))
                result = cur.fetchone()
                conn.commit()

                if not result:
                    raise HTTPException(status_code=404, detail="Tag not found")

        return {"status": "updated", "new_status": body.status}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Moderate tag failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

