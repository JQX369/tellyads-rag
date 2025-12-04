import os
import subprocess
import sys
import tempfile
import time
import json
from pathlib import Path

import dotenv
import streamlit as st
from streamlit.runtime.scriptrunner import add_script_run_ctx

# Import config to clear caches
try:
    from tvads_rag.tvads_rag import config as tvads_config
except ImportError:
    tvads_config = None

# --- Config & Setup ---
st.set_page_config(
    page_title="TellyAds RAG Admin",
    page_icon="📺",
    layout="wide",
    initial_sidebar_state="expanded",
)

ENV_PATH = Path(".env")
LOG_FILE = Path("pipeline.log")

# Ensure .env exists
if not ENV_PATH.exists():
    ENV_PATH.touch()


def load_env_vars():
    """Reload environment variables from file."""
    dotenv.load_dotenv(ENV_PATH, override=True)


def save_env_var(key: str, value: str):
    """Update a single key in the .env file."""
    dotenv.set_key(ENV_PATH, key, value)
    load_env_vars()
    # Clear config caches so new values are picked up
    if tvads_config:
        tvads_config.get_db_config.cache_clear()
        tvads_config.get_openai_config.cache_clear()
        tvads_config.get_vision_config.cache_clear()
        tvads_config.get_rerank_config.cache_clear()
        tvads_config.get_storage_config.cache_clear()
        tvads_config.get_pipeline_config.cache_clear()


def run_command(command_list, cwd=None, log_to_file=False):
    """Run a subprocess command and stream output.

    Notes:
    - We force UTF-8 decoding but allow replacement of invalid bytes so that
      Windows-encoded output (e.g. cp1252 bullets) doesn't crash the dashboard.
    """
    try:
        process = subprocess.Popen(
            command_list,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            cwd=cwd,
            encoding="utf-8",
            errors="replace",
        )
        
        output_buffer = ""
        while True:
            line = process.stdout.readline()
            if not line and process.poll() is not None:
                break
            if line:
                output_buffer += line
                if log_to_file:
                    with open(LOG_FILE, "a", encoding="utf-8") as f:
                        f.write(line)
                yield line
        
        if process.returncode != 0:
            yield f"\nError: Process exited with code {process.returncode}"
            
    except Exception as e:
        yield f"\nException running command: {e}"


# --- Sidebar ---
st.sidebar.title("📺 RAG Admin")
load_env_vars()

# Status Checks
st.sidebar.subheader("System Status")
if os.getenv("OPENAI_API_KEY"):
    st.sidebar.success("✅ OpenAI Key Set")
else:
    st.sidebar.error("❌ OpenAI Key Missing")

if os.getenv("SUPABASE_DB_URL"):
    st.sidebar.success("✅ Database Configured")
else:
    st.sidebar.error("❌ Database Missing")

try:
    import cohere
    st.sidebar.success("✅ Cohere Installed")
except ImportError:
    st.sidebar.warning("⚠️ Cohere Missing")

try:
    import psycopg2
    st.sidebar.success("✅ Psycopg2 Installed")
except ImportError:
    st.sidebar.error("❌ Psycopg2 Missing")


# --- Main Tabs ---
tab_config, tab_setup, tab_ingest, tab_browser, tab_search, tab_chat = st.tabs(
    ["⚙️ Configuration", "🛠️ Setup", "📥 Ingestion", "📊 Ad Browser", "🔍 Search & Eval", "💬 AI Chat"]
)

# --- Tab 1: Configuration ---
with tab_config:
    st.header("Environment Configuration")
    st.info("Values are saved directly to `.env`.")

    with st.form("env_config_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Database & Storage")
            st.text_input("SUPABASE_URL", value=os.getenv("SUPABASE_URL", ""), key="env_SUPABASE_URL")
            st.text_input("SUPABASE_SERVICE_KEY", value=os.getenv("SUPABASE_SERVICE_KEY", ""), key="env_SUPABASE_SERVICE_KEY", type="password")
            st.text_input("SUPABASE_DB_URL", value=os.getenv("SUPABASE_DB_URL", ""), key="env_SUPABASE_DB_URL", type="password", help="Postgres connection string")
            db_backend_default = os.getenv("DB_BACKEND", "postgres")
            db_backend = st.selectbox(
                "DB_BACKEND",
                ["postgres", "http"],
                index=0 if db_backend_default != "http" else 1,
                help="Use 'http' to talk to Supabase via HTTPS (REST/RPC) instead of direct Postgres. Helpful if port 5432 is blocked.",
            )
            
            st.divider()
            st.subheader("Storage")
            video_source = st.selectbox("VIDEO_SOURCE_TYPE", ["local", "s3"], index=0 if os.getenv("VIDEO_SOURCE_TYPE") == "local" else 1)
            st.text_input("LOCAL_VIDEO_DIR", value=os.getenv("LOCAL_VIDEO_DIR", "videos"), key="env_LOCAL_VIDEO_DIR")
            st.text_input("S3_BUCKET", value=os.getenv("S3_BUCKET", ""), key="env_S3_BUCKET")
            st.text_input("S3_PREFIX", value=os.getenv("S3_PREFIX", ""), key="env_S3_PREFIX")
            st.text_input("AWS_ACCESS_KEY_ID", value=os.getenv("AWS_ACCESS_KEY_ID", ""), key="env_AWS_ACCESS_KEY_ID")
            st.text_input("AWS_SECRET_ACCESS_KEY", value=os.getenv("AWS_SECRET_ACCESS_KEY", ""), key="env_AWS_SECRET_ACCESS_KEY", type="password")

        with col2:
            st.subheader("AI Models")
            st.text_input("OPENAI_API_KEY", value=os.getenv("OPENAI_API_KEY", ""), key="env_OPENAI_API_KEY", type="password")
            st.text_input("TEXT_LLM_MODEL", value=os.getenv("TEXT_LLM_MODEL", "gpt-5.1"), key="env_TEXT_LLM_MODEL")
            st.text_input("EMBEDDING_MODEL", value=os.getenv("EMBEDDING_MODEL", "text-embedding-3-large"), key="env_EMBEDDING_MODEL")
            
            st.divider()
            st.subheader("Vision (Gemini)")
            st.info("""
            **Vision Tier Explanation:**
            - **Fast (Gemini 2.5 Flash)**: Used for standard storyboard analysis of all ads. Faster processing, lower cost (~$0.075 per 1M tokens).
            - **Quality (Gemini 3 Pro Preview)**: Automatically used for Deep Hero Analysis of top 10% viewed ads. Slower, higher cost (~$2 per 1M tokens input), but provides detailed cinematography, emotional arc, and creative tactics analysis with advanced reasoning.
            
            The `VISION_DEFAULT_TIER` controls which tier is used for regular storyboard analysis. Hero ads always use Quality tier regardless of this setting.
            """)
            st.text_input("GOOGLE_API_KEY", value=os.getenv("GOOGLE_API_KEY", ""), key="env_GOOGLE_API_KEY", type="password")
            st.selectbox("VISION_PROVIDER", ["none", "google"], index=1 if os.getenv("VISION_PROVIDER") == "google" else 0, key="env_VISION_PROVIDER")
            st.text_input("VISION_MODEL_FAST", value=os.getenv("VISION_MODEL_FAST", "gemini-2.5-flash"), key="env_VISION_MODEL_FAST", help="Fast tier: Gemini 2.5 Flash - faster, lower cost, good for standard storyboard analysis")
            st.text_input("VISION_MODEL_QUALITY", value=os.getenv("VISION_MODEL_QUALITY", "gemini-3-pro-preview"), key="env_VISION_MODEL_QUALITY", help="Quality tier: Gemini 3 Pro Preview - used for hero ads (top 10% by views), best for deep analysis")
            st.selectbox("VISION_DEFAULT_TIER", ["fast", "quality"], index=0 if os.getenv("VISION_DEFAULT_TIER") == "fast" else 1, key="env_VISION_DEFAULT_TIER")
            frame_sample_default = float(os.getenv("FRAME_SAMPLE_SECONDS", "1.0"))
            st.number_input("FRAME_SAMPLE_SECONDS", value=frame_sample_default, min_value=0.1, max_value=10.0, step=0.1, key="env_FRAME_SAMPLE_SECONDS", help="How often to sample frames for storyboard analysis (seconds). Lower = more frames. Default: 1.0s. Hero ads use 0.75s.")
            
            st.divider()
            st.subheader("Reranking (Cohere)")
            st.selectbox("RERANK_PROVIDER", ["none", "cohere"], index=1 if os.getenv("RERANK_PROVIDER") == "cohere" else 0, key="env_RERANK_PROVIDER")
            st.text_input("RERANK_MODEL", value=os.getenv("RERANK_MODEL", "rerank-english-v3.0"), key="env_RERANK_MODEL")
            st.text_input("COHERE_API_KEY", value=os.getenv("COHERE_API_KEY", ""), key="env_COHERE_API_KEY", type="password")

        if st.form_submit_button("💾 Save Configuration"):
            # Save all form values
            save_env_var("SUPABASE_URL", str(st.session_state.get("env_SUPABASE_URL", "")))
            save_env_var("SUPABASE_SERVICE_KEY", str(st.session_state.get("env_SUPABASE_SERVICE_KEY", "")))
            save_env_var("SUPABASE_DB_URL", str(st.session_state.get("env_SUPABASE_DB_URL", "")))
            save_env_var("DB_BACKEND", str(db_backend))
            save_env_var("VIDEO_SOURCE_TYPE", str(video_source))
            save_env_var("LOCAL_VIDEO_DIR", str(st.session_state.get("env_LOCAL_VIDEO_DIR", "")))
            save_env_var("S3_BUCKET", str(st.session_state.get("env_S3_BUCKET", "")))
            save_env_var("S3_PREFIX", str(st.session_state.get("env_S3_PREFIX", "")))
            save_env_var("AWS_ACCESS_KEY_ID", str(st.session_state.get("env_AWS_ACCESS_KEY_ID", "")))
            save_env_var("AWS_SECRET_ACCESS_KEY", str(st.session_state.get("env_AWS_SECRET_ACCESS_KEY", "")))
            save_env_var("OPENAI_API_KEY", str(st.session_state.get("env_OPENAI_API_KEY", "")))
            save_env_var("TEXT_LLM_MODEL", str(st.session_state.get("env_TEXT_LLM_MODEL", "")))
            save_env_var("EMBEDDING_MODEL", str(st.session_state.get("env_EMBEDDING_MODEL", "")))
            save_env_var("GOOGLE_API_KEY", str(st.session_state.get("env_GOOGLE_API_KEY", "")))
            save_env_var("VISION_PROVIDER", str(st.session_state.get("env_VISION_PROVIDER", "none")))
            save_env_var("VISION_MODEL_FAST", str(st.session_state.get("env_VISION_MODEL_FAST", "")))
            save_env_var("VISION_MODEL_QUALITY", str(st.session_state.get("env_VISION_MODEL_QUALITY", "")))
            save_env_var("VISION_DEFAULT_TIER", str(st.session_state.get("env_VISION_DEFAULT_TIER", "fast")))
            save_env_var("FRAME_SAMPLE_SECONDS", str(st.session_state.get("env_FRAME_SAMPLE_SECONDS", 1.0)))
            save_env_var("RERANK_PROVIDER", str(st.session_state.get("env_RERANK_PROVIDER", "none")))
            save_env_var("RERANK_MODEL", str(st.session_state.get("env_RERANK_MODEL", "")))
            save_env_var("COHERE_API_KEY", str(st.session_state.get("env_COHERE_API_KEY", "")))
            st.success("Configuration saved and reloaded! Config caches cleared.")
            time.sleep(1)
            st.rerun()


