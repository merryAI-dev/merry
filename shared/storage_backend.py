"""
Storage backend abstraction for training data.

Supports local filesystem (current) and AWS S3 (future migration).
Designed for secure data collection with encryption and access control.
"""

import json
import os
import uuid
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .logging_config import get_logger

logger = get_logger("storage_backend")


class StorageBackend(ABC):
    """Abstract storage backend for training data."""

    @abstractmethod
    def write_training_sample(
        self,
        task_type: str,
        sample: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Write a training sample to storage.

        Args:
            task_type: Type of task (pdf_extraction, table_classification, etc.)
            sample: Training sample data (input/output pair)
            metadata: Optional metadata (model, timestamp, etc.)

        Returns:
            Storage path/key of written sample
        """
        pass

    @abstractmethod
    def list_samples(
        self,
        task_type: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> List[str]:
        """List training samples for a task type.

        Args:
            task_type: Type of task
            start_date: Optional start date filter
            end_date: Optional end date filter

        Returns:
            List of sample paths/keys
        """
        pass

    @abstractmethod
    def read_sample(self, path: str) -> Dict[str, Any]:
        """Read a training sample from storage.

        Args:
            path: Storage path/key

        Returns:
            Sample data
        """
        pass

    @abstractmethod
    def get_dataset_stats(self, task_type: str) -> Dict[str, Any]:
        """Get statistics for a task type dataset.

        Args:
            task_type: Type of task

        Returns:
            Stats dict (sample_count, size_bytes, date_range, etc.)
        """
        pass


class LocalStorageBackend(StorageBackend):
    """Local filesystem storage backend.

    Stores training data in JSONL format under data/training/{task_type}/
    """

    def __init__(self, base_dir: Optional[Path] = None):
        """Initialize local storage backend.

        Args:
            base_dir: Base directory for training data (default: PROJECT_ROOT/data/training)
        """
        if base_dir is None:
            from pathlib import Path

            project_root = Path(__file__).parent.parent
            base_dir = project_root / "data" / "training"

        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"LocalStorageBackend initialized: {self.base_dir}")

    def write_training_sample(
        self,
        task_type: str,
        sample: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Write training sample to local JSONL file."""
        task_dir = self.base_dir / task_type
        task_dir.mkdir(parents=True, exist_ok=True)

        # JSONL file per day for easy management
        today = datetime.now().strftime("%Y%m%d")
        jsonl_path = task_dir / f"{today}.jsonl"

        # Combine sample + metadata
        record = {
            "timestamp": datetime.now().isoformat(),
            "task_type": task_type,
            **sample,
        }
        if metadata:
            record["metadata"] = metadata

        # Append to JSONL (thread-safe with 'a' mode)
        try:
            with open(jsonl_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
            logger.debug(f"Wrote training sample: {jsonl_path}")
            return str(jsonl_path)
        except Exception as e:
            logger.error(f"Failed to write training sample: {e}", exc_info=True)
            raise

    def list_samples(
        self,
        task_type: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> List[str]:
        """List JSONL files for a task type."""
        task_dir = self.base_dir / task_type
        if not task_dir.exists():
            return []

        jsonl_files = sorted(task_dir.glob("*.jsonl"))

        # Filter by date range if specified
        if start_date or end_date:
            filtered = []
            for path in jsonl_files:
                # Parse YYYYMMDD.jsonl
                try:
                    date_str = path.stem
                    file_date = datetime.strptime(date_str, "%Y%m%d")
                    if start_date and file_date < start_date:
                        continue
                    if end_date and file_date > end_date:
                        continue
                    filtered.append(str(path))
                except ValueError:
                    # Non-date filename, include it
                    filtered.append(str(path))
            return filtered

        return [str(p) for p in jsonl_files]

    def read_sample(self, path: str) -> Dict[str, Any]:
        """Read a single sample (not typically needed for JSONL)."""
        # This reads the entire JSONL file as a list of samples
        samples = []
        try:
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    samples.append(json.loads(line))
            return {"path": path, "samples": samples, "count": len(samples)}
        except Exception as e:
            logger.error(f"Failed to read sample: {e}", exc_info=True)
            raise

    def get_dataset_stats(self, task_type: str) -> Dict[str, Any]:
        """Get statistics for a task type dataset."""
        task_dir = self.base_dir / task_type
        if not task_dir.exists():
            return {
                "task_type": task_type,
                "sample_count": 0,
                "file_count": 0,
                "total_size_bytes": 0,
                "date_range": None,
            }

        jsonl_files = list(task_dir.glob("*.jsonl"))
        total_samples = 0
        total_size = 0
        dates = []

        for path in jsonl_files:
            total_size += path.stat().st_size
            # Count lines in JSONL
            try:
                with open(path, "r", encoding="utf-8") as f:
                    total_samples += sum(1 for line in f if line.strip())
                # Parse date from filename
                try:
                    date_str = path.stem
                    dates.append(datetime.strptime(date_str, "%Y%m%d"))
                except ValueError:
                    pass
            except Exception as e:
                logger.warning(f"Error reading {path}: {e}")

        date_range = None
        if dates:
            dates.sort()
            date_range = {
                "start": dates[0].strftime("%Y-%m-%d"),
                "end": dates[-1].strftime("%Y-%m-%d"),
            }

        return {
            "task_type": task_type,
            "sample_count": total_samples,
            "file_count": len(jsonl_files),
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "date_range": date_range,
        }


class S3StorageBackend(StorageBackend):
    """AWS S3 storage backend (future implementation).

    Design notes for migration:
    - Bucket: merry-training-data
    - Key structure: {task_type}/{YYYY}/{MM}/{DD}/{uuid}.jsonl
    - Encryption: AES-256 server-side encryption
    - Access: IAM role-based, no public access
    - Lifecycle: Archive to Glacier after 90 days
    """

    def __init__(self, bucket_name: str, prefix: str = "training/"):
        """Initialize S3 storage backend.

        Args:
            bucket_name: S3 bucket name
            prefix: Key prefix for training data
        """
        self.bucket_name = bucket_name
        self.prefix = prefix
        self._s3_client = None
        logger.info(f"S3StorageBackend initialized: s3://{bucket_name}/{prefix}")

    def _get_s3_client(self):
        """Lazy-load S3 client (requires boto3)."""
        if self._s3_client is None:
            try:
                import boto3

                self._s3_client = boto3.client("s3")
            except ImportError:
                raise ImportError("boto3 is required for S3 storage. Install: pip install boto3")
        return self._s3_client

    def write_training_sample(
        self,
        task_type: str,
        sample: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Write training sample to S3.

        Key structure: {task_type}/{YYYY}/{MM}/{DD}/{uuid}.jsonl
        Example: pdf_extraction/2026/02/09/a1b2c3d4-e5f6-7890-abcd-ef1234567890.jsonl
        """
        s3 = self._get_s3_client()

        # Build S3 key with date hierarchy
        now = datetime.now()
        sample_id = str(uuid.uuid4())
        s3_key = f"{self.prefix}{task_type}/{now.year}/{now.month:02d}/{now.day:02d}/{sample_id}.jsonl"

        # Add timestamp to sample
        sample_with_meta = {
            "timestamp": now.isoformat(),
            "sample_id": sample_id,
            **sample,
        }
        if metadata:
            sample_with_meta["metadata"] = metadata

        # Write to S3 with server-side encryption
        try:
            jsonl_content = json.dumps(sample_with_meta, ensure_ascii=False) + "\n"
            s3.put_object(
                Bucket=self.bucket_name,
                Key=s3_key,
                Body=jsonl_content.encode("utf-8"),
                ServerSideEncryption="AES256",  # SSE-S3 encryption
                ContentType="application/x-ndjson",
            )
            logger.info(f"Wrote training sample to S3: s3://{self.bucket_name}/{s3_key}")
            return f"s3://{self.bucket_name}/{s3_key}"
        except Exception as e:
            logger.error(f"Failed to write to S3: {e}", exc_info=True)
            raise

    def list_samples(
        self,
        task_type: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> List[str]:
        """List training samples in S3.

        Returns:
            List of S3 URIs (s3://bucket/key)
        """
        s3 = self._get_s3_client()

        # List objects with task_type prefix
        prefix = f"{self.prefix}{task_type}/"
        s3_uris = []

        try:
            paginator = s3.get_paginator("list_objects_v2")
            for page in paginator.paginate(Bucket=self.bucket_name, Prefix=prefix):
                if "Contents" not in page:
                    continue

                for obj in page["Contents"]:
                    key = obj["Key"]
                    # Filter by date range if specified
                    if start_date or end_date:
                        # Extract date from key: task_type/YYYY/MM/DD/uuid.jsonl
                        parts = key.split("/")
                        if len(parts) >= 5:
                            try:
                                year, month, day = int(parts[-4]), int(parts[-3]), int(parts[-2])
                                file_date = datetime(year, month, day)
                                if start_date and file_date < start_date:
                                    continue
                                if end_date and file_date > end_date:
                                    continue
                            except (ValueError, IndexError):
                                # Invalid date structure, include anyway
                                pass

                    s3_uris.append(f"s3://{self.bucket_name}/{key}")

            return sorted(s3_uris)
        except Exception as e:
            logger.error(f"Failed to list S3 samples: {e}", exc_info=True)
            raise

    def read_sample(self, path: str) -> Dict[str, Any]:
        """Read training sample from S3.

        Args:
            path: S3 URI (s3://bucket/key) or just the key

        Returns:
            Dictionary with path, samples list, and count
        """
        s3 = self._get_s3_client()

        # Parse S3 URI
        if path.startswith("s3://"):
            # Extract bucket and key from s3://bucket/key
            parts = path[5:].split("/", 1)
            bucket = parts[0]
            key = parts[1] if len(parts) > 1 else ""
        else:
            # Assume it's just a key
            bucket = self.bucket_name
            key = path

        try:
            response = s3.get_object(Bucket=bucket, Key=key)
            content = response["Body"].read().decode("utf-8")

            # Parse JSONL
            samples = []
            for line in content.strip().split("\n"):
                if line.strip():
                    samples.append(json.loads(line))

            return {"path": f"s3://{bucket}/{key}", "samples": samples, "count": len(samples)}
        except Exception as e:
            logger.error(f"Failed to read S3 sample: {e}", exc_info=True)
            raise

    def get_dataset_stats(self, task_type: str) -> Dict[str, Any]:
        """Get dataset statistics from S3.

        Returns:
            Dictionary with task_type, sample_count, file_count, total_size_mb, date_range
        """
        s3 = self._get_s3_client()

        prefix = f"{self.prefix}{task_type}/"
        file_count = 0
        total_size = 0
        total_samples = 0
        dates = []

        try:
            paginator = s3.get_paginator("list_objects_v2")
            for page in paginator.paginate(Bucket=self.bucket_name, Prefix=prefix):
                if "Contents" not in page:
                    break

                for obj in page["Contents"]:
                    key = obj["Key"]
                    file_count += 1
                    total_size += obj["Size"]

                    # Count samples by reading file (expensive for large datasets)
                    # For production, consider storing sample count in object metadata
                    try:
                        response = s3.get_object(Bucket=self.bucket_name, Key=key)
                        content = response["Body"].read().decode("utf-8")
                        total_samples += sum(1 for line in content.strip().split("\n") if line.strip())
                    except Exception as e:
                        logger.warning(f"Error reading {key} for stats: {e}")

                    # Extract date from key
                    parts = key.split("/")
                    if len(parts) >= 5:
                        try:
                            year, month, day = int(parts[-4]), int(parts[-3]), int(parts[-2])
                            dates.append(datetime(year, month, day))
                        except (ValueError, IndexError):
                            pass

            date_range = None
            if dates:
                dates.sort()
                date_range = {
                    "start": dates[0].strftime("%Y-%m-%d"),
                    "end": dates[-1].strftime("%Y-%m-%d"),
                }

            return {
                "task_type": task_type,
                "sample_count": total_samples,
                "file_count": file_count,
                "total_size_bytes": total_size,
                "total_size_mb": total_size / (1024 * 1024),
                "date_range": date_range,
            }
        except Exception as e:
            logger.error(f"Failed to get S3 stats: {e}", exc_info=True)
            # Return empty stats instead of failing
            return {
                "task_type": task_type,
                "sample_count": 0,
                "file_count": 0,
                "total_size_bytes": 0,
                "total_size_mb": 0.0,
                "date_range": None,
            }


def get_storage_backend(backend_type: str = "local", **kwargs) -> StorageBackend:
    """Factory function to get storage backend.

    Args:
        backend_type: 'local' or 's3'
        **kwargs: Backend-specific arguments
            For s3: bucket_name, prefix (read from env if not provided)
            For local: base_dir (read from env if not provided)

    Returns:
        StorageBackend instance
    """
    if backend_type == "local":
        return LocalStorageBackend(**kwargs)
    elif backend_type == "s3":
        # Read S3 config from environment variables if not provided
        if "bucket_name" not in kwargs:
            kwargs["bucket_name"] = os.getenv("AWS_S3_BUCKET", "merry-training-data")
        if "prefix" not in kwargs:
            kwargs["prefix"] = os.getenv("AWS_S3_PREFIX", "training/")
        return S3StorageBackend(**kwargs)
    else:
        raise ValueError(f"Unknown backend type: {backend_type}")


# Global default backend (can be overridden via env var)
_default_backend = None


def get_default_storage() -> StorageBackend:
    """Get default storage backend (singleton)."""
    global _default_backend
    if _default_backend is None:
        backend_type = os.getenv("TRAINING_STORAGE_BACKEND", "local")
        _default_backend = get_storage_backend(backend_type)
    return _default_backend
