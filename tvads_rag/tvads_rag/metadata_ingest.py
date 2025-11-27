"""
Utilities for loading legacy ad metadata spreadsheets and flagging hero ads.
"""

from __future__ import annotations

import csv
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set

logger = logging.getLogger(__name__)


@dataclass
class AdMetadataEntry:
    """Normalized metadata captured from the legacy spreadsheet."""

    external_id: str
    record_id: Optional[str] = None
    movie_filename: Optional[str] = None
    title: Optional[str] = None
    brand_name: Optional[str] = None
    views: Optional[int] = None
    duration_seconds: Optional[float] = None
    video_url: Optional[str] = None
    still_url: Optional[str] = None
    date_collected: Optional[str] = None
    advertiser_raw: Optional[str] = None
    raw_row: Dict[str, str] = field(default_factory=dict)


@dataclass
class MetadataIndex:
    """Lookups + hero-ad flags derived from the spreadsheet."""

    entries: Dict[str, AdMetadataEntry]
    hero_threshold: Optional[int]
    hero_ids: Set[str]

    def get(self, external_id: str) -> Optional[AdMetadataEntry]:
        return self.entries.get(external_id)

    def is_hero(self, external_id: str) -> bool:
        return external_id in self.hero_ids


def _normalize_header(name: str) -> str:
    return name.strip().lower().replace(" ", "_")


def _as_int(value: Optional[str]) -> Optional[int]:
    if value is None:
        return None
    value = value.strip().replace(",", "")
    if not value:
        return None
    try:
        return int(float(value))
    except ValueError:
        return None


def _as_float(value: Optional[str]) -> Optional[float]:
    if value is None:
        return None
    value = value.strip()
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _derive_external_id(row: Dict[str, str]) -> Optional[str]:
    candidates = [
        row.get("record_id"),
        row.get("movie_filename"),
        row.get("commercial_title"),
    ]
    for candidate in candidates:
        if candidate and candidate.strip():
            return candidate.strip()
    return None


def _compute_hero_threshold(view_counts: Iterable[int]) -> Optional[int]:
    counts = sorted([v for v in view_counts if v is not None and v >= 0], reverse=True)
    if not counts:
        return None
    hero_count = max(1, int(len(counts) * 0.1))
    cutoff_index = min(hero_count - 1, len(counts) - 1)
    return counts[cutoff_index]


def load_metadata(csv_path: str) -> MetadataIndex:
    """
    Load metadata from a CSV spreadsheet and determine hero ads (top 10% by views).
    """
    path = Path(csv_path)
    if not path.exists():
        raise FileNotFoundError(f"Metadata CSV not found: {path}")

    entries: Dict[str, AdMetadataEntry] = {}
    view_counts: List[int] = []

    with path.open("r", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        headers = [_normalize_header(h) for h in reader.fieldnames or []]
        reader.fieldnames = headers

        for row in reader:
            external_id = _derive_external_id(row)
            if not external_id:
                logger.warning("Skipping row without identifiable external_id: %s", row)
                continue

            views = _as_int(row.get("views"))
            if views is not None:
                view_counts.append(views)

            entry = AdMetadataEntry(
                external_id=external_id,
                record_id=row.get("record_id"),
                movie_filename=row.get("movie_filename"),
                title=row.get("commercial_title") or row.get("title"),
                brand_name=row.get("advertiser-1") or row.get("brand_name"),
                views=views,
                duration_seconds=_as_float(row.get("length")),
                video_url=row.get("vid_filename_link") or row.get("video_link"),
                still_url=row.get("still_filename_link"),
                date_collected=row.get("date_collected"),
                advertiser_raw=row.get("advertiser-1"),
                raw_row=row,
            )
            # Primary key: derived external_id (typically record_id for legacy sheets)
            entries[external_id] = entry

            # Also index by record_id and movie_filename so we can join regardless of
            # whether the pipeline uses numeric IDs or filenames like TA25847.
            # This is important because ingestion derives `external_id` from the
            # video filename / S3 key (Path.stem).
            record_id = (row.get("record_id") or "").strip()
            if record_id and record_id != external_id:
                entries.setdefault(record_id, entry)

            movie_filename = (row.get("movie_filename") or "").strip()
            if movie_filename and movie_filename != external_id:
                entries.setdefault(movie_filename, entry)

    hero_threshold = _compute_hero_threshold(view_counts)
    hero_ids: Set[str] = set()
    if hero_threshold is not None:
        for entry in entries.values():
            if entry.views is not None and entry.views >= hero_threshold:
                hero_ids.add(entry.external_id)

    logger.info(
        "Loaded %s metadata rows. Hero threshold=%s. Hero ads=%s",
        len(entries),
        hero_threshold,
        len(hero_ids),
    )
    return MetadataIndex(entries=entries, hero_threshold=hero_threshold, hero_ids=hero_ids)


__all__ = ["AdMetadataEntry", "MetadataIndex", "load_metadata"]


