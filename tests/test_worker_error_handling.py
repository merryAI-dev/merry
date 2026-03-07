"""Tests for worker error handling paths — _is_retryable enhancements,
temp directory cleanup, assembly failure, and metrics recording."""
import json
import os
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from worker.main import (
    _is_retryable,
    _MetricsAccumulator,
    _call_with_backoff,
)


# ═══════════════════════════════════════════
# _is_retryable — HTTP status code tests
# ═══════════════════════════════════════════

class TestIsRetryableHTTPStatus:
    """Tests for HTTP status code based retry classification."""

    def _make_boto_exc(self, code: str, http_status: int) -> Exception:
        exc = Exception(f"An error occurred ({code})")
        exc.response = {  # type: ignore[attr-defined]
            "Error": {"Code": code},
            "ResponseMetadata": {"HTTPStatusCode": http_status},
        }
        return exc

    def test_429_is_throttle(self):
        exc = self._make_boto_exc("TooManyRequestsException", 429)
        retryable, cat = _is_retryable(exc)
        assert retryable is True
        assert cat == "throttle"

    def test_500_is_transient(self):
        exc = self._make_boto_exc("InternalServerError", 500)
        retryable, cat = _is_retryable(exc)
        assert retryable is True
        assert cat == "transient"

    def test_502_is_transient(self):
        exc = self._make_boto_exc("BadGateway", 502)
        retryable, cat = _is_retryable(exc)
        assert retryable is True
        assert cat == "transient"

    def test_503_is_transient(self):
        exc = self._make_boto_exc("ServiceUnavailable", 503)
        retryable, cat = _is_retryable(exc)
        assert retryable is True

    def test_504_is_transient(self):
        exc = self._make_boto_exc("GatewayTimeout", 504)
        retryable, cat = _is_retryable(exc)
        assert retryable is True
        assert cat == "transient"

    def test_400_is_not_retryable(self):
        exc = self._make_boto_exc("ValidationException", 400)
        retryable, _ = _is_retryable(exc)
        assert retryable is False

    def test_403_is_not_retryable(self):
        exc = self._make_boto_exc("AccessDeniedException", 403)
        retryable, _ = _is_retryable(exc)
        assert retryable is False

    def test_404_is_not_retryable(self):
        exc = self._make_boto_exc("ResourceNotFoundException", 404)
        retryable, _ = _is_retryable(exc)
        assert retryable is False


# ═══════════════════════════════════════════
# _is_retryable — Bedrock specific types
# ═══════════════════════════════════════════

class TestIsRetryableBedrockTypes:
    """Tests for Bedrock-specific exception types."""

    def _make_typed_exc(self, type_name: str, msg: str = "error") -> Exception:
        exc = type(type_name, (Exception,), {})(msg)
        return exc

    def test_model_stream_error(self):
        exc = self._make_typed_exc("ModelStreamErrorException", "Stream error")
        retryable, cat = _is_retryable(exc)
        assert retryable is True
        assert cat == "transient"

    def test_model_timeout(self):
        exc = self._make_typed_exc("ModelTimeoutException", "Model timed out")
        retryable, cat = _is_retryable(exc)
        assert retryable is True
        assert cat == "transient"

    def test_service_quota_exceeded(self):
        exc = self._make_typed_exc("ServiceQuotaExceededException", "Quota exceeded")
        retryable, cat = _is_retryable(exc)
        assert retryable is True
        assert cat == "throttle"

    def test_model_overloaded(self):
        exc = Exception("Model is overloaded, please retry")
        retryable, cat = _is_retryable(exc)
        assert retryable is True
        assert cat == "throttle"


# ═══════════════════════════════════════════
# _is_retryable — edge cases
# ═══════════════════════════════════════════

