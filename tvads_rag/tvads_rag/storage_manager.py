"""
S3 Storage Manager for video processing pipeline.

Handles S3/R2 object lifecycle for keyframe storage:
- Upload keyframe JPEGs with correct Content-Type
- Generate public URLs for database storage
- Bulk delete frames when ads are removed
- Concurrent uploads for performance

Compatible with AWS S3 and Cloudflare R2.
"""

from __future__ import annotations

import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import List, Optional, Tuple
from urllib.parse import urlparse

try:
    import boto3
    from botocore.exceptions import ClientError, NoCredentialsError
    BOTO3_AVAILABLE = True
except ImportError:
    boto3 = None  # type: ignore
    ClientError = Exception  # type: ignore
    NoCredentialsError = Exception  # type: ignore
    BOTO3_AVAILABLE = False

logger = logging.getLogger(__name__)


class StorageManagerError(Exception):
    """Base exception for StorageManager errors."""
    pass


class StorageManager:
    """
    S3/R2 storage manager for keyframe uploads.
    
    Handles:
    - Uploading keyframe JPEGs with correct Content-Type (image/jpeg)
    - Constructing public URLs for stored objects
    - Bulk deleting frames when ads are removed
    - Concurrent uploads for batches >5 images
    
    Configuration via environment variables:
    - AWS_ACCESS_KEY_ID: Required
    - AWS_SECRET_ACCESS_KEY: Required
    - S3_BUCKET_NAME: Required (or FRAMES_BUCKET_NAME)
    - S3_REGION: Required (e.g., "us-east-1", "auto" for R2)
    - S3_ENDPOINT_URL: Optional (for Cloudflare R2 or S3-compatible services)
    - S3_PUBLIC_URL_BASE: Optional (custom domain for public URLs)
    
    Usage:
        storage = StorageManager()
        url = storage.upload_frame("/tmp/frame.jpg", "ad123", 0)
        storage.delete_ad_frames("ad123")
    """
    
    def __init__(
        self,
        access_key: Optional[str] = None,
        secret_key: Optional[str] = None,
        bucket_name: Optional[str] = None,
        region: Optional[str] = None,
        endpoint_url: Optional[str] = None,
        public_url_base: Optional[str] = None,
        max_workers: int = 5,
    ):
        """
        Initialize StorageManager.
        
        Args:
            access_key: AWS access key (default: from AWS_ACCESS_KEY_ID env)
            secret_key: AWS secret key (default: from AWS_SECRET_ACCESS_KEY env)
            bucket_name: S3 bucket name (default: from S3_BUCKET_NAME or FRAMES_BUCKET_NAME env)
            region: AWS region (default: from S3_REGION or AWS_REGION env)
            endpoint_url: S3 endpoint URL for R2/compatible services (default: from S3_ENDPOINT_URL env)
            public_url_base: Base URL for public access (default: constructed from bucket/region)
            max_workers: Max concurrent upload threads (default: 5)
        """
        if not BOTO3_AVAILABLE:
            raise StorageManagerError("boto3 is not installed. Run: pip install boto3")
        
        # Load configuration from environment or parameters
        self.access_key = access_key or os.getenv("AWS_ACCESS_KEY_ID")
        self.secret_key = secret_key or os.getenv("AWS_SECRET_ACCESS_KEY")
        self.bucket = bucket_name or os.getenv("S3_BUCKET_NAME") or os.getenv("FRAMES_BUCKET_NAME")
        self.region = region or os.getenv("S3_REGION") or os.getenv("AWS_REGION") or "us-east-1"
        self.endpoint_url = endpoint_url or os.getenv("S3_ENDPOINT_URL")
        self.public_url_base = public_url_base or os.getenv("S3_PUBLIC_URL_BASE")
        self.max_workers = max_workers
        
        # Validate required configuration
        if not self.access_key:
            raise StorageManagerError("AWS_ACCESS_KEY_ID not configured")
        if not self.secret_key:
            raise StorageManagerError("AWS_SECRET_ACCESS_KEY not configured")
        if not self.bucket:
            raise StorageManagerError("S3_BUCKET_NAME not configured")
        
        # Initialize boto3 client
        self._client = None
    
    @property
    def client(self):
        """Lazy-initialize boto3 S3 client."""
        if self._client is None:
            client_kwargs = {
                "service_name": "s3",
                "aws_access_key_id": self.access_key,
                "aws_secret_access_key": self.secret_key,
                "region_name": self.region,
            }
            
            # Add endpoint URL for R2 or S3-compatible services
            if self.endpoint_url:
                client_kwargs["endpoint_url"] = self.endpoint_url
            
            self._client = boto3.client(**client_kwargs)
            logger.debug(
                "Initialized S3 client: bucket=%s, region=%s, endpoint=%s",
                self.bucket, self.region, self.endpoint_url or "default"
            )
        
        return self._client
    
    def _construct_key(self, ad_id: str, scene_index: int) -> str:
        """Construct S3 object key for a frame."""
        return f"frames/{ad_id}/{ad_id}_scene_{scene_index}.jpg"
    
    def _construct_url(self, key: str) -> str:
        """Construct public URL for an S3 object."""
        # Use custom public URL base if provided
        if self.public_url_base:
            base = self.public_url_base.rstrip("/")
            return f"{base}/{key}"
        
        # Cloudflare R2 or custom endpoint
        if self.endpoint_url:
            # Parse endpoint to construct URL
            # R2 format: https://<account_id>.r2.cloudflarestorage.com/<bucket>/<key>
            # Or with custom domain: https://cdn.example.com/<key>
            parsed = urlparse(self.endpoint_url)
            if "r2.cloudflarestorage.com" in parsed.netloc:
                # R2 storage - use public bucket URL or R2.dev
                return f"https://{self.bucket}.{parsed.netloc}/{key}"
            else:
                # Custom endpoint - assume bucket is in path or separate domain
                return f"{self.endpoint_url}/{self.bucket}/{key}"
        
        # Standard AWS S3 URL
        return f"https://{self.bucket}.s3.{self.region}.amazonaws.com/{key}"
    
    def upload_frame(
        self,
        file_path: str,
        ad_id: str,
        scene_index: int,
        content_type: str = "image/jpeg",
    ) -> str:
        """
        Upload a keyframe image to S3.
        
        Args:
            file_path: Local path to the JPG image
            ad_id: Ad identifier (used in S3 key)
            scene_index: Scene number (used in S3 key)
            content_type: MIME type (default: image/jpeg)
        
        Returns:
            Public URL of the uploaded frame
        
        Raises:
            StorageManagerError: If upload fails
            FileNotFoundError: If file_path doesn't exist
        """
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"Frame file not found: {file_path}")
        
        key = self._construct_key(ad_id, scene_index)
        
        try:
            # Upload with explicit Content-Type so browsers display instead of download
            self.client.upload_file(
                str(file_path),
                self.bucket,
                key,
                ExtraArgs={"ContentType": content_type}
            )
            
            url = self._construct_url(key)
            logger.debug("Uploaded frame: %s -> %s", file_path.name, url)
            return url
            
        except NoCredentialsError as e:
            raise StorageManagerError(f"Invalid S3 credentials: {e}")
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            raise StorageManagerError(f"S3 upload failed ({error_code}): {e}")
    
    def upload_frames_batch(
        self,
        frames: List[Tuple[str, str, int]],
    ) -> List[str]:
        """
        Upload multiple frames concurrently.
        
        Args:
            frames: List of (file_path, ad_id, scene_index) tuples
        
        Returns:
            List of public URLs (in same order as input)
        
        For batches >5 images, uses ThreadPoolExecutor for parallel uploads.
        """
        if not frames:
            return []
        
        # For small batches, upload sequentially
        if len(frames) <= 5:
            return [self.upload_frame(*f) for f in frames]
        
        # For larger batches, use concurrent uploads
        results = {}
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all upload tasks
            future_to_index = {
                executor.submit(self.upload_frame, *frame): i
                for i, frame in enumerate(frames)
            }
            
            # Collect results as they complete
            for future in as_completed(future_to_index):
                index = future_to_index[future]
                try:
                    results[index] = future.result()
                except Exception as e:
                    logger.error("Failed to upload frame %d: %s", index, str(e)[:100])
                    results[index] = None
        
        # Return results in original order, filtering out failures
        return [results.get(i) for i in range(len(frames)) if results.get(i)]
    
    def delete_ad_frames(self, ad_id: str) -> int:
        """
        Delete all frames associated with an ad.
        
        Args:
            ad_id: Ad identifier
        
        Returns:
            Number of objects deleted
        
        Safe: Handles empty folders without crashing.
        """
        prefix = f"frames/{ad_id}/"
        deleted_count = 0
        
        try:
            # List all objects with the prefix
            paginator = self.client.get_paginator("list_objects_v2")
            pages = paginator.paginate(Bucket=self.bucket, Prefix=prefix)
            
            for page in pages:
                if "Contents" not in page:
                    continue  # No objects with this prefix
                
                # Build list of keys to delete
                delete_keys = [{"Key": obj["Key"]} for obj in page["Contents"]]
                
                if not delete_keys:
                    continue
                
                # Bulk delete (max 1000 per request)
                response = self.client.delete_objects(
                    Bucket=self.bucket,
                    Delete={"Objects": delete_keys}
                )
                
                deleted = len(response.get("Deleted", []))
                deleted_count += deleted
                
                errors = response.get("Errors", [])
                if errors:
                    for err in errors:
                        logger.warning(
                            "Failed to delete %s: %s",
                            err.get("Key"), err.get("Message")
                        )
            
            if deleted_count > 0:
                logger.info("Deleted %d frames for ad %s", deleted_count, ad_id)
            else:
                logger.debug("No frames to delete for ad %s", ad_id)
            
            return deleted_count
            
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            logger.error("Failed to delete frames for ad %s (%s): %s", ad_id, error_code, e)
            return 0
    
    def get_frame_url(self, ad_id: str, scene_index: int) -> str:
        """
        Get the public URL for a frame (without uploading).
        
        Args:
            ad_id: Ad identifier
            scene_index: Scene number
        
        Returns:
            Public URL where the frame would be/is stored
        """
        key = self._construct_key(ad_id, scene_index)
        return self._construct_url(key)
    
    def frame_exists(self, ad_id: str, scene_index: int) -> bool:
        """
        Check if a frame exists in S3.
        
        Args:
            ad_id: Ad identifier
            scene_index: Scene number
        
        Returns:
            True if frame exists, False otherwise
        """
        key = self._construct_key(ad_id, scene_index)
        
        try:
            self.client.head_object(Bucket=self.bucket, Key=key)
            return True
        except ClientError as e:
            if e.response.get("Error", {}).get("Code") == "404":
                return False
            raise


