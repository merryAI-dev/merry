"""
Prompt iteration logger.

Appends each RALPH Loop run to ralph/PROMPT_LOG.md for tracking
prompt evolution and debugging.
"""

import logging
import json
from datetime import datetime
from pathlib import Path
from typing import List

logger = logging.getLogger(__name__)

# Log file location
PROMPT_LOG_PATH = Path(__file__).parent / "PROMPT_LOG.md"


def log_prompt_iteration(
    pdf_path: str,
    doc_type: str,
    history: list,
    success: bool,
) -> None:
    """
    Append a RALPH loop run to PROMPT_LOG.md.

    Args:
        pdf_path: Source PDF path
        doc_type: Document type
        history: List of IterationLog objects
        success: Whether the loop succeeded
    """
    try:
        filename = Path(pdf_path).name
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        status = "SUCCESS" if success else "FAIL"

        lines = [
            f"\n## {now} | {doc_type} | {filename} | {status}\n",
        ]

        total_input = 0
        total_output = 0

        for it in history:
            attempt = it.attempt
            errors = it.errors
            prompt_type = it.prompt_used
            duration = it.duration_seconds
            model = it.model
            usage = it.usage

            total_input += usage.get("input_tokens", 0)
            total_output += usage.get("output_tokens", 0)

            if errors:
                error_summary = "; ".join(
                    f"`{e.get('field', '?')}`: {e.get('message', '?')}"
                    for e in errors[:5]
                )
                lines.append(f"### Attempt {attempt} (FAIL, {duration:.1f}s)")
                lines.append(f"- **Model**: {model}")
                lines.append(f"- **Prompt**: {prompt_type}")
                lines.append(f"- **Errors**: {error_summary}")
                if usage:
                    lines.append(f"- **Tokens**: {usage.get('input_tokens', 0)} in / {usage.get('output_tokens', 0)} out")
            else:
                lines.append(f"### Attempt {attempt} (PASS, {duration:.1f}s)")
                lines.append(f"- **Model**: {model}")
                lines.append(f"- **Prompt**: {prompt_type}")
                if usage:
                    lines.append(f"- **Tokens**: {usage.get('input_tokens', 0)} in / {usage.get('output_tokens', 0)} out")

            lines.append("")

        # Cost estimate
        lines.append(f"**Total**: {len(history)} attempts, ~{total_input + total_output:,} tokens")
        lines.append("")
        lines.append("---")
        lines.append("")

        # Append to log file
        _ensure_log_file()
        with open(PROMPT_LOG_PATH, "a", encoding="utf-8") as f:
            f.write("\n".join(lines))

        logger.info(f"프롬프트 로그 기록: {PROMPT_LOG_PATH}")

    except Exception as e:
        logger.warning(f"프롬프트 로그 기록 실패 (무시): {e}")


def _ensure_log_file() -> None:
    """Create PROMPT_LOG.md if it doesn't exist."""
    if not PROMPT_LOG_PATH.exists():
        PROMPT_LOG_PATH.write_text(
            "# RALPH Prompt Iteration Log\n\n"
            "프롬프트 이터레이션과 검증 결과를 기록합니다.\n\n"
            "---\n",
            encoding="utf-8",
        )