class TestIsRetryableEdgeCases:

    def test_none_response(self):
        """Exception with response=None should not crash."""
        exc = Exception("Some error")
        exc.response = None  # type: ignore[attr-defined]
        retryable, _ = _is_retryable(exc)
        # Should not raise; may or may not be retryable depending on message
        assert isinstance(retryable, bool)

    def test_empty_error_code(self):
        exc = Exception("Unknown")
        exc.response = {"Error": {}, "ResponseMetadata": {"HTTPStatusCode": 418}}  # type: ignore[attr-defined]
        retryable, _ = _is_retryable(exc)
        assert retryable is False

    def test_value_error_not_retryable(self):
        exc = ValueError("Invalid parameter")
        retryable, _ = _is_retryable(exc)
        assert retryable is False

    def test_runtime_error_not_retryable(self):
        exc = RuntimeError("Missing file metadata")
        retryable, _ = _is_retryable(exc)
        assert retryable is False


# ═══════════════════════════════════════════
# _MetricsAccumulator — job_type tracking
# ═══════════════════════════════════════════

class TestMetricsAccumulator:

    def test_job_type_tracking(self, capsys):
        os.environ["MERRY_CW_NAMESPACE"] = "TestNamespace"
        m = _MetricsAccumulator()
        m.record_task(True, 100.0, input_tokens=50, output_tokens=20, job_type="condition_check")
        m.record_task(True, 200.0, input_tokens=100, output_tokens=40, job_type="condition_check")
        m.record_task(False, 50.0, job_type="document_extraction")
        m.record_task(True, 150.0, job_type="")  # No job_type → not tracked per-type.

        m.flush(3)
        out = capsys.readouterr().out.strip().split("\n")

        # Should have at least 3 lines: aggregate + condition_check + document_extraction.
        assert len(out) >= 3

        agg = json.loads(out[0])
        assert agg["TasksSucceeded"] == 3
        assert agg["TasksFailed"] == 1

        # Find per-type lines.
        per_type = [json.loads(line) for line in out[1:]]
        cc = next((p for p in per_type if p.get("JobType") == "condition_check"), None)
        de = next((p for p in per_type if p.get("JobType") == "document_extraction"), None)

        assert cc is not None
        assert cc["TasksSucceeded"] == 2
        assert cc["TasksFailed"] == 0
        assert cc["InputTokens"] == 150

        assert de is not None
        assert de["TasksSucceeded"] == 0
        assert de["TasksFailed"] == 1

    def test_flush_resets_counters(self, capsys):
        os.environ["MERRY_CW_NAMESPACE"] = "TestNamespace"
        m = _MetricsAccumulator()
        m.record_task(True, 100.0, job_type="pdf_parse")
        m.flush(0)

        # Second flush should be empty.
        m.flush(0)
        out = capsys.readouterr().out.strip().split("\n")
        # Last line (second aggregate) should have 0 tasks.
        last_agg = json.loads(out[-1])
        assert last_agg["TasksSucceeded"] == 0

    def test_no_namespace_skips_emit(self, capsys):
        import worker.main as wm
        orig = wm.CW_NAMESPACE
        try:
            wm.CW_NAMESPACE = ""
            m = _MetricsAccumulator()
            m.record_task(True, 100.0)
            m.flush(0)
            out = capsys.readouterr().out.strip()
            assert out == ""
        finally:
            wm.CW_NAMESPACE = orig


# ═══════════════════════════════════════════
# _call_with_backoff — exhaustion
# ═══════════════════════════════════════════

class TestCallWithBackoff:

    def test_raises_after_max_retries(self):
        fn = MagicMock(side_effect=ConnectionError("reset"))
        with pytest.raises(ConnectionError):
            _call_with_backoff(fn, max_retries=2, base_delay=0.01)
        assert fn.call_count == 3  # initial + 2 retries

    def test_non_retryable_raises_immediately(self):
        fn = MagicMock(side_effect=ValueError("bad input"))
        with pytest.raises(ValueError):
            _call_with_backoff(fn, max_retries=3, base_delay=0.01)
        assert fn.call_count == 1

    def test_success_after_retry(self):
        fn = MagicMock(side_effect=[ConnectionError("reset"), "ok"])
        result = _call_with_backoff(fn, max_retries=3, base_delay=0.01)
        assert result == "ok"
        assert fn.call_count == 2
