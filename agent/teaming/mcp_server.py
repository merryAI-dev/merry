"""
Human-AI Teaming MCP Server
Claude Agent SDK 패턴을 활용한 Teaming 도구 정의
"""

from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
import uuid
import json


# ========================================
# 데이터 타입 정의
# ========================================

class CheckpointStatus(str, Enum):
    """Checkpoint 상태"""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    MODIFIED = "modified"
    AUTO_APPROVED = "auto_approved"


@dataclass
class Checkpoint:
    """
    Teaming Checkpoint

    Level 2: pre_execution (실행 전 승인 필요)
    Level 3: post_execution (실행 후 검토 필요)
    """
    checkpoint_id: str
    tool_name: str
    automation_level: int
    checkpoint_type: str  # "pre_execution" | "post_execution"
    input_data: Dict[str, Any]
    output_data: Optional[Dict[str, Any]] = None
    ai_rationale: str = ""
    confidence_score: float = 0.0
    risk_indicators: List[str] = field(default_factory=list)
    status: CheckpointStatus = CheckpointStatus.PENDING
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    resolved_at: Optional[str] = None
    human_comment: Optional[str] = None
    human_modifications: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리 변환"""
        result = asdict(self)
        result["status"] = self.status.value
        return result

    def to_summary(self) -> Dict[str, Any]:
        """UI 표시용 요약"""
        return {
            "checkpoint_id": self.checkpoint_id,
            "tool_name": self.tool_name,
            "level": self.automation_level,
            "type": self.checkpoint_type,
            "confidence": f"{self.confidence_score:.0%}",
            "status": self.status.value,
            "risks": self.risk_indicators,
            "created_at": self.created_at,
        }


@dataclass
class AuditEntry:
    """감사 로그 항목"""
    entry_id: str
    timestamp: str
    event_type: str
    tool_name: str
    automation_level: int
    checkpoint_id: Optional[str] = None
    decision: Optional[str] = None
    responsibility: str = "ai"  # "ai" | "human" | "shared"
    confidence_score: Optional[float] = None
    details: Optional[Dict[str, Any]] = None


# ========================================
# Checkpoint Store (세션별 저장소)
# ========================================

class CheckpointStore:
    """세션별 Checkpoint 저장소"""

    def __init__(self, session_id: str = "default"):
        self.session_id = session_id
        self._checkpoints: Dict[str, Checkpoint] = {}
        self._audit_log: List[AuditEntry] = []

    def create(self, checkpoint: Checkpoint) -> str:
        """Checkpoint 생성"""
        self._checkpoints[checkpoint.checkpoint_id] = checkpoint
        self._log_event("checkpoint_created", checkpoint)
        return checkpoint.checkpoint_id

    def get(self, checkpoint_id: str) -> Optional[Checkpoint]:
        """Checkpoint 조회"""
        return self._checkpoints.get(checkpoint_id)

    def get_pending(self) -> List[Checkpoint]:
        """대기 중인 Checkpoint 목록"""
        return [
            cp for cp in self._checkpoints.values()
            if cp.status == CheckpointStatus.PENDING
        ]

    def get_all(self) -> List[Checkpoint]:
        """모든 Checkpoint 목록"""
        return list(self._checkpoints.values())

    def resolve(
        self,
        checkpoint_id: str,
        status: CheckpointStatus,
        comment: str = None,
        modifications: Dict[str, Any] = None
    ) -> Optional[Checkpoint]:
        """Checkpoint 해결 (승인/거부/수정)"""
        cp = self._checkpoints.get(checkpoint_id)
        if not cp:
            return None

        cp.status = status
        cp.resolved_at = datetime.now().isoformat()
        cp.human_comment = comment
        cp.human_modifications = modifications

        self._log_event(f"checkpoint_{status.value}", cp)
        return cp

    def _log_event(self, event_type: str, checkpoint: Checkpoint):
        """감사 로그 기록"""
        # 책임 주체 결정
        if event_type == "checkpoint_created":
            responsibility = "ai"
        elif event_type.startswith("checkpoint_") and event_type != "checkpoint_created":
            if checkpoint.status == CheckpointStatus.AUTO_APPROVED:
                responsibility = "ai"
            else:
                responsibility = "human"
        else:
            responsibility = "shared"

        entry = AuditEntry(
            entry_id=f"audit_{uuid.uuid4().hex[:12]}",
            timestamp=datetime.now().isoformat(),
            event_type=event_type,
            tool_name=checkpoint.tool_name,
            automation_level=checkpoint.automation_level,
            checkpoint_id=checkpoint.checkpoint_id,
            decision=checkpoint.status.value if checkpoint.status != CheckpointStatus.PENDING else None,
            responsibility=responsibility,
            confidence_score=checkpoint.confidence_score,
        )
        self._audit_log.append(entry)

    def get_audit_log(self, limit: int = 50) -> List[Dict[str, Any]]:
        """감사 로그 조회"""
        return [asdict(e) for e in self._audit_log[-limit:]]

    def get_statistics(self) -> Dict[str, Any]:
        """통계 조회"""
        checkpoints = list(self._checkpoints.values())
        total = len(checkpoints)

        if total == 0:
            return {
                "total": 0,
                "by_status": {},
                "by_level": {},
                "avg_confidence": 0.0,
            }

        by_status = {}
        by_level = {}
        confidence_sum = 0.0

        for cp in checkpoints:
            # 상태별 집계
            status = cp.status.value
            by_status[status] = by_status.get(status, 0) + 1

            # 레벨별 집계
            level = f"level_{cp.automation_level}"
            by_level[level] = by_level.get(level, 0) + 1

            # 신뢰도 합계
            confidence_sum += cp.confidence_score

        return {
            "total": total,
            "by_status": by_status,
            "by_level": by_level,
            "avg_confidence": round(confidence_sum / total, 2),
        }


# 전역 스토어 관리
_stores: Dict[str, CheckpointStore] = {}


def get_store(session_id: str = "default") -> CheckpointStore:
    """세션별 스토어 조회 (없으면 생성)"""
    if session_id not in _stores:
        _stores[session_id] = CheckpointStore(session_id)
    return _stores[session_id]


def clear_store(session_id: str = "default") -> bool:
    """스토어 초기화"""
    if session_id in _stores:
        del _stores[session_id]
        return True
    return False


# ========================================
# MCP 도구 정의 (SDK 스타일)
# ========================================

def tool(name: str, description: str, input_schema: Dict):
    """SDK 스타일 도구 데코레이터"""
    def decorator(func):
        func._mcp_tool = {
            "name": name,
            "description": description,
            "inputSchema": {
                "type": "object",
                "properties": input_schema,
                "required": [k for k, v in input_schema.items() if not v.get("optional")]
            }
        }
        return func
    return decorator


@tool(
    "get_pending_checkpoints",
    "보류 중인 모든 checkpoint 목록을 조회합니다",
    {
        "session_id": {
            "type": "string",
            "description": "세션 ID (기본값: default)",
            "optional": True
        }
    }
)
async def get_pending_checkpoints(args: Dict[str, Any]) -> Dict[str, Any]:
    """보류 중인 checkpoint 목록 조회"""
    session_id = args.get("session_id", "default")
    store = get_store(session_id)
    pending = store.get_pending()

    return {
        "content": [{
            "type": "text",
            "text": json.dumps({
                "success": True,
                "checkpoints": [cp.to_summary() for cp in pending],
                "count": len(pending)
            }, ensure_ascii=False, indent=2)
        }]
    }


@tool(
    "approve_checkpoint",
    "Checkpoint를 승인하여 도구 실행을 계속합니다",
    {
        "checkpoint_id": {
            "type": "string",
            "description": "승인할 Checkpoint ID"
        },
        "comment": {
            "type": "string",
            "description": "승인 코멘트 (선택)",
            "optional": True
        },
        "modifications": {
            "type": "object",
            "description": "입력값 수정 (선택)",
            "optional": True
        },
        "session_id": {
            "type": "string",
            "description": "세션 ID",
            "optional": True
        }
    }
)
async def approve_checkpoint(args: Dict[str, Any]) -> Dict[str, Any]:
    """Checkpoint 승인"""
    session_id = args.get("session_id", "default")
    store = get_store(session_id)

    checkpoint_id = args.get("checkpoint_id")
    comment = args.get("comment")
    modifications = args.get("modifications")

    status = CheckpointStatus.MODIFIED if modifications else CheckpointStatus.APPROVED
    checkpoint = store.resolve(checkpoint_id, status, comment, modifications)

    if not checkpoint:
        return {
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "success": False,
                    "error": f"Checkpoint를 찾을 수 없습니다: {checkpoint_id}"
                }, ensure_ascii=False)
            }],
            "isError": True
        }

    return {
        "content": [{
            "type": "text",
            "text": json.dumps({
                "success": True,
                "checkpoint_id": checkpoint_id,
                "status": status.value,
                "message": "Checkpoint가 승인되었습니다. 실행을 계속합니다.",
                "modifications": modifications
            }, ensure_ascii=False)
        }]
    }


@tool(
    "reject_checkpoint",
    "Checkpoint를 거부하여 도구 실행을 취소합니다",
    {
        "checkpoint_id": {
            "type": "string",
            "description": "거부할 Checkpoint ID"
        },
        "reason": {
            "type": "string",
            "description": "거부 사유"
        },
        "session_id": {
            "type": "string",
            "description": "세션 ID",
            "optional": True
        }
    }
)
async def reject_checkpoint(args: Dict[str, Any]) -> Dict[str, Any]:
    """Checkpoint 거부"""
    session_id = args.get("session_id", "default")
    store = get_store(session_id)

    checkpoint_id = args.get("checkpoint_id")
    reason = args.get("reason", "사유 없음")

    checkpoint = store.resolve(checkpoint_id, CheckpointStatus.REJECTED, reason)

    if not checkpoint:
        return {
            "content": [{
                "type": "text",
                "text": json.dumps({
                    "success": False,
                    "error": f"Checkpoint를 찾을 수 없습니다: {checkpoint_id}"
                }, ensure_ascii=False)
            }],
            "isError": True
        }

    return {
        "content": [{
            "type": "text",
            "text": json.dumps({
                "success": True,
                "checkpoint_id": checkpoint_id,
                "status": "rejected",
                "message": f"Checkpoint가 거부되었습니다: {reason}"
            }, ensure_ascii=False)
        }]
    }


@tool(
    "get_audit_log",
    "Teaming 결정 및 도구 실행의 감사 로그를 조회합니다",
    {
        "limit": {
            "type": "integer",
            "description": "최대 항목 수 (기본값: 50)",
            "optional": True
        },
        "session_id": {
            "type": "string",
            "description": "세션 ID",
            "optional": True
        }
    }
)
async def get_audit_log(args: Dict[str, Any]) -> Dict[str, Any]:
    """감사 로그 조회"""
    session_id = args.get("session_id", "default")
    store = get_store(session_id)
    limit = args.get("limit", 50)

    logs = store.get_audit_log(limit)
    stats = store.get_statistics()

    # 책임 주체별 집계
    by_responsibility = {"ai": 0, "human": 0, "shared": 0}
    for log in logs:
        resp = log.get("responsibility", "ai")
        by_responsibility[resp] = by_responsibility.get(resp, 0) + 1

    return {
        "content": [{
            "type": "text",
            "text": json.dumps({
                "success": True,
                "logs": logs,
                "total": len(logs),
                "statistics": stats,
                "summary": {
                    "by_responsibility": by_responsibility
                }
            }, ensure_ascii=False, indent=2)
        }]
    }


@tool(
    "get_tool_level",
    "특정 도구의 자동화 레벨을 조회합니다",
    {
        "tool_name": {
            "type": "string",
            "description": "도구 이름"
        }
    }
)
async def get_tool_level(args: Dict[str, Any]) -> Dict[str, Any]:
    """도구 자동화 레벨 조회"""
    from .level_config import (
        TOOL_LEVELS,
        LEVEL_DESCRIPTIONS,
        LEVEL_NAMES_KO,
        AutomationLevel,
        get_tool_level as _get_tool_level
    )

    tool_name = args.get("tool_name")
    level = _get_tool_level(tool_name)

    return {
        "content": [{
            "type": "text",
            "text": json.dumps({
                "success": True,
                "tool_name": tool_name,
                "automation_level": level.value,
                "level_name": level.name,
                "level_name_ko": LEVEL_NAMES_KO.get(level, "알 수 없음"),
                "description": LEVEL_DESCRIPTIONS.get(level, "")
            }, ensure_ascii=False)
        }]
    }


@tool(
    "get_teaming_status",
    "현재 세션의 Teaming 상태 요약을 조회합니다",
    {
        "session_id": {
            "type": "string",
            "description": "세션 ID",
            "optional": True
        }
    }
)
async def get_teaming_status(args: Dict[str, Any]) -> Dict[str, Any]:
    """Teaming 상태 요약"""
    session_id = args.get("session_id", "default")
    store = get_store(session_id)

    pending = store.get_pending()
    stats = store.get_statistics()

    return {
        "content": [{
            "type": "text",
            "text": json.dumps({
                "success": True,
                "session_id": session_id,
                "pending_count": len(pending),
                "pending_checkpoints": [cp.to_summary() for cp in pending],
                "statistics": stats
            }, ensure_ascii=False, indent=2)
        }]
    }


# ========================================
# MCP 서버 생성
# ========================================

TEAMING_TOOLS = [
    get_pending_checkpoints,
    approve_checkpoint,
    reject_checkpoint,
    get_audit_log,
    get_tool_level,
    get_teaming_status,
]


def create_teaming_mcp_server() -> Dict[str, Any]:
    """
    Teaming MCP 서버 생성 (SDK 패턴)

    도구 이름 형식: mcp__teaming__<tool_name>
    """
    return {
        "name": "teaming",
        "version": "1.0.0",
        "description": "Human-AI Teaming Framework",
        "tools": [func._mcp_tool for func in TEAMING_TOOLS],
        "handlers": {func._mcp_tool["name"]: func for func in TEAMING_TOOLS}
    }