# --- Tab 2: Setup ---
with tab_setup:
    st.header("System Setup")
    col_setup1, col_setup2 = st.columns(2)
    
    with col_setup1:
        st.subheader("Dependencies")
        if st.button("📦 Install Requirements"):
            with st.status("Installing dependencies...", expanded=True) as status:
                st.write("Running `pip install -r tvads_rag/requirements.txt`...")
                container = st.empty()
                output = ""
                for line in run_command([sys.executable, "-m", "pip", "install", "-r", "tvads_rag/requirements.txt"]):
                    output += line
                    container.code(output[-2000:], language="bash") # tail last 2000 chars
                status.update(label="Dependencies installed!", state="complete")

    with col_setup2:
        st.subheader("Database Schema")
        if st.button("🗄️ Apply Schema"):
            with st.status("Applying database schema...", expanded=True) as status:
                st.write("Running `tvads_rag/apply_schema.py`...")
                container = st.empty()
                output = ""
                for line in run_command([sys.executable, "tvads_rag/apply_schema.py"]):
                    output += line
                    container.code(output, language="text")
                status.update(label="Schema operation finished.", state="complete")


# --- Tab 3: Ingestion ---
with tab_ingest:
    st.header("Ad Ingestion Pipeline")
    
    # Auto-detect default metadata CSV
    DEFAULT_METADATA_CSV = Path("TELLY+ADS (2).csv")
    has_default_csv = DEFAULT_METADATA_CSV.exists()
    
    col_ingest_ctrl, col_ingest_log = st.columns([1, 2])
    
    with col_ingest_ctrl:
        st.subheader("Controls")
        ingest_source = st.selectbox("Source Override", ["Default (.env)", "local", "s3"])
        vision_tier_override = st.selectbox("Vision Tier", ["Default (.env)", "fast", "quality"])
        limit_ads = st.number_input("Limit (0 for all)", min_value=0, value=0)
        offset_ads = st.number_input("Offset", min_value=0, value=0)
        
        # Minimum external_id filter (e.g., TA1665) - optional
        min_id_input = st.text_input(
            "Minimum External ID (optional)", 
            value="",
            placeholder="e.g., TA1665",
            help="Only process ads with external_id >= this value. Leave empty to process all ads."
        )
        
        # Metadata CSV handling - auto-detect default file
        st.subheader("📊 Metadata CSV")
        use_default_csv = False
        metadata_upload = None
        if has_default_csv:
            st.success(f"✅ Default metadata: `{DEFAULT_METADATA_CSV.name}` (auto-detected)")
            use_default_csv = st.checkbox("Use default metadata CSV", value=True)
            if not use_default_csv:
                metadata_upload = st.file_uploader("Upload custom CSV", type=["csv"])
        else:
            st.warning("No default metadata CSV found. Upload one if needed.")
            metadata_upload = st.file_uploader("Metadata CSV (optional)", type=["csv"])
        
        start_ingest = st.button("🚀 Start Indexing", type="primary")
        
        st.divider()
        st.caption("Log file: `pipeline.log`")
        if st.button("Clear Log"):
            if LOG_FILE.exists():
                LOG_FILE.write_text("")
                st.success("Log cleared.")
        
        st.divider()
        st.subheader("🗑️ Reset Ads")
        st.warning("Deleting ads will remove all associated data (chunks, segments, claims, embeddings, etc.)")
        
        reset_mode = st.radio("Reset Mode", ["Last N", "All Ads"], horizontal=True)
        reset_n = 3
        if reset_mode == "Last N":
            reset_n = st.number_input("Number to delete", min_value=1, max_value=100, value=3)
        
        if st.button("🗑️ Delete Ads", type="secondary"):
            mode_arg = "lastN" if reset_mode == "Last N" else "all"
            cmd = [sys.executable, "-m", "tvads_rag.tvads_rag.reset_ads", "--mode", mode_arg, "-y"]
            if reset_mode == "Last N":
                cmd.extend(["--n", str(reset_n)])
            
            with st.status(f"Deleting ads ({reset_mode})...", expanded=True) as status:
                container = st.empty()
                output = ""
                for line in run_command(cmd):
                    output += line
                    container.code(output[-2000:], language="text")
                status.update(label="Reset complete", state="complete")
                # Clear all cached data so Ad Browser refreshes
                st.cache_data.clear()
                st.rerun()

    with col_ingest_log:
        st.subheader("Live Logs")
        log_container = st.empty()
        
        # Ingestion Runner
        if start_ingest:
            # Use the nested package path so Python can resolve the CLI module
            # when running from the project root.
            cmd = [sys.executable, "-m", "tvads_rag.tvads_rag.index_ads"]
            
            if ingest_source != "Default (.env)":
                cmd.extend(["--source", ingest_source])
            if vision_tier_override != "Default (.env)":
                cmd.extend(["--vision-tier", vision_tier_override])
            if limit_ads > 0:
                cmd.extend(["--limit", str(limit_ads)])
            if offset_ads > 0:
                cmd.extend(["--offset", str(offset_ads)])
            
            # Minimum external_id filter (optional)
            if min_id_input and min_id_input.strip():
                cmd.extend(["--min-id", min_id_input.strip()])
            
            # Metadata CSV handling
            metadata_temp_path = None
            if use_default_csv and has_default_csv:
                # Use the auto-detected default CSV
                cmd.extend(["--metadata-csv", str(DEFAULT_METADATA_CSV.absolute())])
            elif metadata_upload is not None:
                # Use uploaded CSV
                tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".csv")
                tmp.write(metadata_upload.getvalue())
                tmp.flush()
                tmp.close()
                metadata_temp_path = tmp.name
                cmd.extend(["--metadata-csv", metadata_temp_path])
            
            with st.status("Running Ingestion Pipeline...", expanded=True) as status:
                st.write(f"Command: `{' '.join(cmd)}`")
                # Clear previous log if starting new run
                with open(LOG_FILE, "w") as f:
                    f.write(f"--- Starting run at {time.ctime()} ---\n")
                
                # Run and stream to log file + UI
                output_text = ""
                for line in run_command(cmd, log_to_file=True):
                    output_text += line
                    # Update log view every few lines or just append
                    log_container.code(output_text[-5000:], language="text") # Keep UI responsive
                
                status.update(label="Ingestion Run Completed", state="complete")
                if metadata_temp_path:
                    try:
                        os.remove(metadata_temp_path)
                    except OSError:
                        pass

        else:
            # Passive log viewing
            if LOG_FILE.exists():
                log_content = LOG_FILE.read_text(encoding="utf-8")
                log_container.code(log_content[-5000:], language="text")
            else:
                log_container.info("No log file found.")


