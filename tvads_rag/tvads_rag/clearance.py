"""
Regulatory clearance inference from external_id prefixes.

Known clearance body prefixes:
- TA* → UK Clearcast (UK)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, Optional

logger = logging.getLogger(__name__)


@dataclass
class ClearanceInfo:
    """Regulatory clearance information."""
    body: str           # e.g., "UK Clearcast"
    country: str        # e.g., "UK"
    clearance_id: str   # The official ID (often the external_id itself)


# =============================================================================
# Known Clearance Prefixes
# =============================================================================

# Map of external_id prefix -> (clearance_body, clearance_country)
CLEARANCE_PREFIXES: Dict[str, tuple[str, str]] = {
    "TA": ("UK Clearcast", "UK"),
    # Add more as identified:
    # "XX": ("ARPP France", "FR"),
    # "YY": ("FTC USA", "US"),
}


# =============================================================================
# Inference Functions
# =============================================================================

def infer_clearance_from_external_id(external_id: str) -> Optional[ClearanceInfo]:
    """
    Infer regulatory clearance from external_id prefix.

    Args:
        external_id: The ad's external identifier (e.g., "TABC12345")

    Returns:
        ClearanceInfo if prefix matches known clearance body, else None
    """
    if not external_id:
        return None

    external_id_upper = external_id.upper()

    for prefix, (body, country) in CLEARANCE_PREFIXES.items():
        if external_id_upper.startswith(prefix):
            logger.debug(
                "Inferred clearance for %s: %s (%s)",
                external_id, body, country
            )
            return ClearanceInfo(
                body=body,
                country=country,
                clearance_id=external_id,  # Use external_id as clearance ID
            )

    return None


def enrich_ad_data_with_clearance(ad_data: dict) -> dict:
    """
    Enrich ad_data dict with clearance fields if inferable from external_id.

    This is called during ingestion to auto-populate clearance fields.

    Args:
        ad_data: Ad metadata dict (must have 'external_id')

    Returns:
        Same dict with clearance_body, clearance_country, clearance_id added if inferred
    """
    external_id = ad_data.get("external_id")
    if not external_id:
        return ad_data

    # Don't overwrite if already set
    if ad_data.get("clearance_body"):
        return ad_data

    clearance = infer_clearance_from_external_id(external_id)
    if clearance:
        ad_data["clearance_body"] = clearance.body
        ad_data["clearance_country"] = clearance.country
        ad_data["clearance_id"] = clearance.clearance_id

        logger.info(
            "[%s] Auto-populated clearance: %s (%s)",
            external_id, clearance.body, clearance.country
        )

    return ad_data


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    "ClearanceInfo",
    "CLEARANCE_PREFIXES",
    "infer_clearance_from_external_id",
    "enrich_ad_data_with_clearance",
]
