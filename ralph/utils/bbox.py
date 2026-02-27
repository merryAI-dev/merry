"""바운딩 박스 유틸리티 함수."""
from __future__ import annotations

from ralph.layout.models import BBox


def merge_bboxes(bboxes: list[BBox]) -> BBox:
    """여러 bbox를 감싸는 최소 bbox."""
    return BBox(
        x0=min(b.x0 for b in bboxes),
        y0=min(b.y0 for b in bboxes),
        x1=max(b.x1 for b in bboxes),
        y1=max(b.y1 for b in bboxes),
    )


def find_nearby_text(
    target: BBox,
    candidates: list,
    max_distance: float = 30.0,
    direction: str | None = None,
) -> list:
    """target bbox 근처의 텍스트 블록/라인 찾기.

    direction: "right", "below", "left", "above", None (전방향)
    """
    results = []
    for candidate in candidates:
        bbox = candidate.bbox if hasattr(candidate, "bbox") else candidate
        dist = target.distance_to(bbox)
        if dist > max_distance:
            continue

        if direction == "right" and bbox.x0 < target.x1 - 5:
            continue
        if direction == "below" and bbox.y0 < target.y1 - 5:
            continue
        if direction == "left" and bbox.x1 > target.x0 + 5:
            continue
        if direction == "above" and bbox.y1 > target.y0 + 5:
            continue

        results.append((candidate, dist))

    results.sort(key=lambda x: x[1])
    return [r[0] for r in results]
