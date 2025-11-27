from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import os
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
                    image_url=get_image_url_from_csv(external_id)
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
async def get_recent_ads(limit: int = 20, offset: int = 0):
    """Get recently indexed ads"""
    try:
        conn = db_backend.get_connection()
        with conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT external_id, brand_name, product_name, one_line_summary, created_at 
                    FROM ads 
                    ORDER BY created_at DESC 
                    LIMIT %s OFFSET %s
                """, (limit, offset))
                rows = cur.fetchall()
                
                return [
                    {
                        "external_id": r["external_id"],
                        "brand_name": r["brand_name"],
                        "title": r["one_line_summary"],
                        "image_url": get_image_url_from_csv(r["external_id"])
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