# --- Tab 4: Ad Browser ---
with tab_browser:
    st.header("📊 Ingested Ads Browser")
    st.markdown("View all ads that have been processed and indexed in the database.")
    
    @st.cache_data(ttl=300)  # Cache full ad data for 5 minutes
    def load_full_ad_analysis(ad_id):
        """Lazy-load full ad data with JSONB fields (analysis_json, etc.) when needed."""
        try:
            db_backend_mode = os.getenv("DB_BACKEND", "postgres")
            
            if db_backend_mode == "http":
                from tvads_rag.tvads_rag.supabase_db import _get_client
                client = _get_client()
                
                # Load ad with JSONB fields (including new analytics fields)
                ad_resp = client.table("ads").select(
                    "id, analysis_json, impact_scores, emotional_metrics, effectiveness, "
                    "cta_offer, brand_asset_timeline, audio_fingerprint, creative_dna, claims_compliance, "
                    "performance_metrics, visual_objects, physics_data, toxicity_report, "
                    "color_psychology, spatial_telemetry, visual_physics"
                ).eq("id", ad_id).execute()
                
                if not ad_resp.data:
                    return {}
                return ad_resp.data[0]
            else:
                # Postgres direct connection
                from tvads_rag.tvads_rag.db import get_connection
                
                with get_connection() as conn, conn.cursor() as cur:
                    cur.execute("""
                        SELECT 
                            id, analysis_json, impact_scores, emotional_metrics, effectiveness,
                            cta_offer, brand_asset_timeline, audio_fingerprint, creative_dna, claims_compliance,
                            performance_metrics, visual_objects, physics_data, toxicity_report,
                            color_psychology, spatial_telemetry, visual_physics
                        FROM ads 
                        WHERE id = %s
                    """, (ad_id,))
                    row = cur.fetchone()
                    if not row:
                        return {}
                    return dict(row)
        except Exception as e:
            st.error(f"Failed to load ad analysis: {e}")
            return {}
    
    def load_complete_ad_data(ad_id):
        """Load complete ad data including all related records."""
        try:
            db_backend_mode = os.getenv("DB_BACKEND", "postgres")
            
            if db_backend_mode == "http":
                from tvads_rag.tvads_rag.supabase_db import _get_client
                client = _get_client()
                
                # Load main ad record
                ad_resp = client.table("ads").select("*").eq("id", ad_id).execute()
                if not ad_resp.data:
                    return None
                ad_data = ad_resp.data[0]
                
                # Load related data
                chunks_resp = client.table("ad_chunks").select("*").eq("ad_id", ad_id).order("chunk_index").execute()
                ad_data["chunks"] = chunks_resp.data or []
                
                segments_resp = client.table("ad_segments").select("*").eq("ad_id", ad_id).order("start_time").execute()
                ad_data["segments"] = segments_resp.data or []
                
                storyboards_resp = client.table("ad_storyboards").select("*").eq("ad_id", ad_id).order("shot_index").execute()
                ad_data["storyboards"] = storyboards_resp.data or []
                
                claims_resp = client.table("ad_claims").select("*").eq("ad_id", ad_id).execute()
                ad_data["claims"] = claims_resp.data or []
                
                supers_resp = client.table("ad_supers").select("*").eq("ad_id", ad_id).order("start_time").execute()
                ad_data["supers"] = supers_resp.data or []
                
                embeddings_resp = client.table("embedding_items").select("id, item_type, text, meta").eq("ad_id", ad_id).execute()
                ad_data["embeddings_summary"] = embeddings_resp.data or []
                
                return ad_data
            else:
                # Postgres direct connection
                from tvads_rag.tvads_rag.db import get_connection
                
                with get_connection() as conn, conn.cursor() as cur:
                    # Load main ad record
                    cur.execute("SELECT * FROM ads WHERE id = %s", (ad_id,))
                    ad_row = cur.fetchone()
                    if not ad_row:
                        return None
                    ad_data = dict(ad_row)
                    
                    # Load chunks
                    cur.execute("SELECT * FROM ad_chunks WHERE ad_id = %s ORDER BY chunk_index", (ad_id,))
                    ad_data["chunks"] = [dict(row) for row in cur.fetchall()]
                    
                    # Load segments
                    cur.execute("SELECT * FROM ad_segments WHERE ad_id = %s ORDER BY start_time", (ad_id,))
                    ad_data["segments"] = [dict(row) for row in cur.fetchall()]
                    
                    # Load storyboards
                    cur.execute("SELECT * FROM ad_storyboards WHERE ad_id = %s ORDER BY shot_index", (ad_id,))
                    ad_data["storyboards"] = [dict(row) for row in cur.fetchall()]
                    
                    # Load claims
                    cur.execute("SELECT * FROM ad_claims WHERE ad_id = %s", (ad_id,))
                    ad_data["claims"] = [dict(row) for row in cur.fetchall()]
                    
                    # Load supers
                    cur.execute("SELECT * FROM ad_supers WHERE ad_id = %s ORDER BY start_time", (ad_id,))
                    ad_data["supers"] = [dict(row) for row in cur.fetchall()]
                    
                    # Load embeddings summary (without the actual vector)
                    cur.execute("""
                        SELECT id, item_type, text, meta 
                        FROM embedding_items 
                        WHERE ad_id = %s
                    """, (ad_id,))
                    ad_data["embeddings_summary"] = [dict(row) for row in cur.fetchall()]
                    
                    return ad_data
        except Exception as e:
            st.error(f"Failed to load complete ad data: {e}")
            return None
    
    @st.cache_data(ttl=300)  # Cache for 5 minutes (ads don't change frequently)
    def load_all_ads():
        """Load all ads from the database with optimized queries."""
        try:
            from tvads_rag.tvads_rag import db_backend
            
            # Get the Supabase client if using HTTP backend
            db_backend_mode = os.getenv("DB_BACKEND", "postgres")
            
            if db_backend_mode == "http":
                from tvads_rag.tvads_rag.supabase_db import _get_client
                client = _get_client()
                
                # Fetch ads WITHOUT large JSONB fields (load on demand)
                # Only load essential fields for the list view
                response = client.table("ads").select(
                    "id, external_id, brand_name, product_name, one_line_summary, "
                    "duration_seconds, format_type, created_at, "
                    "hero_analysis"  # Keep hero_analysis for hero badge
                ).order("created_at", desc=True).execute()
                
                ads = response.data if response.data else []
                
                if not ads:
                    return []
                
                # Use RPC function for efficient count aggregation (single query instead of 4)
                try:
                    counts_resp = client.rpc("get_ad_counts").execute()
                    counts_data = counts_resp.data or []
                    
                    # Build lookup dict by ad_id
                    counts_by_ad = {row["ad_id"]: row for row in counts_data}
                    
                    # Assign counts to ads
                    for ad in ads:
                        ad_id = ad["id"]
                        counts = counts_by_ad.get(ad_id, {})
                        ad["chunk_count"] = counts.get("chunk_count", 0)
                        ad["segment_count"] = counts.get("segment_count", 0)
                        ad["storyboard_count"] = counts.get("storyboard_count", 0)
                        ad["embedding_count"] = counts.get("embedding_count", 0)
                        
                except Exception as count_error:
                    # Fallback: if RPC fails, set counts to 0
                    st.warning(f"Could not load counts via RPC: {count_error}. Counts set to 0.")
                    for ad in ads:
                        ad["chunk_count"] = 0
                        ad["segment_count"] = 0
                        ad["storyboard_count"] = 0
                        ad["embedding_count"] = 0
                
                return ads
            else:
                # Postgres direct connection - optimized with JOINs instead of subqueries
                from tvads_rag.tvads_rag.db import get_connection
                
                with get_connection() as conn, conn.cursor() as cur:
                    # Use LEFT JOINs with GROUP BY for better performance than correlated subqueries
                    cur.execute("""
                        SELECT 
                            a.id, a.external_id, a.brand_name, a.product_name, 
                            a.one_line_summary, a.duration_seconds, a.format_type,
                            a.created_at, a.hero_analysis,
                            COALESCE(chunk_counts.cnt, 0) as chunk_count,
                            COALESCE(segment_counts.cnt, 0) as segment_count,
                            COALESCE(storyboard_counts.cnt, 0) as storyboard_count,
                            COALESCE(embedding_counts.cnt, 0) as embedding_count
                        FROM ads a
                        LEFT JOIN (
                            SELECT ad_id, COUNT(*) as cnt 
                            FROM ad_chunks 
                            GROUP BY ad_id
                        ) chunk_counts ON chunk_counts.ad_id = a.id
                        LEFT JOIN (
                            SELECT ad_id, COUNT(*) as cnt 
                            FROM ad_segments 
                            GROUP BY ad_id
                        ) segment_counts ON segment_counts.ad_id = a.id
                        LEFT JOIN (
                            SELECT ad_id, COUNT(*) as cnt 
                            FROM ad_storyboards 
                            GROUP BY ad_id
                        ) storyboard_counts ON storyboard_counts.ad_id = a.id
                        LEFT JOIN (
                            SELECT ad_id, COUNT(*) as cnt 
                            FROM embedding_items 
                            GROUP BY ad_id
                        ) embedding_counts ON embedding_counts.ad_id = a.id
                        ORDER BY a.created_at DESC
                    """)
                    rows = cur.fetchall()
                    return [dict(row) for row in rows]
                    
        except Exception as e:
            st.error(f"Failed to load ads: {e}")
            return []
    
    # Refresh button
    col_refresh, col_count = st.columns([1, 3])
    with col_refresh:
        if st.button("🔄 Refresh"):
            load_all_ads.clear()
            st.rerun()
    
    ads = load_all_ads()
    
    with col_count:
        st.metric("Total Ads Indexed", len(ads))
    
    if not ads:
        st.info("No ads have been ingested yet. Go to the Ingestion tab to process some ads.")
    else:
        # Summary stats
        st.subheader("Summary Statistics")
        stat_cols = st.columns(5)
        
        total_chunks = sum(ad.get("chunk_count", 0) for ad in ads)
        total_segments = sum(ad.get("segment_count", 0) for ad in ads)
        total_storyboards = sum(ad.get("storyboard_count", 0) for ad in ads)
        total_embeddings = sum(ad.get("embedding_count", 0) for ad in ads)
        hero_count = sum(1 for ad in ads if ad.get("hero_analysis"))
        
        stat_cols[0].metric("Total Chunks", total_chunks)
        stat_cols[1].metric("Total Segments", total_segments)
        stat_cols[2].metric("Total Storyboards", total_storyboards)
        stat_cols[3].metric("Total Embeddings", total_embeddings)
        stat_cols[4].metric("Hero Ads", hero_count)
        
        st.divider()
        
        # Filter options
        st.subheader("Browse Ads")
        
        filter_col1, filter_col2 = st.columns(2)
        with filter_col1:
            brand_filter = st.text_input("Filter by brand", placeholder="e.g. Nike")
        with filter_col2:
            hero_only = st.checkbox("Show only Hero ads")
        
        # Apply filters
        filtered_ads = ads
        if brand_filter:
            filtered_ads = [a for a in filtered_ads if brand_filter.lower() in (a.get("brand_name") or "").lower()]
        if hero_only:
            filtered_ads = [a for a in filtered_ads if a.get("hero_analysis")]
        
        # Pagination settings
        ITEMS_PER_PAGE = 10
        total_items = len(filtered_ads)
        total_pages = max(1, (total_items + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE)
        
        # Initialize or get current page from session state
        if "ad_browser_page" not in st.session_state:
            st.session_state.ad_browser_page = 1
        
        # Reset to page 1 if filters changed and current page is invalid
        if st.session_state.ad_browser_page > total_pages:
            st.session_state.ad_browser_page = 1
        
        current_page = st.session_state.ad_browser_page
        
        # Calculate slice indices
        start_idx = (current_page - 1) * ITEMS_PER_PAGE
        end_idx = min(start_idx + ITEMS_PER_PAGE, total_items)
        
        # Pagination controls
        pag_col1, pag_col2, pag_col3, pag_col4, pag_col5 = st.columns([1, 1, 2, 1, 1])
        
        with pag_col1:
            if st.button("⏮️ First", disabled=current_page == 1, key="pag_first"):
                st.session_state.ad_browser_page = 1
                st.rerun()
        
        with pag_col2:
            if st.button("◀️ Prev", disabled=current_page == 1, key="pag_prev"):
                st.session_state.ad_browser_page = max(1, current_page - 1)
                st.rerun()
        
        with pag_col3:
            st.markdown(f"<div style='text-align: center; padding-top: 8px;'>Page {current_page} of {total_pages} ({start_idx + 1}-{end_idx} of {total_items} ads)</div>", unsafe_allow_html=True)
        
        with pag_col4:
            if st.button("Next ▶️", disabled=current_page >= total_pages, key="pag_next"):
                st.session_state.ad_browser_page = min(total_pages, current_page + 1)
                st.rerun()
        
        with pag_col5:
            if st.button("Last ⏭️", disabled=current_page >= total_pages, key="pag_last"):
                st.session_state.ad_browser_page = total_pages
                st.rerun()
        
        st.divider()
        
        # Display paginated ads
        paginated_ads = filtered_ads[start_idx:end_idx]
        
        for ad in paginated_ads:
            external_id = ad.get("external_id", "Unknown")
            brand = ad.get("brand_name", "Unknown Brand")
            product = ad.get("product_name", "")
            summary = ad.get("one_line_summary", "No summary available")
            is_hero = bool(ad.get("hero_analysis"))
            
            # Card title
            title = f"{'⭐ ' if is_hero else ''}{external_id} | {brand}"
            if product:
                title += f" - {product}"
            
            with st.expander(title, expanded=False):
                # Basic info row
                info_cols = st.columns(4)
                info_cols[0].metric("Duration", f"{ad.get('duration_seconds', 0):.1f}s" if ad.get('duration_seconds') else "N/A")
                info_cols[1].metric("Format", ad.get("format_type", "N/A"))
                info_cols[2].metric("Chunks", ad.get("chunk_count", 0))
                info_cols[3].metric("Embeddings", ad.get("embedding_count", 0))
                
                # Summary
                st.markdown(f"**Summary:** {summary}")
                
                # Created date
                created = ad.get("created_at")
                if created:
                    st.caption(f"Indexed: {created}")
                
                # Download button - load complete ad data
                download_key = f"download_data_{ad['id']}"
                
                # Check if we need to load data
                if download_key not in st.session_state or st.session_state[download_key] is None:
                    if st.button("📥 Prepare Download", key=f"prepare_{ad['id']}"):
                        with st.spinner("Loading complete ad data..."):
                            st.session_state[download_key] = load_complete_ad_data(ad["id"])
                            st.rerun()
                else:
                    # Data is loaded, show download button
                    complete_data = st.session_state[download_key]
                    if complete_data:
                        json_str = json.dumps(complete_data, indent=2, default=str)
                        filename = f"{external_id}_{brand.replace(' ', '_')}_complete.json"
                        
                        col_dl1, col_dl2 = st.columns([2, 1])
                        with col_dl1:
                            st.download_button(
                                label="💾 Download Complete JSON",
                                data=json_str,
                                file_name=filename,
                                mime="application/json",
                                key=f"dl_{ad['id']}"
                            )
                        with col_dl2:
                            if st.button("🔄 Reset", key=f"reset_{ad['id']}"):
                                st.session_state[download_key] = None
                                st.rerun()
                    else:
                        st.error("Failed to load ad data")
                        if st.button("🔄 Retry", key=f"retry_{ad['id']}"):
                            st.session_state[download_key] = None
                            st.rerun()
                
                st.divider()
                
                # Lazy-load full analysis data ONLY when user clicks "Load Details"
                details_key = f"details_loaded_{ad['id']}"
                
                # Check if details have been loaded into session state
                if details_key not in st.session_state:
                    st.session_state[details_key] = None
                
                # Use empty dict if not loaded - tabs will show "No data" messages
                full_ad_data = st.session_state[details_key] or {}
                details_loaded = bool(st.session_state[details_key])
                
                # Show load button if not loaded
                if not details_loaded:
                    if st.button("📋 Load Detailed Analysis", key=f"load_details_{ad['id']}", type="primary"):
                        with st.spinner("Loading analysis data..."):
                            st.session_state[details_key] = load_full_ad_analysis(ad["id"])
                            st.rerun()
                    st.info("Click 'Load Detailed Analysis' to view extraction details, impact scores, and more.")
                
                # Extraction v2.0 grouped tabs
                detail_tabs = st.tabs([
                    "📊 Overview", "⚡ Impact Scores", "💓 Emotional", "🎨 Creative DNA",
                    "🏷️ Brand & Characters", "🎬 Audio & Visual", "🔬 Physics & Analytics",
                    "⚠️ Compliance & Effectiveness"
                ])
                
                with detail_tabs[0]:  # Overview - core_metadata, campaign_strategy, creative_attributes
                    analysis = full_ad_data.get("analysis_json") or ad.get("analysis_json")
                    if analysis:
                        if isinstance(analysis, str):
                            try:
                                analysis = json.loads(analysis)
                            except:
                                pass
                        
                        if isinstance(analysis, dict):
                            # Extraction version badge
                            version = analysis.get("extraction_version", "1.0")
                            st.caption(f"Extraction v{version}")
                            
                            # Core Metadata Section
                            st.markdown("### Core Metadata")
                            core = analysis.get("core_metadata", {})
                            meta_cols = st.columns(4)
                            meta_cols[0].metric("Brand", core.get("brand_name") or ad.get("brand_name") or "Unknown")
                            meta_cols[1].metric("Category", core.get("product_category") or ad.get("product_category") or "N/A")
                            meta_cols[2].metric("Country", core.get("country") or ad.get("country") or "N/A")
                            meta_cols[3].metric("Duration", f"{core.get('duration_seconds') or ad.get('duration_seconds') or 0:.1f}s")
                            
                            if core.get("product_subcategory"):
                                st.caption(f"Subcategory: {core.get('product_subcategory')}")
                            
                            # Campaign Strategy Section
                            st.markdown("### Campaign Strategy")
                            strategy = analysis.get("campaign_strategy", {})
                            strat_cols = st.columns(4)
                            strat_cols[0].metric("Objective", (strategy.get("objective") or "N/A").replace("_", " ").title())
                            strat_cols[1].metric("Funnel Stage", (strategy.get("funnel_stage") or "N/A").replace("_", " ").title())
                            strat_cols[2].metric("Primary KPI", (strategy.get("primary_kpi") or "N/A").replace("_", " ").title())
                            strat_cols[3].metric("Format", (strategy.get("format_type") or ad.get("format_type") or "N/A").replace("_", " ").title())
                            
                            # Creative Attributes Section
                            st.markdown("### Creative Attributes")
                            attrs = analysis.get("creative_attributes", {})
                            
                            if attrs.get("one_line_summary") or ad.get("one_line_summary"):
                                st.info(f"📝 {attrs.get('one_line_summary') or ad.get('one_line_summary')}")
                            
                            if attrs.get("story_summary") or ad.get("story_summary"):
                                st.markdown(f"**Story:** {attrs.get('story_summary') or ad.get('story_summary')}")
                            
                            attr_cols = st.columns(4)
                            attr_cols[0].markdown(f"**Tone:** {(attrs.get('tone') or 'N/A').replace('_', ' ').title()}")
                            attr_cols[1].markdown(f"**Visual Style:** {(attrs.get('visual_style') or 'N/A').replace('_', ' ').title()}")
                            attr_cols[2].markdown(f"**Editing Pace:** {(attrs.get('editing_pace') or ad.get('editing_pace') or 'N/A').replace('_', ' ').title()}")
                            attr_cols[3].markdown(f"**Colour Mood:** {(attrs.get('colour_mood') or ad.get('colour_mood') or 'N/A').replace('_', ' ').title()}")
                            
                            # Creative Flags Section
                            st.markdown("### Creative Flags")
                            flags = analysis.get("creative_flags", {})
                            flag_items = []
                            flag_map = {
                                "has_voiceover": "🎙️ Voiceover",
                                "has_dialogue": "💬 Dialogue", 
                                "has_on_screen_text": "📝 On-screen Text",
                                "has_celebrity": "⭐ Celebrity",
                                "has_humor": "😄 Humor",
                                "has_story_arc": "📖 Story Arc",
                                "has_music_with_lyrics": "🎵 Music w/ Lyrics",
                                "uses_nostalgia": "📺 Nostalgia",
                                "regulator_sensitive": "⚠️ Regulator Sensitive",
                            }
                            for flag_key, flag_label in flag_map.items():
                                if flags.get(flag_key) or ad.get(flag_key):
                                    flag_items.append(flag_label)
                            
                            if flag_items:
                                st.write(" | ".join(flag_items))
                            else:
                                st.caption("No special flags detected")
                            
                            with st.expander("Full Analysis JSON"):
                                st.json(analysis)
                        else:
                            st.json(analysis)
                    else:
                        st.info("No analysis data available - click 'Load Detailed Analysis' above")
                
                with detail_tabs[1]:  # Impact Scores - all 8 metrics with visualizations
                    # Use lazy-loaded data
                    analysis = full_ad_data.get("analysis_json") or {}
                    if isinstance(analysis, str):
                        try:
                            analysis = json.loads(analysis)
                        except:
                            analysis = {}
                    impact = full_ad_data.get("impact_scores") or ad.get("impact_scores") or (analysis.get("impact_scores") if analysis else None)
                    if impact:
                        if isinstance(impact, str):
                            try:
                                impact = json.loads(impact)
                            except:
                                pass
                        
                        if isinstance(impact, dict):
                            st.markdown("### Impact Scores (0-10 Scale)")
                            
                            # Overall Impact prominently displayed
                            overall = impact.get("overall_impact", {})
                            if isinstance(overall, dict) and overall.get("score") is not None:
                                score = float(overall.get("score", 5))
                                confidence = float(overall.get("confidence", 0.5))
                                st.metric(
                                    "Overall Impact",
                                    f"{score:.1f}/10",
                                    delta=f"Confidence: {confidence:.0%}"
                                )
                                if overall.get("rationale"):
                                    st.info(f"📋 {overall.get('rationale')}")
                            
                            st.divider()
                            
                            # Score grid - 4 columns x 2 rows
                            score_names = [
                                ("pulse_score", "⚡ Pulse (Short-term)", "evidence"),
                                ("echo_score", "📢 Echo (Long-term)", "evidence"),
                                ("hook_power", "🎣 Hook Power", "hook_technique"),
                                ("brand_integration", "🏷️ Brand Integration", "integration_style"),
                                ("emotional_resonance", "💓 Emotional Resonance", "primary_emotion"),
                                ("clarity_score", "🎯 Clarity", "main_message"),
                                ("distinctiveness", "✨ Distinctiveness", "distinctive_elements"),
                            ]
                            
                            # Create 4 columns for the scores
                            row1_cols = st.columns(4)
                            row2_cols = st.columns(4)
                            all_cols = row1_cols + row2_cols
                            
                            for i, (score_key, label, detail_key) in enumerate(score_names):
                                score_data = impact.get(score_key, {})
                                if isinstance(score_data, dict):
                                    score_val = float(score_data.get("score", 5))
                                    conf = float(score_data.get("confidence", 0.5))
                                    
                                    # Color coding based on score
                                    if score_val >= 7:
                                        color = "🟢"
                                    elif score_val >= 5:
                                        color = "🟡"
                                    else:
                                        color = "🔴"
                                    
                                    with all_cols[i]:
                                        st.markdown(f"**{label}**")
                                        st.markdown(f"{color} **{score_val:.1f}**/10")
                                        st.caption(f"Conf: {conf:.0%}")
                                        
                                        # Show detail if available
                                        detail = score_data.get(detail_key)
                                        if detail:
                                            if isinstance(detail, list):
                                                st.caption(", ".join(str(d) for d in detail[:3]))
                                            else:
                                                st.caption(str(detail)[:50])
                            
                            with st.expander("Full Impact Scores JSON"):
                                st.json(impact)
                        else:
                            st.json(impact)
                    else:
                        st.info("No impact scores available - may be using extraction v1.0")
                
                with detail_tabs[2]:  # Emotional - emotional_timeline, brain_balance, attention_dynamics
                    # Use lazy-loaded data
                    emotional_metrics = full_ad_data.get("emotional_metrics") or ad.get("emotional_metrics") or (analysis.get("emotional_timeline") if analysis else None)
                    
                    # Try to get from emotional_metrics container or directly from analysis
                    if isinstance(emotional_metrics, str):
                        try:
                            emotional_metrics = json.loads(emotional_metrics)
                        except:
                            pass
                    
                    timeline = None
                    brain = None
                    attention = None
                    
                    if isinstance(emotional_metrics, dict):
                        timeline = emotional_metrics.get("emotional_timeline") or emotional_metrics
                        brain = emotional_metrics.get("brain_balance")
                        attention = emotional_metrics.get("attention_dynamics")
                    
                    # Also check analysis_json directly for v2.0 format
                    if analysis and isinstance(analysis, dict):
                        if not timeline:
                            timeline = analysis.get("emotional_timeline")
                        if not brain:
                            brain = analysis.get("brain_balance")
                        if not attention:
                            attention = analysis.get("attention_dynamics")
                    
                    if timeline or brain or attention:
                        # Emotional Timeline Section
                        if timeline and isinstance(timeline, dict):
                            st.markdown("### 📈 Emotional Timeline")
                            
                            tl_cols = st.columns(4)
                            tl_cols[0].metric("Arc Shape", (timeline.get("arc_shape") or "unknown").replace("_", " ").title())
                            tl_cols[1].metric("Peak Emotion", (timeline.get("peak_emotion") or "neutral").title())
                            if timeline.get("peak_moment_s") is not None:
                                tl_cols[2].metric("Peak @ ", f"{timeline.get('peak_moment_s'):.1f}s")
                            tl_cols[3].metric("Positive Ratio", f"{(timeline.get('positive_ratio') or 0.5):.0%}")
                            
                            # Emotional readings chart (if available)
                            readings = timeline.get("readings") or []
                            if readings:
                                st.markdown("**Emotional Journey:**")
                                chart_data = []
                                for r in readings:
                                    if isinstance(r, dict):
                                        chart_data.append({
                                            "Time (s)": r.get("t_s", 0),
                                            "Intensity": r.get("intensity", 0.5),
                                            "Valence": r.get("valence", 0),
                                            "Emotion": r.get("dominant_emotion", "neutral")
                                        })
                                if chart_data:
                                    import pandas as pd
                                    df = pd.DataFrame(chart_data)
                                    st.line_chart(df.set_index("Time (s)")[["Intensity", "Valence"]])
                            
                            st.divider()
                        
                        # Brain Balance Section
                        if brain and isinstance(brain, dict):
                            st.markdown("### 🧠 Brain Balance")
                            
                            emotional_score = float(brain.get("emotional_appeal_score", 5))
                            rational_score = float(brain.get("rational_appeal_score", 5))
                            balance_type = brain.get("balance_type", "balanced")
                            
                            bb_cols = st.columns(3)
                            bb_cols[0].metric("💓 Emotional Appeal", f"{emotional_score:.1f}/10")
                            bb_cols[1].metric("🧮 Rational Appeal", f"{rational_score:.1f}/10")
                            bb_cols[2].metric("Balance", balance_type.replace("_", " ").title())
                            
                            # Emotional elements
                            emo_elements = brain.get("emotional_elements", {})
                            if emo_elements:
                                present = [k.replace("has_", "").replace("_", " ").title() 
                                          for k, v in emo_elements.items() if v]
                                if present:
                                    st.markdown(f"**Emotional Elements:** {', '.join(present)}")
                            
                            # Rational elements
                            rat_elements = brain.get("rational_elements", {})
                            if rat_elements:
                                present = [k.replace("has_", "").replace("_", " ").title() 
                                          for k, v in rat_elements.items() if v]
                                if present:
                                    st.markdown(f"**Rational Elements:** {', '.join(present)}")
                            
                            st.divider()
                        
                        # Attention Dynamics Section
                        if attention and isinstance(attention, dict):
                            st.markdown("### 👁️ Attention Dynamics")
                            
                            att_cols = st.columns(4)
                            att_cols[0].metric("Predicted Completion", f"{(attention.get('predicted_completion_rate') or 0.5):.0%}")
                            att_cols[1].metric("Cognitive Load", (attention.get("cognitive_load") or "moderate").title())
                            att_cols[2].metric("Pacing", (attention.get("pacing_assessment") or "just_right").replace("_", " ").title())
                            
                            # Skip risk zones
                            skip_zones = attention.get("skip_risk_zones") or []
                            if skip_zones:
                                st.markdown("**⚠️ Skip Risk Zones:**")
                                for zone in skip_zones:
                                    if isinstance(zone, dict):
                                        risk = zone.get("risk_level", "medium")
                                        risk_icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(risk, "⚪")
                                        st.markdown(f"- {risk_icon} {zone.get('t_start_s', 0):.1f}s - {zone.get('t_end_s', 0):.1f}s: {zone.get('reason', '')}")
                            
                            # Attention peaks
                            peaks = attention.get("attention_peaks") or []
                            if peaks:
                                st.markdown("**✨ Attention Peaks:**")
                                for peak in peaks:
                                    if isinstance(peak, dict):
                                        st.markdown(f"- {peak.get('t_s', 0):.1f}s: {peak.get('trigger', '')}")
                        
                        with st.expander("Full Emotional Metrics JSON"):
                            st.json({"emotional_timeline": timeline, "brain_balance": brain, "attention_dynamics": attention})
                    else:
                        st.info("No emotional metrics available - may be using extraction v1.0")
                
                with detail_tabs[3]:  # Creative DNA - creative_dna, distinctive_assets, memorability
                    # Use lazy-loaded data
                    dna = full_ad_data.get("creative_dna") or ad.get("creative_dna") or (analysis.get("creative_dna") if analysis else None)
                    if isinstance(dna, str):
                        try:
                            dna = json.loads(dna)
                        except:
                            pass
                    
                    distinctive = (analysis.get("distinctive_assets") if analysis else None) or []
                    memorability = (analysis.get("memorability") if analysis else None) or {}
                    
                    # Creative DNA Section
                    if dna and isinstance(dna, dict):
                        st.markdown("### 🧬 Creative DNA")
                        
                        dna_cols = st.columns(3)
                        dna_cols[0].metric("Archetype", (dna.get("archetype") or "everyman").replace("_", " ").title())
                        dna_cols[1].metric("Hook Type", (dna.get("hook_type") or "N/A").replace("_", " ").title())
                        dna_cols[2].metric("Structure", (dna.get("narrative_structure") or "linear").replace("_", " ").title())
                        
                        # Persuasion devices
                        devices = dna.get("persuasion_devices") or []
                        if devices:
                            st.markdown("**Persuasion Devices:**")
                            device_tags = [d.replace("_", " ").title() for d in devices]
                            st.write(" | ".join(device_tags))
                        
                        # Distinctive creative choices
                        choices = dna.get("distinctive_creative_choices") or []
                        if choices:
                            st.markdown("**Distinctive Choices:**")
                            for choice in choices:
                                st.markdown(f"- {choice}")
                        
                        if dna.get("pacing_notes"):
                            st.markdown(f"**Pacing:** {dna.get('pacing_notes')}")
                        
                        st.divider()
                    
                    # Distinctive Assets Section
                    if distinctive:
                        st.markdown("### ✨ Distinctive Assets (Fluent Devices)")
                        
                        for asset in distinctive:
                            if isinstance(asset, dict):
                                asset_type = (asset.get("asset_type") or "unknown").replace("_", " ").title()
                                desc = asset.get("description", "")
                                linkage = float(asset.get("brand_linkage", 0))
                                ownable = "✅ Ownable" if asset.get("is_ownable") else "❌ Not Ownable"
                                
                                st.markdown(f"**{asset_type}:** {desc}")
                                st.caption(f"Brand Linkage: {linkage:.0%} | {ownable}")
                        
                        st.divider()
                    
                    # Memorability Section
                    if memorability and isinstance(memorability, dict):
                        st.markdown("### 🧠 Memorability")
                        
                        mem_cols = st.columns(4)
                        mem_cols[0].metric("Overall Memorability", f"{memorability.get('overall_memorability_score', 5):.1f}/10")
                        mem_cols[1].metric("Predicted Recall (24h)", f"{(memorability.get('predicted_recall_24h') or 0.5):.0%}")
                        mem_cols[2].metric("Predicted Recall (7d)", f"{(memorability.get('predicted_recall_7d') or 0.3):.0%}")
                        mem_cols[3].metric("Cultural Impact", (memorability.get("potential_for_cultural_impact") or "low").title())
                        
                        # Memorable elements
                        mem_elements = memorability.get("memorable_elements") or []
                        if mem_elements:
                            st.markdown("**🌟 What People Will Remember:**")
                            for elem in mem_elements:
                                if isinstance(elem, dict):
                                    brand_linked = "🔗 Brand-linked" if elem.get("brand_linked") else "⚠️ Not brand-linked"
                                    score = elem.get("memorability_score", 5)
                                    st.markdown(f"- **{elem.get('element', '')}** ({score:.0f}/10, {brand_linked})")
                        
                        # Forgettable elements
                        forget = memorability.get("forgettable_elements") or []
                        if forget:
                            st.markdown("**❌ What People Will Forget:**")
                            for f in forget:
                                if isinstance(f, dict):
                                    st.markdown(f"- {f.get('element', '')} — _{f.get('reason', '')}_")
                    
                    if not dna and not distinctive and not memorability:
                        st.info("No creative DNA data available")
                    else:
                        with st.expander("Full Creative DNA JSON"):
                            st.json({"creative_dna": dna, "distinctive_assets": distinctive, "memorability": memorability})
                
                with detail_tabs[4]:  # Brand & Characters - brand_presence, characters, cta_offer
                    # Use lazy-loaded data
                    brand = full_ad_data.get("brand_asset_timeline") or ad.get("brand_asset_timeline") or (analysis.get("brand_presence") if analysis else None)
                    if isinstance(brand, str):
                        try:
                            brand = json.loads(brand)
                        except:
                            pass
                    
                    characters = (analysis.get("characters") if analysis else None) or []
                    cta = full_ad_data.get("cta_offer") or ad.get("cta_offer") or (analysis.get("cta_offer") if analysis else None)
                    if isinstance(cta, str):
                        try:
                            cta = json.loads(cta)
                        except:
                            pass
                    
                    # Brand Presence Section
                    if brand and isinstance(brand, dict):
                        st.markdown("### 🏷️ Brand Presence")
                        
                        br_cols = st.columns(4)
                        if brand.get("first_appearance_s") is not None:
                            br_cols[0].metric("First Appearance", f"{brand.get('first_appearance_s'):.1f}s")
                        br_cols[1].metric("First Type", (brand.get("first_appearance_type") or "none").replace("_", " ").title())
                        br_cols[2].metric("Screen Time", f"{(brand.get('total_screen_time_pct') or 0):.0%}")
                        br_cols[3].metric("Late Reveal", "Yes" if brand.get("late_reveal") else "No")
                        
                        br_cols2 = st.columns(3)
                        br_cols2[0].metric("Frequency Score", f"{brand.get('brand_frequency_score', 0):.1f}/10")
                        br_cols2[1].metric("Integration Naturalness", f"{brand.get('brand_integration_naturalness', 5):.1f}/10")
                        br_cols2[2].metric("Sonic Branding", "✅" if brand.get("sonic_branding_present") else "❌")
                        
                        if brand.get("tagline_used"):
                            st.info(f"📢 Tagline: \"{brand.get('tagline_used')}\" @ {brand.get('tagline_timestamp_s', 0):.1f}s")
                        
                        # Brand mentions
                        mentions = brand.get("mentions") or brand.get("brand_mentions") or []
                        if mentions:
                            st.markdown("**Brand Mentions:**")
                            for m in mentions[:8]:
                                if isinstance(m, dict):
                                    mode_icon = {"verbal": "🔊", "visual": "👁️", "both": "🔊👁️"}.get(m.get("type") or m.get("mode"), "📍")
                                    prominence = m.get("prominence", "")
                                    st.markdown(f"- {mode_icon} {m.get('t_s', 0):.1f}s: {m.get('context', m.get('text', ''))} ({prominence})")
                        
                        st.divider()
                    
                    # Characters Section
                    if characters:
                        st.markdown("### 👥 Characters & Casting")
                        
                        for i, char in enumerate(characters):
                            if isinstance(char, dict):
                                role = (char.get("role") or "unknown").replace("_", " ").title()
                                char_type = (char.get("character_type") or "unknown").replace("_", " ").title()
                                gender = char.get("gender", "unclear")
                                age = (char.get("age_bracket") or "unknown").replace("_", " ")
                                
                                celeb_badge = " ⭐ " + char.get("celebrity_name") if char.get("is_celebrity") and char.get("celebrity_name") else ""
                                
                                st.markdown(f"**{role}{celeb_badge}** - {char_type}")
                                char_cols = st.columns(4)
                                char_cols[0].caption(f"Gender: {gender}")
                                char_cols[1].caption(f"Age: {age}")
                                char_cols[2].caption(f"Screen: {(char.get('screen_time_pct') or 0):.0%}")
                                char_cols[3].caption(f"Likability: {char.get('likability_score', 5):.0f}/10")
                        
                        st.divider()
                    
                    # CTA/Offer Section
                    if cta and isinstance(cta, dict):
                        st.markdown("### 🎯 CTA & Offer")
                        
                        cta_cols = st.columns(4)
                        cta_cols[0].metric("Has CTA", "✅" if cta.get("has_cta") else "❌")
                        cta_cols[1].metric("CTA Type", (cta.get("cta_type") or "none").replace("_", " ").title())
                        cta_cols[2].metric("Has Offer", "✅" if cta.get("has_offer") else "❌")
                        cta_cols[3].metric("Urgency", "✅" if cta.get("urgency_present") else "❌")
                        
                        if cta.get("cta_text"):
                            st.info(f"📢 CTA: \"{cta.get('cta_text')}\"")
                        if cta.get("offer_summary"):
                            st.success(f"💰 Offer: {cta.get('offer_summary')}")
                        if cta.get("price_shown"):
                            st.markdown(f"**Price:** {cta.get('price_shown')}")
                        if cta.get("deadline_mentioned"):
                            st.warning(f"⏰ Deadline: {cta.get('deadline_mentioned')}")
                        
                        # Endcard info
                        if cta.get("endcard_present"):
                            st.markdown(f"**Endcard:** {cta.get('endcard_start_s', 0):.1f}s - {cta.get('endcard_duration_s', 0):.1f}s duration")
                            elements = cta.get("endcard_elements") or []
                            if elements:
                                st.caption(f"Elements: {', '.join(elements)}")
                    
                    if not brand and not characters and not cta:
                        st.info("No brand/character data available")
                    else:
                        with st.expander("Full Brand & Characters JSON"):
                            st.json({"brand_presence": brand, "characters": characters, "cta_offer": cta})
                
                with detail_tabs[5]:  # Audio & Visual - audio_fingerprint, storyboard, segments
                    # Use lazy-loaded data
                    audio = full_ad_data.get("audio_fingerprint") or ad.get("audio_fingerprint") or (analysis.get("audio_fingerprint") if analysis else None)
                    if isinstance(audio, str):
                        try:
                            audio = json.loads(audio)
                        except:
                            pass
                    
                    segments = (analysis.get("segments") if analysis else None) or []
                    storyboard_count = ad.get("storyboard_count", 0)
                    
                    # Audio Fingerprint Section
                    if audio and isinstance(audio, dict):
                        st.markdown("### 🔊 Audio Fingerprint")
                        
                        # Voiceover
                        vo = audio.get("voiceover") or audio
                        if isinstance(vo, dict):
                            vo_cols = st.columns(4)
                            vo_present = vo.get("present", audio.get("vo_present", False))
                            vo_cols[0].metric("Voiceover", "✅" if vo_present else "❌")
                            
                            if vo_present:
                                vo_cols[1].metric("Gender", (vo.get("gender") or "N/A").title())
                                vo_cols[2].metric("Tone", (vo.get("tone") or vo.get("energy") or "N/A").title())
                                vo_cols[3].metric("Pace", (vo.get("pace") or "N/A").title())
                                
                                if vo.get("accent"):
                                    st.caption(f"Accent: {vo.get('accent')}")
                        
                        # Dialogue
                        dialogue = audio.get("dialogue", {})
                        if isinstance(dialogue, dict) and dialogue.get("present"):
                            st.markdown("**💬 Dialogue:**")
                            key_lines = dialogue.get("key_lines") or []
                            for line in key_lines[:5]:
                                st.markdown(f'- _{line}_')
                        
                        # Music
                        music = audio.get("music") or audio.get("music_structure", {})
                        if isinstance(music, dict):
                            music_present = music.get("present", audio.get("music_present", False))
                            if music_present:
                                st.markdown("**🎵 Music:**")
                                music_info = []
                                if music.get("type"):
                                    music_info.append(f"Type: {music.get('type')}")
                                if music.get("genre") or music.get("genre_guess"):
                                    music_info.append(f"Genre: {music.get('genre') or music.get('genre_guess')}")
                                if music.get("energy_curve"):
                                    music_info.append(f"Energy: {music.get('energy_curve')}")
                                if music.get("bpm_estimate") or music.get("bpm_guess"):
                                    music_info.append(f"~{music.get('bpm_estimate') or music.get('bpm_guess')} BPM")
                                if music.get("has_lyrics"):
                                    music_info.append("Has Lyrics")
                                if music.get("emotional_fit"):
                                    music_info.append(f"Fit: {music.get('emotional_fit'):.0f}/10")
                                st.write(" | ".join(music_info))
                        
                        # SFX
                        sfx = audio.get("sfx", {})
                        if isinstance(sfx, dict) and sfx.get("present"):
                            sounds = sfx.get("notable_sounds") or []
                            if sounds:
                                st.markdown(f"**🔉 SFX:** {', '.join(sounds)}")
                        
                        if audio.get("audio_quality_score"):
                            st.caption(f"Audio Quality: {audio.get('audio_quality_score'):.0f}/10")
                        
                        st.divider()
                    
                    # Segments (AIDA) Section
                    if segments:
                        st.markdown("### 📊 Segments (AIDA)")
                        
                        for seg in segments:
                            if isinstance(seg, dict):
                                seg_type = (seg.get("segment_type") or "unknown").replace("_", " ").title()
                                aida = (seg.get("aida_stage") or "mixed").upper()
                                start = seg.get("start_s", seg.get("start_time", 0))
                                end = seg.get("end_s", seg.get("end_time", 0))
                                
                                aida_colors = {"ATTENTION": "🟢", "INTEREST": "🟡", "DESIRE": "🟠", "ACTION": "🔴", "MIXED": "⚪"}
                                
                                st.markdown(f"**{seg_type}** ({start:.1f}s - {end:.1f}s) {aida_colors.get(aida, '⚪')} {aida}")
                                if seg.get("transcript_excerpt") or seg.get("transcript_text"):
                                    st.caption(f"_{seg.get('transcript_excerpt') or seg.get('transcript_text')}_")
                                if seg.get("visual_summary"):
                                    st.caption(f"Visual: {seg.get('visual_summary')}")
                        
                        st.divider()
                    
                    # Storyboard Section
                    if storyboard_count > 0:
                        st.markdown("### 🎬 Storyboard")
                        st.success(f"✅ {storyboard_count} storyboard shots captured")
                        
                        if st.button(f"Load Storyboard Details", key=f"load_sb_{ad['id']}"):
                            try:
                                db_backend_mode = os.getenv("DB_BACKEND", "postgres")
                                if db_backend_mode == "http":
                                    from tvads_rag.tvads_rag.supabase_db import _get_client
                                    client = _get_client()
                                    sb_resp = client.table("ad_storyboards").select("*").eq("ad_id", ad["id"]).order("shot_index").execute()
                                    storyboards = sb_resp.data or []
                                else:
                                    from tvads_rag.tvads_rag.db import get_connection
                                    with get_connection() as conn, conn.cursor() as cur:
                                        cur.execute("""
                                            SELECT * FROM ad_storyboards 
                                            WHERE ad_id = %s 
                                            ORDER BY shot_index
                                        """, (ad["id"],))
                                        storyboards = [dict(row) for row in cur.fetchall()]
                                
                                for shot in storyboards:
                                    st.markdown(f"**Shot {shot.get('shot_index', '?')}** ({shot.get('start_time', 0):.1f}s - {shot.get('end_time', 0):.1f}s)")
                                    st.markdown(f"*{shot.get('shot_label', '')}* - {shot.get('description', '')}")
                                    if shot.get("mood"):
                                        st.caption(f"Mood: {shot.get('mood')} | Camera: {shot.get('camera_style', 'N/A')}")
                                    st.divider()
                            except Exception as e:
                                st.error(f"Failed to load storyboard: {e}")
                    else:
                        st.warning("No storyboard data - vision analysis may not have run")
                    
                    if not audio and not segments and storyboard_count == 0:
                        st.info("No audio/visual data available")
                    else:
                        with st.expander("Full Audio JSON"):
                            st.json(audio or {})
                
                with detail_tabs[6]:  # Physics & Analytics - physics_data, visual_objects, color_psychology, spatial_telemetry
                    # Load new analytics fields
                    physics_data = full_ad_data.get("physics_data") or ad.get("physics_data") or {}
                    visual_objects = full_ad_data.get("visual_objects") or ad.get("visual_objects") or {}
                    color_psychology = full_ad_data.get("color_psychology") or ad.get("color_psychology") or {}
                    spatial_telemetry = full_ad_data.get("spatial_telemetry") or ad.get("spatial_telemetry") or {}
                    visual_physics = full_ad_data.get("visual_physics") or ad.get("visual_physics") or {}
                    
                    # Parse JSON strings if needed
                    for field_name, field_data in [
                        ("physics_data", physics_data),
                        ("visual_objects", visual_objects),
                        ("color_psychology", color_psychology),
                        ("spatial_telemetry", spatial_telemetry),
                        ("visual_physics", visual_physics),
                    ]:
                        if isinstance(field_data, str):
                            try:
                                if field_name == "physics_data":
                                    physics_data = json.loads(field_data)
                                elif field_name == "visual_objects":
                                    visual_objects = json.loads(field_data)
                                elif field_name == "color_psychology":
                                    color_psychology = json.loads(field_data)
                                elif field_name == "spatial_telemetry":
                                    spatial_telemetry = json.loads(field_data)
                                elif field_name == "visual_physics":
                                    visual_physics = json.loads(field_data)
                            except:
                                pass
                    
                    # Visual Physics Section
                    if visual_physics and isinstance(visual_physics, dict):
                        st.markdown("### 🎬 Visual Physics")
                        vp_cols = st.columns(4)
                        vp_cols[0].metric("Cuts/Min", f"{visual_physics.get('cuts_per_minute', 0):.1f}")
                        vp_cols[1].metric("Avg Shot Duration", f"{visual_physics.get('average_shot_duration_s', 0):.2f}s")
                        vp_cols[2].metric("Motion Energy", f"{visual_physics.get('optical_flow_score', 0):.2f}")
                        vp_cols[3].metric("Brightness Variance", f"{visual_physics.get('brightness_variance', 0):.2f}")
                        
                        if visual_physics.get("motion_vector_direction"):
                            st.caption(f"Motion Direction: {visual_physics.get('motion_vector_direction', 'N/A')}")
                        
                        st.divider()
                    
                    # Physics Data (from Physics Engine)
                    if physics_data and isinstance(physics_data, dict):
                        st.markdown("### ⚙️ Physics Engine Data")
                        
                        physics_version = physics_data.get("physics_version", "N/A")
                        st.caption(f"Physics Engine v{physics_version}")
                        
                        # Visual Physics from engine
                        vp_engine = physics_data.get("visual_physics", {})
                        if vp_engine:
                            st.markdown("**Visual Metrics:**")
                            vp_eng_cols = st.columns(4)
                            vp_eng_cols[0].metric("Cuts/Min", f"{vp_engine.get('cuts_per_minute', 0):.1f}")
                            vp_eng_cols[1].metric("Motion Score", f"{vp_engine.get('optical_flow_score', 0):.2f}")
                            vp_eng_cols[2].metric("Brightness Var", f"{vp_engine.get('brightness_variance', 0):.2f}")
                            vp_eng_cols[3].metric("Scenes Detected", len(vp_engine.get("scenes", [])))
                        
                        # Audio Physics
                        audio_physics = physics_data.get("audio_physics", {})
                        if audio_physics:
                            st.markdown("**Audio Metrics:**")
                            ap_cols = st.columns(3)
                            if audio_physics.get("loudness_lu") is not None:
                                ap_cols[0].metric("Loudness (LUFS)", f"{audio_physics.get('loudness_lu', 0):.1f}")
                            if audio_physics.get("bpm") is not None:
                                ap_cols[1].metric("BPM", f"{audio_physics.get('bpm', 0):.0f}")
                            if audio_physics.get("tempo") is not None:
                                ap_cols[2].metric("Tempo", f"{audio_physics.get('tempo', 0):.0f}")
                        
                        # Objects Detected
                        objects = physics_data.get("objects_detected", [])
                        if objects:
                            st.markdown("**🔍 Objects Detected (YOLO):**")
                            obj_list = []
                            for obj in objects[:10]:  # Show top 10
                                if isinstance(obj, dict):
                                    obj_name = obj.get("class", obj.get("name", "Unknown"))
                                    conf = obj.get("confidence", 0)
                                    obj_list.append(f"{obj_name} ({conf:.0%})")
                            if obj_list:
                                st.write(" | ".join(obj_list))
                        
                        # Spatial Data
                        spatial = physics_data.get("spatial_data", {})
                        if spatial:
                            st.markdown("**📍 Spatial Data:**")
                            if spatial.get("largest_object_bbox"):
                                bbox = spatial.get("largest_object_bbox", {})
                                st.caption(f"Largest Object: x={bbox.get('x', 0):.2f}, y={bbox.get('y', 0):.2f}, w={bbox.get('w', 0):.2f}, h={bbox.get('h', 0):.2f}")
                        
                        # Keyframes
                        keyframes = physics_data.get("keyframes_saved", [])
                        if keyframes:
                            st.markdown(f"**🖼️ Keyframes:** {len(keyframes)} extracted")
                            if isinstance(keyframes, list) and len(keyframes) > 0:
                                if isinstance(keyframes[0], str) and keyframes[0].startswith("http"):
                                    st.caption("Keyframes uploaded to S3")
                                    for i, url in enumerate(keyframes[:5]):  # Show first 5 URLs
                                        st.markdown(f"- [Frame {i}]({url})")
                        
                        st.divider()
                    
                    # Visual Objects (from Gemini Vision)
                    if visual_objects and isinstance(visual_objects, dict):
                        st.markdown("### 👁️ Visual Objects Detection")
                        
                        agg = visual_objects.get("aggregate_summary", {})
                        if agg:
                            vo_cols = st.columns(4)
                            vo_cols[0].metric("Products", len(agg.get("unique_products", [])))
                            vo_cols[1].metric("Logos", len(agg.get("unique_logos", [])))
                            vo_cols[2].metric("Text Items", len(agg.get("all_text_ocr", [])))
                            vo_cols[3].metric("People", len(agg.get("people_detected", [])))
                            
                            if agg.get("unique_products"):
                                st.markdown("**Products:** " + ", ".join(agg.get("unique_products", [])[:10]))
                            if agg.get("unique_logos"):
                                st.markdown("**Logos:** " + ", ".join(agg.get("unique_logos", [])[:10]))
                        
                        st.divider()
                    
                    # Color Psychology
                    if color_psychology and isinstance(color_psychology, dict):
                        st.markdown("### 🎨 Color Psychology")
                        
                        dominant_hex = color_psychology.get("dominant_hex", [])
                        ratios = color_psychology.get("ratios", [])
                        contrast = color_psychology.get("contrast_ratio")
                        saturation = color_psychology.get("saturation_mean")
                        
                        dominant_colors = []
                        for i, hex_code in enumerate(dominant_hex[:3]):
                            ratio = ratios[i] if i < len(ratios) else 0
                            dominant_colors.append(f"{hex_code} ({ratio:.0%})")
                        
                        if dominant_colors:
                            st.markdown("**Dominant Colors:** " + " | ".join(dominant_colors))
                        
                        cp_cols = st.columns(2)
                        if contrast is not None:
                            cp_cols[0].metric("Contrast Ratio", f"{contrast:.1f}")
                        if saturation is not None:
                            cp_cols[1].metric("Saturation", f"{saturation:.2f}")
                        
                        st.divider()
                    
                    # Spatial Telemetry
                    if spatial_telemetry and isinstance(spatial_telemetry, dict):
                        st.markdown("### 📐 Spatial Telemetry")
                        
                        brand_prom = spatial_telemetry.get("brand_prominence", {})
                        if brand_prom:
                            st.markdown("**Brand Prominence:**")
                            sp_cols = st.columns(2)
                            sp_cols[0].metric("Screen Coverage", f"{(brand_prom.get('total_screen_coverage_pct', 0) * 100):.1f}%")
                            sp_cols[1].metric("Center Distance", f"{brand_prom.get('center_gravity_dist', 0):.2f}")
                        
                        face_prom = spatial_telemetry.get("face_prominence", {})
                        if face_prom:
                            st.markdown("**Face Prominence:**")
                            fp_cols = st.columns(2)
                            fp_cols[0].metric("Max Face Size", f"{(face_prom.get('max_face_size_pct', 0) * 100):.1f}%")
                            fp_cols[1].metric("Eye Contact", f"{face_prom.get('eye_contact_duration_s', 0):.1f}s")
                        
                        st.divider()
                    
                    # Summary
                    has_data = any([
                        visual_physics, physics_data, visual_objects,
                        color_psychology, spatial_telemetry
                    ])
                    
                    if not has_data:
                        st.info("No physics/analytics data available - physics extraction may not have run")
                    else:
                        with st.expander("Full Physics & Analytics JSON"):
                            st.json({
                                "visual_physics": visual_physics,
                                "physics_data": physics_data,
                                "visual_objects": visual_objects,
                                "color_psychology": color_psychology,
                                "spatial_telemetry": spatial_telemetry,
                            })
                
                with detail_tabs[7]:  # Compliance & Effectiveness - compliance_assessment, effectiveness_drivers, competitive_context, toxicity_report
                    # Use lazy-loaded data
                    compliance = full_ad_data.get("claims_compliance") or ad.get("claims_compliance") or (analysis.get("compliance_assessment") if analysis else None)
                    if isinstance(compliance, str):
                        try:
                            compliance = json.loads(compliance)
                        except:
                            pass
                    
                    effectiveness = full_ad_data.get("effectiveness") or ad.get("effectiveness") or {}
                    if isinstance(effectiveness, str):
                        try:
                            effectiveness = json.loads(effectiveness)
                        except:
                            pass
                    
                    # Try to get from effectiveness container or directly from analysis
                    eff_drivers = None
                    competitive = None
                    if isinstance(effectiveness, dict):
                        eff_drivers = effectiveness.get("effectiveness_drivers")
                        competitive = effectiveness.get("competitive_context")
                    
                    if analysis and isinstance(analysis, dict):
                        if not eff_drivers:
                            eff_drivers = analysis.get("effectiveness_drivers")
                        if not competitive:
                            competitive = analysis.get("competitive_context")
                    
                    # Claims section (from analysis)
                    claims = (analysis.get("claims") if analysis else None) or []
                    supers = (analysis.get("supers") if analysis else None) or []
                    
                    # Compliance Assessment Section
                    if compliance and isinstance(compliance, dict):
                        st.markdown("### ⚠️ Compliance Assessment")
                        
                        risk = compliance.get("overall_risk", "low")
                        risk_colors = {"low": "🟢", "medium": "🟡", "high": "🔴", "critical": "🚨"}
                        
                        comp_cols = st.columns(3)
                        comp_cols[0].metric("Overall Risk", f"{risk_colors.get(risk, '⚪')} {risk.upper()}")
                        comp_cols[1].metric("Clearcast Ready", f"{compliance.get('clearcast_readiness', 5):.0f}/10")
                        
                        flags = compliance.get("regulated_category_flags") or []
                        if flags and flags != ["none"]:
                            st.warning(f"**⚠️ Regulated Categories:** {', '.join(flags)}")
                        
                        # Potential issues
                        issues = compliance.get("potential_issues") or []
                        if issues:
                            st.markdown("**Potential Issues:**")
                            for issue in issues:
                                if isinstance(issue, dict):
                                    issue_type = (issue.get("issue_type") or "other").replace("_", " ").title()
                                    risk_lvl = issue.get("risk_level", "medium")
                                    risk_icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(risk_lvl, "⚪")
                                    st.markdown(f"- {risk_icon} **{issue_type}:** {issue.get('description', '')}")
                                    if issue.get("suggested_fix"):
                                        st.caption(f"  Fix: {issue.get('suggested_fix')}")
                        
                        if compliance.get("clearcast_notes"):
                            st.info(f"📋 Clearcast Notes: {compliance.get('clearcast_notes')}")
                        
                        st.divider()
                    
                    # Claims & Supers
                    if claims or supers:
                        st.markdown("### 📜 Claims & Supers")
                        
                        if claims:
                            st.markdown("**Claims:**")
                            for claim in claims:
                                if isinstance(claim, dict):
                                    claim_type = (claim.get("claim_type") or "general").title()
                                    risk = "⚠️" if claim.get("likely_needs_substantiation") else "✅"
                                    comparative = " (Comparative)" if claim.get("is_comparative") else ""
                                    st.markdown(f"- {risk} **{claim_type}{comparative}:** _{claim.get('text', '')}_")
                        
                        if supers:
                            st.markdown("**Supers (On-screen text):**")
                            for sup in supers:
                                if isinstance(sup, dict):
                                    sup_type = (sup.get("super_type") or "other").title()
                                    legible = "✅" if sup.get("reading_time_adequate", True) else "⚠️ Too fast"
                                    st.markdown(f"- {legible} **{sup_type}:** _{sup.get('text', '')}_ ({sup.get('duration_s', 0):.1f}s)")
                        
                        st.divider()
                    
                    # Effectiveness Drivers Section
                    if eff_drivers and isinstance(eff_drivers, dict):
                        st.markdown("### 💪 Effectiveness Drivers")
                        
                        # Strengths
                        strengths = eff_drivers.get("strengths") or []
                        if strengths:
                            st.markdown("**✅ Strengths:**")
                            for s in strengths:
                                if isinstance(s, dict):
                                    impact = s.get("impact", "medium")
                                    impact_icon = {"high": "🔥", "medium": "✨", "low": "💫"}.get(impact, "✨")
                                    st.markdown(f"- {impact_icon} **{s.get('driver', '')}** ({impact} impact)")
                                    if s.get("evidence"):
                                        st.caption(f"  Evidence: {s.get('evidence')}")
                                    if s.get("recommendation"):
                                        st.caption(f"  Amplify: {s.get('recommendation')}")
                        
                        # Weaknesses
                        weaknesses = eff_drivers.get("weaknesses") or []
                        if weaknesses:
                            st.markdown("**❌ Weaknesses:**")
                            for w in weaknesses:
                                if isinstance(w, dict):
                                    impact = w.get("impact", "medium")
                                    difficulty = (w.get("fix_difficulty") or "moderate").title()
                                    st.markdown(f"- **{w.get('driver', '')}** ({impact} impact, {difficulty} fix)")
                                    if w.get("fix_suggestion"):
                                        st.success(f"  💡 Fix: {w.get('fix_suggestion')}")
                        
                        # Optimization opportunities
                        opts = eff_drivers.get("optimization_opportunities") or []
                        if opts:
                            st.markdown("**🚀 Optimization Opportunities:**")
                            for o in opts:
                                if isinstance(o, dict):
                                    st.markdown(f"- **{o.get('opportunity', '')}** → {o.get('potential_impact', '')}")
                        
                        # A/B test suggestions
                        ab_tests = eff_drivers.get("ab_test_suggestions") or []
                        if ab_tests:
                            st.markdown("**🔬 A/B Test Suggestions:**")
                            for ab in ab_tests:
                                if isinstance(ab, dict):
                                    st.markdown(f"- Test: {ab.get('element_to_test', '')}")
                                    st.caption(f"  A: {ab.get('variant_a', '')} vs B: {ab.get('variant_b', '')}")
                                    if ab.get("hypothesis"):
                                        st.caption(f"  Hypothesis: {ab.get('hypothesis')}")
                        
                        st.divider()
                    
                    # Competitive Context Section
                    if competitive and isinstance(competitive, dict):
                        st.markdown("### 🏆 Competitive Context")
                        
                        st.metric("Share of Voice Potential", (competitive.get("share_of_voice_potential") or "medium").title())
                        
                        if competitive.get("differentiation_strategy"):
                            st.info(f"🎯 Differentiation: {competitive.get('differentiation_strategy')}")
                        if competitive.get("competitive_vulnerability"):
                            st.warning(f"⚠️ Vulnerability: {competitive.get('competitive_vulnerability')}")
                        
                        followed = competitive.get("category_conventions_followed") or []
                        if followed:
                            st.markdown(f"**Conventions Followed:** {', '.join(followed)}")
                        
                        broken = competitive.get("category_conventions_broken") or []
                        if broken:
                            st.markdown(f"**Conventions Broken:** {', '.join(broken)}")
                    
                    # Toxicity Report Section
                    toxicity_report = full_ad_data.get("toxicity_report") or ad.get("toxicity_report") or {}
                    if isinstance(toxicity_report, str):
                        try:
                            toxicity_report = json.loads(toxicity_report)
                        except:
                            pass
                    
                    if toxicity_report and isinstance(toxicity_report, dict) and toxicity_report.get("toxic_score") is not None:
                        st.divider()
                        st.markdown("### ⚠️ Toxicity Score")
                        
                        toxic_score = toxicity_report.get("toxic_score", 0)
                        risk_level = toxicity_report.get("risk_level", "UNKNOWN")
                        
                        # Color code by risk level
                        risk_colors = {
                            "LOW": "🟢",
                            "MEDIUM": "🟡",
                            "HIGH": "🔴",
                            "CRITICAL": "🚨"
                        }
                        risk_icon = risk_colors.get(risk_level.upper(), "⚪")
                        
                        tox_cols = st.columns(3)
                        tox_cols[0].metric("Toxicity Score", f"{risk_icon} {toxic_score}/100")
                        tox_cols[1].metric("Risk Level", risk_level.upper())
                        
                        # Breakdown by pillar
                        breakdown = toxicity_report.get("breakdown", {})
                        if breakdown:
                            phys_score = breakdown.get("physiological", {}).get("score", 0)
                            psych_score = breakdown.get("psychological", {}).get("score", 0)
                            reg_score = breakdown.get("regulatory", {}).get("score", 0)
                            
                            st.markdown("**Breakdown by Pillar:**")
                            br_cols = st.columns(3)
                            br_cols[0].metric("Physiological", f"{phys_score}/100", delta="40% weight")
                            br_cols[1].metric("Psychological", f"{psych_score}/100", delta="40% weight")
                            br_cols[2].metric("Regulatory", f"{reg_score}/100", delta="20% weight")
                            
                            # Flags
                            all_flags = []
                            for pillar_name, pillar_data in breakdown.items():
                                if isinstance(pillar_data, dict):
                                    flags = pillar_data.get("flags", [])
                                    if flags:
                                        all_flags.extend([f"{pillar_name.title()}: {f}" for f in flags])
                            
                            if all_flags:
                                st.markdown("**🚩 Flags:**")
                                for flag in all_flags[:10]:  # Show top 10
                                    st.caption(f"- {flag}")
                            
                            # Dark patterns
                            dark_patterns = toxicity_report.get("dark_patterns_detected", [])
                            if dark_patterns:
                                st.markdown("**🕳️ Dark Patterns Detected:**")
                                for pattern in dark_patterns[:5]:
                                    st.caption(f"- {pattern}")
                        
                        # Recommendation
                        recommendation = toxicity_report.get("recommendation", "")
                        if recommendation:
                            if risk_level.upper() in ["HIGH", "CRITICAL"]:
                                st.error(f"**Recommendation:** {recommendation}")
                            elif risk_level.upper() == "MEDIUM":
                                st.warning(f"**Recommendation:** {recommendation}")
                            else:
                                st.info(f"**Recommendation:** {recommendation}")
                        
                        with st.expander("Full Toxicity Report JSON"):
                            st.json(toxicity_report)
                    
                    # Hero Analysis (if present)
                    hero = full_ad_data.get("hero_analysis") or ad.get("hero_analysis")
                    if hero:
                        if isinstance(hero, str):
                            try:
                                hero = json.loads(hero)
                            except:
                                pass
                        
                        if isinstance(hero, dict):
                            st.divider()
                            st.markdown("### ⭐ Hero Ad Analysis")
                            st.success("This is a top-performing ad with deep analysis")
                            
                            if hero.get("overall_score") is not None:
                                st.metric("Overall Score", f"{hero.get('overall_score'):.1f}/100")
                            
                            if hero.get("creative_strategy"):
                                st.markdown(f"**Creative Strategy:** {hero.get('creative_strategy')}")
                            
                            with st.expander("Full Hero Analysis JSON"):
                                st.json(hero)
                    
                    if not compliance and not eff_drivers and not competitive:
                        st.info("No compliance/effectiveness data available")
                    else:
                        with st.expander("Full Compliance & Effectiveness JSON"):
                            st.json({
                                "compliance_assessment": compliance, 
                                "effectiveness_drivers": eff_drivers, 
                                "competitive_context": competitive
                            })


# --- Tab 5: Search & Eval ---
with tab_search:
    st.header("Search & Evaluation")
    
    search_col, eval_col = st.columns([2, 1])
    
    with search_col:
        st.subheader("Hybrid Search Demo")
        query_text = st.text_input("Query", placeholder="e.g. 'car ads with family roadtrip'")
        top_k = st.slider("Results (Top K)", 1, 20, 5)
        
        if st.button("🔎 Search"):
            if not query_text:
                st.warning("Please enter a query.")
            else:
                # We import here to ensure we pick up the latest env vars if changed
                # Backend selection is lazy and will fall back to postgres if http backend unavailable
                from tvads_rag.tvads_rag.retrieval import retrieve_with_rerank
                
                with st.spinner("Searching..."):
                    try:
                        results = retrieve_with_rerank(query_text, final_k=top_k)
                        if not results:
                            st.info("No results found.")
                        else:
                            for idx, row in enumerate(results):
                                title = f"{idx+1}. {row.get('brand_name')} - {row.get('product_name')}"
                                if row.get("hero_analysis"):
                                    title += " ⭐ Hero"
                                with st.expander(title, expanded=True):
                                    cols = st.columns(3)
                                    cols[0].metric("RRF Score", f"{row.get('rrf_score', 0):.4f}")
                                    cols[1].metric("Rerank Score", f"{row.get('rerank_score', 0):.4f}" if row.get('rerank_score') else "N/A")
                                    cols[2].caption(f"Type: {row.get('item_type')}")
                                    st.markdown(f"**Text:** {row.get('text')}")
                                    if row.get('meta'):
                                        st.json(row.get('meta'))
                                    if row.get("performance_metrics"):
                                        st.caption("Performance Metrics")
                                        st.json(row["performance_metrics"])
                                    if row.get("hero_analysis"):
                                        st.caption("Hero Analysis")
                                        st.json(row["hero_analysis"])
                    except Exception as e:
                        st.error(f"Search failed: {e}")

    with eval_col:
        st.subheader("Golden Set Evaluation")
        st.markdown("Run the full evaluation suite against `docs/golden_set.jsonl`.")
        
        if st.button("🏆 Run Evaluation"):
            with st.status("Running Evaluation...", expanded=True) as status:
                container = st.empty()
                output = ""
                # Use the nested package path to avoid import errors when launched
                # from the project root.
                cmd = [sys.executable, "-m", "tvads_rag.tvads_rag.evaluate_rag", "--golden-path", "docs/golden_set.jsonl"]
                
                for line in run_command(cmd):
                    output += line
                    container.code(output, language="text")
                status.update(label="Evaluation Complete", state="complete")


# --- Tab 5: AI Chat ---
with tab_chat:
    st.header("AI Chat - Ask Questions About Ads")
    st.markdown("""
    Ask questions about the TV ads in your database. The AI will search for relevant ads 
    and provide answers based on the data.
    
    **Example questions:**
    - "What car ads use family themes?"
    - "Show me ads with celebrity endorsements"
    - "Which brands use urgency in their messaging?"
    - "Find ads with price claims or discounts"
    - "What creative techniques do luxury brands use?"
    """)
    
    # Initialize chat history
    if "messages" not in st.session_state:
        st.session_state.messages = []
    
    # Display chat history
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if message.get("sources"):
                with st.expander("📚 Sources", expanded=False):
                    for src in message["sources"]:
                        st.markdown(f"**{src.get('brand_name', 'Unknown')}** - {src.get('item_type', '')}")
                        st.caption(src.get("text", "")[:300] + "..." if len(src.get("text", "")) > 300 else src.get("text", ""))
    
    # Chat input
    if prompt := st.chat_input("Ask about your ads..."):
        # Add user message to history
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        with st.chat_message("user"):
            st.markdown(prompt)
        
        with st.chat_message("assistant"):
            with st.spinner("Searching ads and generating response..."):
                try:
                    # Import RAG components
                    from tvads_rag.tvads_rag.retrieval import retrieve_with_rerank
                    from tvads_rag.tvads_rag.config import get_openai_config
                    import openai
                    
                    # Retrieve relevant context
                    results = retrieve_with_rerank(prompt, final_k=8)
                    
                    if not results:
                        response = "I couldn't find any relevant ads matching your query. Try rephrasing or asking about different topics."
                        sources = []
                    else:
                        # Build context from retrieved results
                        context_parts = []
                        for i, r in enumerate(results, 1):
                            brand = r.get("brand_name", "Unknown")
                            product = r.get("product_name", "")
                            item_type = r.get("item_type", "")
                            text = r.get("text", "")
                            summary = r.get("one_line_summary", "")
                            
                            context_parts.append(f"""
[Ad {i}] Brand: {brand} | Product: {product} | Type: {item_type}
{f'Summary: {summary}' if summary else ''}
Content: {text}
""")
                        
                        context = "\n".join(context_parts)
                        
                        # Generate response using OpenAI
                        openai_cfg = get_openai_config()
                        client = openai.OpenAI(
                            api_key=openai_cfg.api_key,
                            base_url=openai_cfg.api_base if openai_cfg.api_base else None,
                        )
                        
                        system_prompt = """You are an expert TV advertising analyst. You help users understand and analyze TV commercials based on a database of ad content.

When answering questions:
- Be specific and cite which ads/brands you're referring to
- Highlight creative techniques, messaging strategies, and audience targeting
- If asked about specific brands or products, focus on those
- Provide actionable insights when relevant
- Be concise but informative

Base your answers ONLY on the provided ad context. If the context doesn't contain relevant information, say so."""

                        user_prompt = f"""Based on the following ad data, answer this question: {prompt}

AD CONTEXT:
{context}

Provide a helpful, specific answer based on the ads above. Reference specific brands and content where relevant."""

                        # Build completion kwargs - newer models use max_completion_tokens
                        completion_kwargs = {
                            "model": openai_cfg.llm_model_name,
                            "messages": [
                                {"role": "system", "content": system_prompt},
                                {"role": "user", "content": user_prompt},
                            ],
                        }
                        
                        # o1/o3 models don't support temperature or max_tokens
                        model_name = openai_cfg.llm_model_name.lower()
                        if model_name.startswith(("o1", "o3")):
                            completion_kwargs["max_completion_tokens"] = 1000
                        else:
                            completion_kwargs["temperature"] = 0.7
                            completion_kwargs["max_completion_tokens"] = 1000
                        
                        completion = client.chat.completions.create(**completion_kwargs)
                        
                        response = completion.choices[0].message.content
                        sources = results[:5]  # Keep top 5 as sources
                    
                    st.markdown(response)
                    
                    if sources:
                        with st.expander("📚 Sources", expanded=False):
                            for src in sources:
                                st.markdown(f"**{src.get('brand_name', 'Unknown')}** - {src.get('item_type', '')}")
                                text = src.get("text", "")
                                st.caption(text[:300] + "..." if len(text) > 300 else text)
                    
                    # Add assistant message to history
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": response,
                        "sources": sources,
                    })
                    
                except Exception as e:
                    error_msg = f"Error generating response: {e}"
                    st.error(error_msg)
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": error_msg,
                    })
    
    # Clear chat button
    col1, col2, col3 = st.columns([1, 1, 2])
    with col1:
        if st.button("🗑️ Clear Chat"):
            st.session_state.messages = []
            st.rerun()
    with col2:
        st.caption(f"Using: {os.getenv('OPENAI_LLM_MODEL', 'gpt-4o-mini')}")

