"""
Pipeline stages for ad processing.

Each stage is responsible for a specific part of the processing pipeline.
Stages are executed in order, with each stage reading from and writing to
the shared ProcessingContext.
"""

from .video_load import VideoLoadStage
from .media_probe import MediaProbeStage
from .transcription import TranscriptionStage
from .llm_analysis import LLMAnalysisStage
from .hero_analysis import HeroAnalysisStage
from .db_insertion import DatabaseInsertionStage
from .editorial_enrichment import EditorialEnrichmentStage
from .vision import VisionStage
from .physics import PhysicsStage
from .toxicity import ToxicityStage
from .embeddings import EmbeddingsStage

__all__ = [
    "VideoLoadStage",
    "MediaProbeStage",
    "TranscriptionStage",
    "LLMAnalysisStage",
    "HeroAnalysisStage",
    "DatabaseInsertionStage",
    "EditorialEnrichmentStage",
    "VisionStage",
    "PhysicsStage",
    "ToxicityStage",
    "EmbeddingsStage",
]

# Default stage order for the pipeline
DEFAULT_STAGES = [
    VideoLoadStage(),
    MediaProbeStage(),
    TranscriptionStage(),
    LLMAnalysisStage(),
    HeroAnalysisStage(),
    DatabaseInsertionStage(),
    EditorialEnrichmentStage(),  # Match to Wix data and create ad_editorial
    VisionStage(),
    PhysicsStage(),
    ToxicityStage(),  # After physics so we have cuts/min, loudness data
    EmbeddingsStage(),
]

