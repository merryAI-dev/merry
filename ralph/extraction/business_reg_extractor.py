"""
사업자등록증 전용 추출기.

규칙 기반 KV 패턴 매칭으로 API 호출 없이 모든 필드 추출.
"""
from __future__ import annotations

import re

from ralph.layout.models import LayoutResult, ZoneType
from ralph.utils.korean_text import (
    normalize_text, normalize_date,
    normalize_business_number, normalize_corp_reg_number,
)
from .base import BaseExtractor


class BusinessRegExtractor(BaseExtractor):
    """사업자등록증 추출기 — 0 API 호출."""

    @property
    def doc_type(self) -> str:
        return "business_reg"

    # 필드별 정규식 패턴 (순서: 우선순위 높은 것부터)
    FIELD_PATTERNS: dict[str, list[re.Pattern]] = {
        "business_number": [
            re.compile(r"등록\s*번호\s*[:：]?\s*(\d{3}[-‐]\d{2}[-‐]\d{5})"),
            re.compile(r"사업자\s*등록\s*번호\s*[:：]?\s*(\d{3}[-‐]\d{2}[-‐]\d{5})"),
            re.compile(r"(\d{3}[-‐]\d{2}[-‐]\d{5})"),
        ],
        "corp_name": [
            re.compile(r"(?:법인명|상\s*호)\s*(?:\(단체명\))?\s*[:：]\s*(.+?)(?:\s{2,}|$)", re.MULTILINE),
            re.compile(r"법인명\s*(?:\(단체명\))?\s*[:：]?\s*(.+?)(?:\s{2,}|\n)", re.MULTILINE),
        ],
        "representative": [
            re.compile(r"대\s*표\s*자\s*[:：]\s*(.+?)(?:\s{2,}|$)", re.MULTILINE),
            re.compile(r"성\s*명\s*(?:\(대표자\))?\s*[:：]\s*(.+?)(?:\s{2,}|$)", re.MULTILINE),
        ],
        "corp_reg_number": [
            re.compile(r"법인등록번호\s*[:：]?\s*(\d{6}[-‐]\d{7})"),
        ],
        "registration_date": [
            re.compile(r"(?:사업자\s*)?등록\s*(?:연월)?일\s*[:：]?\s*(.+?)(?:\s{2,}|$)", re.MULTILINE),
        ],
        "opening_date": [
            re.compile(r"개업\s*(?:연월)?일\s*[:：]?\s*(.+?)(?:\s{2,}|$)", re.MULTILINE),
        ],
        "address": [
            re.compile(r"사업장\s*소재지\s*[:：]\s*(.+?)(?:\n본점|$)", re.DOTALL),
        ],
        "head_office_address": [
            re.compile(r"본점\s*소재지\s*[:：]\s*(.+?)(?:\n사업|$)", re.DOTALL),
        ],
        "tax_office": [
            re.compile(r"(.+?)세무서장"),
        ],
    }

    # 업태/종목은 별도 처리 (다중 행)
    BUSINESS_TYPE_PATTERN = re.compile(r"업\s*태")
    BUSINESS_ITEM_PATTERN = re.compile(r"종\s*목")

    def extract(self, layout: LayoutResult) -> tuple[dict, float]:
        """레이아웃에서 사업자등록증 필드 추출."""
        result: dict = {}
        found_fields = 0
        total_fields = 9  # 필수+선택 필드 총 수

        # 전체 텍스트 수집 (페이지별)
        full_text = layout.full_text
        full_text_normalized = normalize_text(full_text)

        # KV 존 텍스트 우선 수집
        kv_text_parts = []
        for zone in layout.all_zones(ZoneType.KEY_VALUE):
            kv_text_parts.append(normalize_text(zone.text))

        # 제목 존에서 세무서 정보 추출
        for zone in layout.all_zones(ZoneType.TITLE):
            text = zone.text.strip()
            if "세무서" in text:
                m = re.match(r"(.+세무서)", text)
                if m:
                    result["tax_office"] = m.group(1).strip()
                    found_fields += 1

        # KV 텍스트 + 전체 텍스트에서 패턴 매칭
        search_texts = kv_text_parts + [full_text_normalized]

        for field_name, patterns in self.FIELD_PATTERNS.items():
            if field_name in result:
                continue
            for search_text in search_texts:
                matched = False
                for pattern in patterns:
                    m = pattern.search(search_text)
                    if m:
                        raw_value = m.group(1).strip()
                        processed = self._process_field(field_name, raw_value)
                        if processed:
                            result[field_name] = processed
                            found_fields += 1
                            matched = True
                            break
                if matched:
                    break

        # 업태/종목 추출 (스팬 좌표 기반)
        biz_type, biz_item = self._extract_business_type_item(layout)
        if biz_type:
            result["business_type"] = biz_type
            found_fields += 1
        if biz_item:
            result["business_item"] = biz_item
            found_fields += 1

        # registration_date가 없으면 opening_date로 대체
        if "registration_date" not in result and "opening_date" in result:
            result["registration_date"] = result["opening_date"]
            found_fields += 1

        confidence = min(1.0, found_fields / total_fields)
        return result, confidence

    def _process_field(self, field_name: str, raw: str) -> str | None:
        """필드별 후처리."""
        raw = raw.strip()
        if not raw:
            return None

        if field_name == "business_number":
            return normalize_business_number(raw) or raw

        if field_name == "corp_reg_number":
            return normalize_corp_reg_number(raw) or raw

        if field_name in ("registration_date", "opening_date"):
            return normalize_date(raw) or raw

        if field_name in ("address", "head_office_address"):
            # 개행 제거, 연속 공백 정리
            raw = re.sub(r"\s+", "", raw)
            return raw

        if field_name == "corp_name":
            # 공백 제거된 법인명
            return re.sub(r"\s+", "", raw)

        return raw

    def _extract_business_type_item(
        self, layout: LayoutResult
    ) -> tuple[str | None, str | None]:
        """업태/종목은 다중 행이므로 좌표 기반 추출.

        사업자등록증 레이아웃:
        - 업태/종목이 행 단위로 쌍을 이룸 (같은 Y좌표)
        - 같은 업태가 여러 종목에 반복됨 → deduplicate 필요
        - 한 셀이 여러 줄에 걸칠 수 있음 → Y 근접 스팬 머지
        """
        for page in layout.pages:
            all_spans = []
            for block in page.text_blocks:
                for line in block.lines:
                    for span in line.spans:
                        all_spans.append(span)

            # "업태"와 "종목" 라벨 찾기
            type_label = None
            item_label = None
            for span in all_spans:
                text = span.text.strip()
                if text == "업태" or re.match(r"업\s*태$", text):
                    type_label = span
                elif text == "종목" or re.match(r"종\s*목$", text):
                    item_label = span

            if not type_label and not item_label:
                continue

            # 섹션 Y 범위 결정
            y_start = min(
                s.bbox.y0 for s in [type_label, item_label] if s
            ) - 5
            y_end = page.height * 0.8
            for span in all_spans:
                if any(kw in span.text for kw in ["발급", "사업자단위"]):
                    if span.bbox.y0 > y_start + 20:
                        y_end = min(y_end, span.bbox.y0)
                        break

            if not (type_label and item_label):
                continue

            type_x_start = type_label.bbox.x1 + 5
            type_x_end = item_label.bbox.x0 - 5
            item_x_start = item_label.bbox.x1 + 5

            # 열별로 스팬 수집 (Y 정렬)
            type_spans = []
            item_spans = []

            for span in all_spans:
                if span.bbox.y0 < y_start or span.bbox.y0 > y_end:
                    continue
                text = span.text.strip()
                if not text or text in ("업태", "종목", ":", "："):
                    continue
                if re.match(r"^사업의", text) or "(별지출력)" in text:
                    continue

                cx = span.bbox.center_x
                if type_x_start <= cx <= type_x_end:
                    type_spans.append(span)
                elif cx >= item_x_start:
                    item_spans.append(span)

            # Y좌표 근접 스팬 머지 (줄바꿈된 셀 결합)
            type_values = self._merge_spans_by_y(type_spans)
            item_values = self._merge_spans_by_y(item_spans)

            # 업태 deduplicate (순서 유지)
            type_unique = list(dict.fromkeys(type_values))

            biz_type = ", ".join(type_unique) if type_unique else None
            biz_item = ", ".join(item_values) if item_values else None

            return biz_type, biz_item

        return None, None

    @staticmethod
    def _merge_spans_by_y(
        spans: list, y_tolerance: float = 12.0
    ) -> list[str]:
        """Y좌표가 근접한 스팬들을 하나의 값으로 머지.

        예: y=391 "사업시설관리, 사업지원및임대서" + y=400 "비스업"
        → "사업시설관리·사업지원및임대서비스업"
        """
        if not spans:
            return []

        sorted_spans = sorted(spans, key=lambda s: (s.bbox.y0, s.bbox.x0))
        groups: list[list] = [[sorted_spans[0]]]

        for span in sorted_spans[1:]:
            # 그룹의 첫 스팬 Y와 비교 (체인 확장 방지)
            group_start_y = groups[-1][0].bbox.y0
            if abs(span.bbox.y0 - group_start_y) <= y_tolerance:
                groups[-1].append(span)
            else:
                groups.append([span])

        values = []
        for group in groups:
            # 같은 그룹 내 스팬 텍스트 결합
            texts = [s.text.strip() for s in group if s.text.strip()]
            merged = "".join(texts)
            # 내부 쉼표를 중점(·)으로 변환 (같은 셀 내 구분)
            merged = merged.replace(", ", "·").replace(",", "·")
            if merged:
                values.append(merged)

        return values
