"""Unit tests for _is_retryable and _call_with_backoff retry logic."""
import time
from unittest.mock import MagicMock

import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from worker.main import _is_retryable, _call_with_backoff


class TestIsRetryable:
    """Tests for _is_retryable error classification."""

    def test_throttle_bedrock(self):
        exc = Exception("ThrottlingException: Rate exceeded")
        retryable, cat = _is_retryable(exc)
        assert retryable is True
        assert cat == "throttle"

    def test_throttle_too_many_requests(self):
        exc = Exception("Too many requests")
        retryable, cat = _is_retryable(exc)
        assert retryable is True
        assert cat == "throttle"

    def test_throttle_limit_exceeded(self):
        exc = Exception("Limit exceeded for model")
        retryable, cat = _is_retryable(exc)
        assert retryable is True
        assert cat == "throttle"

    def test_throttle_s3_slowdown(self):
        exc = Exception("SlowDown: Please reduce your request rate")
        retryable, cat = _is_retryable(exc)
        assert retryable is True
        assert cat == "throttle"

    def test_throttle_provisioned_throughput(self):
        exc = Exception("Provisioned throughput exceeded")
        retryable, cat = _is_retryable(exc)
        assert retryable is True
        assert cat == "throttle"

    def test_transient_connection_error(self):
        exc = ConnectionError("Connection reset by peer")
        retryable, cat = _is_retryable(exc)
        assert retryable is True
        assert cat == "transient"

    def test_transient_timeout_error(self):
        exc = TimeoutError("Read timed out")
        retryable, cat = _is_retryable(exc)
        assert retryable is True
        assert cat == "transient"

    def test_transient_connection_reset(self):
        exc = ConnectionResetError("Connection reset")
        retryable, cat = _is_retryable(exc)
        assert retryable is True
        assert cat == "transient"

    def test_transient_broken_pipe(self):
        exc = BrokenPipeError("Broken pipe")
        retryable, cat = _is_retryable(exc)
        assert retryable is True
        assert cat == "transient"

    def test_transient_keyword_503(self):
        exc = Exception("Service unavailable (503)")
        retryable, cat = _is_retryable(exc)
        assert retryable is True
        assert cat == "transient"

    def test_transient_keyword_502(self):
        exc = Exception("Bad gateway 502")
        retryable, cat = _is_retryable(exc)
        assert retryable is True
        assert cat == "transient"

    def test_transient_keyword_504(self):
        exc = Exception("504 Gateway Timeout")
        retryable, cat = _is_retryable(exc)
        assert retryable is True
        assert cat == "transient"

    def test_transient_keyword_internal_server_error(self):
        exc = Exception("Internal server error")
        retryable, cat = _is_retryable(exc)
        assert retryable is True
        assert cat == "transient"

    def test_transient_keyword_dns(self):
        exc = Exception("Temporary failure in name resolution")
        retryable, cat = _is_retryable(exc)
        assert retryable is True
        assert cat == "transient"

    def test_botocore_internal_server_error(self):
        exc = Exception("InternalServerError")
        exc.response = {"Error": {"Code": "InternalServerError"}}
        retryable, cat = _is_retryable(exc)
        assert retryable is True
        assert cat == "transient"

    def test_botocore_transaction_conflict(self):
        exc = Exception("TransactionConflictException")
        exc.response = {"Error": {"Code": "TransactionConflictException"}}
        retryable, cat = _is_retryable(exc)
        assert retryable is True
        assert cat == "transient"

    def test_transaction_canceled_with_conflict_reason_is_retryable(self):
        exc = Exception(
            "TransactionCanceledException: Transaction cancelled "
            "[None, None, TransactionConflict]"
        )
        exc.response = {
            "Error": {"Code": "TransactionCanceledException"},
            "CancellationReasons": [{}, {}, {"Code": "TransactionConflict"}],
        }
        retryable, cat = _is_retryable(exc)
        assert retryable is True
        assert cat == "transient"

    def test_botocore_provisioned_throughput_code(self):
        exc = Exception("Throughput exceeded")
        exc.response = {"Error": {"Code": "ProvisionedThroughputExceededException"}}
        retryable, cat = _is_retryable(exc)
        assert retryable is True
        assert cat == "throttle"

    def test_not_retryable_validation_error(self):
        exc = Exception("ValidationException: Invalid parameter")
        retryable, _ = _is_retryable(exc)
        assert retryable is False

    def test_not_retryable_file_not_found(self):
        exc = FileNotFoundError("file.pdf not found")
        retryable, _ = _is_retryable(exc)
        assert retryable is False

    def test_not_retryable_key_error(self):
        exc = KeyError("missing_key")
        retryable, _ = _is_retryable(exc)
        assert retryable is False

    def test_not_retryable_runtime_error(self):
        exc = RuntimeError("conditions 파라미터가 비어 있습니다")
        retryable, _ = _is_retryable(exc)
        assert retryable is False

    def test_not_retryable_conditional_check(self):
        exc = Exception("ConditionalCheckFailedException")
        retryable, _ = _is_retryable(exc)
        assert retryable is False


class TestCallWithBackoff:
    """Tests for _call_with_backoff retry behavior."""

    def test_success_first_attempt(self):
        fn = MagicMock(return_value="ok")
        result = _call_with_backoff(fn, max_retries=3, base_delay=0.01)
        assert result == "ok"
        assert fn.call_count == 1

    def test_retry_on_throttle_then_succeed(self):
        fn = MagicMock(side_effect=[
            Exception("ThrottlingException: too fast"),
            "ok",
        ])
        result = _call_with_backoff(fn, max_retries=3, base_delay=0.01)
        assert result == "ok"
        assert fn.call_count == 2

    def test_retry_on_transient_then_succeed(self):
        fn = MagicMock(side_effect=[
            ConnectionError("Connection reset"),
            TimeoutError("Read timed out"),
            "ok",
        ])
        result = _call_with_backoff(fn, max_retries=3, base_delay=0.01)
        assert result == "ok"
        assert fn.call_count == 3

    def test_non_retryable_raises_immediately(self):
        fn = MagicMock(side_effect=RuntimeError("bad input"))
        with pytest.raises(RuntimeError, match="bad input"):
            _call_with_backoff(fn, max_retries=3, base_delay=0.01)
        assert fn.call_count == 1

    def test_max_retries_exhausted(self):
        fn = MagicMock(side_effect=Exception("ThrottlingException: rate limit"))
        with pytest.raises(Exception, match="ThrottlingException"):
            _call_with_backoff(fn, max_retries=2, base_delay=0.01)
        assert fn.call_count == 3  # initial + 2 retries

    def test_passes_args_and_kwargs(self):
        fn = MagicMock(return_value=42)
        result = _call_with_backoff(fn, "a", "b", max_retries=1, base_delay=0.01, key="val")
        assert result == 42
        fn.assert_called_once_with("a", "b", key="val")

    def test_exponential_delay_increases(self):
        """Verify delays increase exponentially (rough check)."""
        call_times = []

        def slow_fail(*args, **kwargs):
            call_times.append(time.time())
            raise Exception("Service unavailable (503)")

        fn = MagicMock(side_effect=slow_fail)
        with pytest.raises(Exception, match="Service unavailable"):
            _call_with_backoff(fn, max_retries=2, base_delay=0.1)

        assert len(call_times) == 3
        delay1 = call_times[1] - call_times[0]
        delay2 = call_times[2] - call_times[1]
        # Both delays should be positive (base_delay=0.1 + jitter).
        assert delay1 > 0.05
        assert delay2 > 0.1  # second delay = 0.1 * 2^1 + jitter ≥ 0.2
