"""
Training data collection decorator.

Logs tool executions for fine-tuning dataset creation.
Automatically scrubs PII and stores to configurable backend (local/S3).
"""

import os
import time
from functools import wraps
from typing import Any, Callable, Dict, Optional

from .logging_config import get_logger
from .pii_scrubber import scrub_training_sample, validate_no_pii
from .storage_backend import get_default_storage

logger = get_logger("training_logger")

# Enable/disable training data collection via env var
TRAINING_ENABLED = os.getenv("ENABLE_TRAINING_COLLECTION", "false").lower() == "true"


def log_training_data(
    task_type: str,
    model_name: Optional[str] = None,
    scrub_pii: bool = True,
    validate_pii: bool = True,
):
    """Decorator to log training data from tool executions.

    Usage:
        @log_training_data(task_type="pdf_extraction", model_name="claude-sonnet-4-5")
        def execute_read_pdf(pdf_path: str, max_pages: int = 30) -> Dict[str, Any]:
            # Tool implementation
            ...

    Args:
        task_type: Type of task (pdf_extraction, table_classification, text_parsing, json_repair)
        model_name: Model used (if known upfront, else extracted from result)
        scrub_pii: Whether to scrub PII from logged data
        validate_pii: Whether to validate no PII before logging

    Returns:
        Decorated function
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Check if training collection is enabled
            if not TRAINING_ENABLED:
                return func(*args, **kwargs)

            # Execute original function
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                success = True
                error = None
            except Exception as e:
                result = None
                success = False
                error = str(e)
                raise  # Re-raise after logging
            finally:
                elapsed = time.time() - start_time

                # Only log successful executions for training
                if success and result is not None:
                    try:
                        _log_sample(
                            task_type=task_type,
                            func_name=func.__name__,
                            input_params=kwargs,  # args typically not used in our tools
                            output=result,
                            model_name=model_name,
                            elapsed_seconds=elapsed,
                            scrub_pii=scrub_pii,
                            validate_pii=validate_pii,
                        )
                    except Exception as log_error:
                        # Don't fail the original function if logging fails
                        logger.error(
                            f"Failed to log training data for {func.__name__}: {log_error}",
                            exc_info=True,
                        )

            return result

        return wrapper

    return decorator


def _log_sample(
    task_type: str,
    func_name: str,
    input_params: Dict[str, Any],
    output: Dict[str, Any],
    model_name: Optional[str],
    elapsed_seconds: float,
    scrub_pii: bool,
    validate_pii: bool,
):
    """Internal function to log a training sample."""

    # Extract model from output if not provided
    if not model_name:
        model_name = output.get("processing_method") or output.get("model") or "unknown"

    # Build sample
    sample = {
        "function": func_name,
        "input": _sanitize_input(input_params),
        "output": _sanitize_output(output),
        "model": model_name,
        "elapsed_seconds": round(elapsed_seconds, 3),
    }

    # Scrub PII if requested
    if scrub_pii:
        sample = scrub_training_sample(sample)

    # Validate no PII if requested
    if validate_pii:
        warnings = validate_no_pii(sample)
        if warnings:
            logger.warning(
                f"PII detected in training sample for {func_name}: {len(warnings)} issues"
            )
            for warning in warnings[:5]:  # Log first 5
                logger.warning(f"  - {warning}")
            # Don't log if PII detected and validation is strict
            if os.getenv("TRAINING_PII_STRICT", "false").lower() == "true":
                logger.error("Skipping training sample due to PII detection (strict mode)")
                return

    # Write to storage
    try:
        storage = get_default_storage()
        path = storage.write_training_sample(
            task_type=task_type,
            sample=sample,
            metadata={
                "function": func_name,
                "model": model_name,
                "elapsed_seconds": elapsed_seconds,
            },
        )
        logger.info(f"Logged training sample: {task_type} ({func_name}) -> {path}")
    except Exception as e:
        logger.error(f"Failed to write training sample: {e}", exc_info=True)


def _sanitize_input(params: Dict[str, Any]) -> Dict[str, Any]:
    """Sanitize input parameters for training data.

    - Remove large binary data (base64 images, etc.)
    - Keep file paths, text, and structured data
    """
    sanitized = {}
    for key, value in params.items():
        # Skip large binary data
        if key in ("images_base64", "image_data", "binary_data"):
            sanitized[key] = f"[BINARY_DATA_{len(value) if hasattr(value, '__len__') else 0}_bytes]"
            continue

        # Keep file paths (useful for debugging, not PII)
        if key in ("pdf_path", "excel_path", "file_path", "jsonl_path"):
            # Only keep filename, not full path (could contain username)
            if isinstance(value, str):
                from pathlib import Path

                sanitized[key] = Path(value).name
            else:
                sanitized[key] = value
            continue

        # Keep simple types
        if isinstance(value, (str, int, float, bool, type(None))):
            sanitized[key] = value
        elif isinstance(value, (list, dict)):
            # Keep structured data (will be scrubbed later if needed)
            sanitized[key] = value
        else:
            sanitized[key] = f"[{type(value).__name__}]"

    return sanitized


def _sanitize_output(output: Dict[str, Any]) -> Dict[str, Any]:
    """Sanitize output for training data.

    - Keep structured extraction results
    - Remove large content fields
    - Keep success/error metadata
    """
    if not isinstance(output, dict):
        return {"raw_output": str(output)}

    sanitized = {}
    for key, value in output.items():
        # Keep success/error metadata
        if key in ("success", "error", "processing_method", "model", "cache_hit"):
            sanitized[key] = value
            continue

        # Keep structured extraction results (will be scrubbed for PII)
        if key in (
            "financial_tables",
            "company_info",
            "structured_content",
            "tables",
            "parsed_data",
            "valuation",
            "enterprise_value",
            "irr",
            "multiple",
        ):
            sanitized[key] = value
            continue

        # Skip large text content (keep only first 500 chars for context)
        if key in ("content", "text", "raw_output"):
            if isinstance(value, str) and len(value) > 500:
                sanitized[key] = value[:500] + f"... [truncated {len(value)} chars]"
            else:
                sanitized[key] = value
            continue

        # Keep simple types
        if isinstance(value, (str, int, float, bool, type(None))):
            sanitized[key] = value
        elif isinstance(value, (list, dict)):
            sanitized[key] = value
        else:
            sanitized[key] = f"[{type(value).__name__}]"

    return sanitized


# CLI tool to view collected data
def get_training_stats(task_type: Optional[str] = None) -> Dict[str, Any]:
    """Get training data collection statistics.

    Args:
        task_type: Optional task type filter

    Returns:
        Statistics dict
    """
    storage = get_default_storage()

    if task_type:
        return storage.get_dataset_stats(task_type)

    # Get stats for all task types
    from pathlib import Path

    base_dir = storage.base_dir if hasattr(storage, "base_dir") else Path("data/training")
    task_dirs = [d for d in base_dir.iterdir() if d.is_dir()]

    all_stats = {}
    for task_dir in task_dirs:
        task_name = task_dir.name
        all_stats[task_name] = storage.get_dataset_stats(task_name)

    return {
        "total_tasks": len(all_stats),
        "tasks": all_stats,
        "training_enabled": TRAINING_ENABLED,
    }


# Example usage
if __name__ == "__main__":
    import json

    # Demo: Get training stats
    stats = get_training_stats()
    print("Training Data Collection Stats:")
    print(json.dumps(stats, indent=2, ensure_ascii=False))