# ---------------------------------------------------------------------------
# Convenience functions
# ---------------------------------------------------------------------------

_default_manager: Optional[StorageManager] = None


def get_storage_manager() -> StorageManager:
    """Get or create the default StorageManager instance."""
    global _default_manager
    if _default_manager is None:
        _default_manager = StorageManager()
    return _default_manager


def upload_frame(file_path: str, ad_id: str, scene_index: int) -> str:
    """Upload a frame using the default StorageManager."""
    return get_storage_manager().upload_frame(file_path, ad_id, scene_index)


def delete_ad_frames(ad_id: str) -> int:
    """Delete all frames for an ad using the default StorageManager."""
    return get_storage_manager().delete_ad_frames(ad_id)


# ---------------------------------------------------------------------------
# Integration example (commented code showing PhysicsExtractor usage)
# ---------------------------------------------------------------------------

"""
# Integration with PhysicsExtractor:
# Add this to physics_engine.py extract() method after keyframe extraction

from .storage_manager import StorageManager

# Initialize storage manager (once per session, not per ad)
storage = StorageManager()

# After extracting keyframes...
frame_urls = []
for i, local_path in enumerate(keyframes_saved):
    try:
        # Upload to S3/R2
        url = storage.upload_frame(local_path, ad_id, i)
        frame_urls.append(url)
        
        # Cleanup local file immediately after successful upload
        os.remove(local_path)
        
    except Exception as e:
        logger.warning("Failed to upload frame %d: %s", i, str(e)[:100])
        # Keep local path as fallback
        frame_urls.append(local_path)

# Store URLs instead of local paths in result
result["keyframes_urls"] = frame_urls


# When deleting an ad, also delete its frames:
# In reset_ads.py or ad deletion logic:

from .storage_manager import delete_ad_frames

def delete_ad(ad_id: str):
    # Delete from database first
    db_backend.delete_ad(ad_id)
    
    # Then cleanup S3 frames
    deleted = delete_ad_frames(ad_id)
    logger.info("Deleted ad %s and %d frames", ad_id, deleted)
"""


# ---------------------------------------------------------------------------
# Exports
# ---------------------------------------------------------------------------

__all__ = [
    "StorageManager",
    "StorageManagerError",
    "get_storage_manager",
    "upload_frame",
    "delete_ad_frames",
    "BOTO3_AVAILABLE",
]




