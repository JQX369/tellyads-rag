"""
Processing context for pipeline stages.

The ProcessingContext is the shared state passed through all pipeline stages.
Each stage reads from and writes to this context, making data flow explicit.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ..metadata_ingest import AdMetadataEntry


@dataclass
class ProcessingContext:
    """
    Shared state passed through pipeline stages.
    
    Each stage reads its inputs from the context and writes its outputs back.
    This makes data flow explicit and testable.
    
    Attributes:
        external_id: Unique identifier for the ad (e.g., filename, ISCI code)
        source: Source type ("local" or "s3")
        s3_key: S3 object key (if source="s3")
        bucket: S3 bucket name (if source="s3")
        location: Original path or S3 key
        
        video_path: Local path to video file (set by VideoLoadStage)
        audio_path: Local path to extracted audio (set by MediaProbeStage)
        probe_result: FFprobe metadata (set by MediaProbeStage)
        transcript: ASR transcript (set by TranscriptionStage)
        analysis_result: LLM analysis output (set by LLMAnalysisStage)
        hero_analysis: Deep analysis for hero ads (set by HeroAnalysisStage)
        ad_id: Database UUID (set by DatabaseInsertionStage)
        
        storyboard_shots: Vision storyboard results (set by VisionStage)
        visual_objects: Object detection results (set by VisionStage)
        physics_result: Physics extraction results (set by PhysicsStage)
        frame_samples: Sampled frames for vision (set by VisionStage)
        
        segment_ids: Database segment IDs (set by DatabaseInsertionStage)
        chunk_ids: Database chunk IDs (set by DatabaseInsertionStage)
        claim_ids: Database claim IDs (set by DatabaseInsertionStage)
        super_ids: Database super IDs (set by DatabaseInsertionStage)
        
        metadata_entry: Optional CSV metadata (set externally)
        processing_notes: Notes about processing issues
        temp_dirs: Temp directories to clean up
        
        start_time: Pipeline start timestamp
        vision_tier: Vision model tier to use
        hero_required: Whether this ad requires hero analysis
    """
    
    # Required inputs
    external_id: str
    source: str
    location: str
    
    # Optional inputs
    s3_key: Optional[str] = None
    bucket: Optional[str] = None
    metadata_entry: Optional["AdMetadataEntry"] = None
    vision_tier: Optional[str] = None
    hero_required: bool = False
    
    # Stage 1: Video Load outputs
    video_path: Optional[Path] = None
    
    # Stage 2: Media Probe outputs
    audio_path: Optional[Path] = None
    probe_result: Optional[Dict[str, Any]] = None
    
    # Stage 3: Transcription outputs
    transcript: Optional[Dict[str, Any]] = None
    
    # Stage 4: LLM Analysis outputs
    analysis_result: Optional[Dict[str, Any]] = None
    
    # Stage 5: Hero Analysis outputs
    hero_analysis: Optional[Dict[str, Any]] = None
    
    # Stage 6: Database Insertion outputs
    ad_id: Optional[str] = None
    segment_ids: List[str] = field(default_factory=list)
    chunk_ids: List[str] = field(default_factory=list)
    claim_ids: List[str] = field(default_factory=list)
    super_ids: List[str] = field(default_factory=list)
    
    # Stage 7: Vision outputs
    storyboard_shots: List[Dict[str, Any]] = field(default_factory=list)
    storyboard_ids: List[str] = field(default_factory=list)
    visual_objects: Optional[Dict[str, Any]] = None
    frame_samples: List[Any] = field(default_factory=list)
    
    # Stage 7b: Physics outputs
    physics_result: Optional[Dict[str, Any]] = None
    
    # Stage 9: Toxicity outputs
    toxicity_report: Optional[Dict[str, Any]] = None
    
    # Stage 10: Embedding outputs
    embedding_count: int = 0
    
    # Processing metadata
    processing_notes: Dict[str, Any] = field(default_factory=dict)
    temp_dirs: List[Path] = field(default_factory=list)
    start_time: float = field(default_factory=time.time)
    
    # Stage tracking
    completed_stages: List[str] = field(default_factory=list)
    skipped_stages: List[str] = field(default_factory=list)
    failed_stages: List[str] = field(default_factory=list)
    
    def register_temp_dir(self, temp_dir: Path) -> None:
        """Register a temp directory for cleanup."""
        self.temp_dirs.append(temp_dir)
    
    def add_processing_note(self, key: str, note: Dict[str, Any]) -> None:
        """Add a processing note (e.g., error, warning)."""
        self.processing_notes[key] = note
    
    def mark_stage_complete(self, stage_name: str) -> None:
        """Mark a stage as completed."""
        if stage_name not in self.completed_stages:
            self.completed_stages.append(stage_name)
    
    def mark_stage_skipped(self, stage_name: str) -> None:
        """Mark a stage as skipped."""
        if stage_name not in self.skipped_stages:
            self.skipped_stages.append(stage_name)
    
    def mark_stage_failed(self, stage_name: str) -> None:
        """Mark a stage as failed."""
        if stage_name not in self.failed_stages:
            self.failed_stages.append(stage_name)
    
    def elapsed_time(self) -> float:
        """Get elapsed time since processing started."""
        return time.time() - self.start_time
    
    @property
    def brand_name(self) -> Optional[str]:
        """Get brand name from analysis result or metadata."""
        if self.analysis_result:
            return self.analysis_result.get("brand_name")
        if self.metadata_entry:
            return self.metadata_entry.brand_name
        return None
    
    def to_summary(self) -> Dict[str, Any]:
        """Generate a summary of the processing context."""
        return {
            "external_id": self.external_id,
            "ad_id": self.ad_id,
            "source": self.source,
            "elapsed_time": round(self.elapsed_time(), 2),
            "completed_stages": self.completed_stages,
            "skipped_stages": self.skipped_stages,
            "failed_stages": self.failed_stages,
            "segments": len(self.segment_ids),
            "chunks": len(self.chunk_ids),
            "claims": len(self.claim_ids),
            "storyboard_shots": len(self.storyboard_shots),
            "embeddings": self.embedding_count,
            "has_processing_notes": bool(self.processing_notes),
        }

