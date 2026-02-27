"""
RALPH v2 레이아웃 분석기.

PyMuPDF get_text("dict") + get_drawings() + find_tables()를 사용하여
문서의 레이아웃을 분석하고 의미적 영역(Zone)으로 분류.
"""
from __future__ import annotations

import re
from collections import Counter

import fitz

from .models import (
    BBox, TextSpan, TextLine, TextBlock, DocumentZone, ZoneType,
    LayoutPage, LayoutResult, FontStats, Drawing, DrawingType,
    ImageInfo, TableInfo,
)


class LayoutAnalyzer:
    """PDF 문서 레이아웃 분석기."""

    # 존 분류 기준값
    HEADER_RATIO = 0.12         # 페이지 상단 12% = 헤더 후보
    FOOTER_RATIO = 0.10         # 페이지 하단 10% = 푸터 후보
    TITLE_SIZE_MULTIPLIER = 1.3 # body 대비 1.3x 이상 = 제목
    FOOTNOTE_SIZE_MULTIPLIER = 0.85
    LINE_Y_TOLERANCE = 3.0      # Y좌표 이 이내면 같은 라인
    BLOCK_GAP_THRESHOLD = 15.0  # 라인 간 이 이상 간격 = 다른 블록

    # 한국 문서 KV 패턴
    KV_LABEL_PATTERN = re.compile(
        r"^(.{1,20})\s*[:：]\s*$|"       # "라벨 :" (콜론으로 끝남)
        r"^(.{1,20})\s*[:：]\s*(.+)$|"   # "라벨 : 값" (같은 스팬)
        r"^(등록번호|상\s*호|법인명|대표자?|개업|소재지|업\s*태|종\s*목|세무서)",
    )

    def analyze(self, pdf_path: str) -> LayoutResult:
        """전체 문서 레이아웃 분석."""
        doc = fitz.open(pdf_path)
        try:
            # 1단계: 모든 페이지의 텍스트 스팬 수집 → 전역 폰트 통계
            all_spans_meta = []
            for page in doc:
                page_dict = page.get_text("dict")
                for block in page_dict.get("blocks", []):
                    if block.get("type") != 0:
                        continue
                    for line in block.get("lines", []):
                        for span in line.get("spans", []):
                            text = span["text"].strip()
                            if text:
                                all_spans_meta.append(round(span["size"], 1))

            font_stats = self._compute_font_stats(all_spans_meta)

            # 2단계: 페이지별 분석
            pages = []
            total_drawings = 0
            total_images = 0
            total_tables = 0
            has_charts = False
            has_raster_images = False

            for page_num, page in enumerate(doc):
                layout_page = self._analyze_page(page, page_num, font_stats)
                pages.append(layout_page)
                total_drawings += len(layout_page.drawings)
                total_images += len(layout_page.images)
                total_tables += len(layout_page.tables)
                if layout_page.images:
                    has_raster_images = True

            total_text_blocks = sum(len(p.text_blocks) for p in pages)

            return LayoutResult(
                pages=pages,
                font_stats=font_stats,
                total_text_blocks=total_text_blocks,
                total_drawings=total_drawings,
                total_images=total_images,
                total_tables=total_tables,
                source_path=pdf_path,
                has_charts=has_charts,
                has_raster_images=has_raster_images,
            )
        finally:
            doc.close()

    def _analyze_page(
        self, page: fitz.Page, page_num: int, font_stats: FontStats
    ) -> LayoutPage:
        """단일 페이지 레이아웃 분석."""
        page_dict = page.get_text("dict")
        page_width = page_dict["width"]
        page_height = page_dict["height"]

        # 1) 텍스트 스팬 추출
        raw_spans = self._extract_spans(page_dict)

        # 2) 스팬 → 라인 그룹핑
        lines = self._group_spans_into_lines(raw_spans)

        # 3) 라인 → 블록 그룹핑
        text_blocks = self._group_lines_into_blocks(lines)

        # 4) 드로잉 추출
        drawings = self._extract_drawings(page)

        # 5) 이미지 추출
        images = self._extract_images(page, page_num)

        # 6) 테이블 추출
        tables = self._extract_tables(page, page_num)

        # 7) 존 분류
        zones = self._classify_zones(
            text_blocks, drawings, images, tables,
            page_width, page_height, page_num, font_stats,
        )

        return LayoutPage(
            page_num=page_num,
            width=page_width,
            height=page_height,
            text_blocks=text_blocks,
            zones=zones,
            drawings=drawings,
            images=images,
            tables=tables,
        )

    def _extract_spans(self, page_dict: dict) -> list[TextSpan]:
        """get_text("dict") → TextSpan 리스트."""
        spans = []
        for block in page_dict.get("blocks", []):
            if block.get("type") != 0:
                continue
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    text = span["text"]
                    if not text.strip():
                        continue
                    spans.append(TextSpan(
                        text=text,
                        bbox=BBox.from_tuple(span["bbox"]),
                        font_name=span.get("font", ""),
                        font_size=span.get("size", 0.0),
                        font_flags=span.get("flags", 0),
                        color=span.get("color", 0),
                    ))
        return spans

    def _group_spans_into_lines(self, spans: list[TextSpan]) -> list[TextLine]:
        """Y좌표 근접성으로 스팬을 라인으로 그룹핑."""
        if not spans:
            return []

        # Y 좌표로 정렬
        sorted_spans = sorted(spans, key=lambda s: (s.bbox.y0, s.bbox.x0))

        lines: list[TextLine] = []
        current_line_spans: list[TextSpan] = [sorted_spans[0]]

        for span in sorted_spans[1:]:
            # 현재 라인의 Y 범위와 비교
            last_span = current_line_spans[-1]
            if abs(span.bbox.y0 - last_span.bbox.y0) <= self.LINE_Y_TOLERANCE:
                current_line_spans.append(span)
            else:
                # 새 라인 시작
                lines.append(self._make_text_line(current_line_spans))
                current_line_spans = [span]

        if current_line_spans:
            lines.append(self._make_text_line(current_line_spans))

        return lines

    def _make_text_line(self, spans: list[TextSpan]) -> TextLine:
        """스팬 리스트 → TextLine (X 정렬)."""
        spans = sorted(spans, key=lambda s: s.bbox.x0)
        bbox = BBox(
            x0=min(s.bbox.x0 for s in spans),
            y0=min(s.bbox.y0 for s in spans),
            x1=max(s.bbox.x1 for s in spans),
            y1=max(s.bbox.y1 for s in spans),
        )
        return TextLine(spans=spans, bbox=bbox)

    def _group_lines_into_blocks(self, lines: list[TextLine]) -> list[TextBlock]:
        """공간 근접성으로 라인을 블록으로 그룹핑."""
        if not lines:
            return []

        blocks: list[TextBlock] = []
        current_block_lines: list[TextLine] = [lines[0]]

        for line in lines[1:]:
            prev_line = current_block_lines[-1]
            gap = line.bbox.y0 - prev_line.bbox.y1

            # X 범위가 크게 다르면 다른 블록 (다단 감지)
            x_overlap = (min(line.bbox.x1, prev_line.bbox.x1) -
                         max(line.bbox.x0, prev_line.bbox.x0))
            x_overlap_ratio = x_overlap / max(
                1, min(line.bbox.width, prev_line.bbox.width)
            )

            if gap > self.BLOCK_GAP_THRESHOLD or x_overlap_ratio < 0.3:
                blocks.append(self._make_text_block(current_block_lines, len(blocks)))
                current_block_lines = [line]
            else:
                current_block_lines.append(line)

        if current_block_lines:
            blocks.append(self._make_text_block(current_block_lines, len(blocks)))

        return blocks

    def _make_text_block(self, lines: list[TextLine], block_num: int) -> TextBlock:
        bbox = BBox(
            x0=min(l.bbox.x0 for l in lines),
            y0=min(l.bbox.y0 for l in lines),
            x1=max(l.bbox.x1 for l in lines),
            y1=max(l.bbox.y1 for l in lines),
        )
        return TextBlock(lines=lines, bbox=bbox, block_num=block_num)

    def _extract_drawings(self, page: fitz.Page) -> list[Drawing]:
        """get_drawings() → Drawing 리스트."""
        drawings = []
        for d in page.get_drawings():
            bbox = BBox.from_tuple(d["rect"])
            items = d.get("items", [])

            # 유형 분류
            dtype = DrawingType.UNKNOWN
            if len(items) == 1:
                op = items[0][0]
                if op == "re":
                    dtype = (DrawingType.RECT_FILLED
                             if d.get("fill") else DrawingType.RECT)
                elif op == "l":
                    dtype = DrawingType.LINE
                elif op == "c":
                    dtype = DrawingType.CURVE
            elif len(items) > 1:
                ops = set(item[0] for item in items)
                if ops == {"l"} or ops <= {"l", "m"}:
                    dtype = DrawingType.LINE
                elif "c" in ops:
                    dtype = DrawingType.CURVE

            drawings.append(Drawing(
                drawing_type=dtype,
                bbox=bbox,
                color=d.get("color"),
                fill=d.get("fill"),
                width=d.get("width", 0),
                items=items,
            ))
        return drawings

    def _extract_images(self, page: fitz.Page, page_num: int) -> list[ImageInfo]:
        """페이지 내 래스터 이미지 추출."""
        images = []
        for img in page.get_images(full=True):
            xref = img[0]
            try:
                rects = page.get_image_rects(xref)
                if rects:
                    rect = rects[0]
                    images.append(ImageInfo(
                        bbox=BBox.from_tuple(rect),
                        xref=xref,
                        width=img[2],
                        height=img[3],
                        colorspace=img[5] if len(img) > 5 else "",
                        page_num=page_num,
                    ))
            except Exception:
                continue
        return images

    def _extract_tables(self, page: fitz.Page, page_num: int) -> list[TableInfo]:
        """find_tables() → TableInfo 리스트."""
        tables = []
        try:
            result = page.find_tables()
            if result and result.tables:
                for t in result.tables:
                    cells = t.extract()
                    tables.append(TableInfo(
                        bbox=BBox.from_tuple(t.bbox),
                        row_count=t.row_count,
                        col_count=t.col_count,
                        cells=cells,
                        page_num=page_num,
                    ))
        except Exception:
            pass
        return tables

    def _classify_zones(
        self,
        text_blocks: list[TextBlock],
        drawings: list[Drawing],
        images: list[ImageInfo],
        tables: list[TableInfo],
        page_width: float,
        page_height: float,
        page_num: int,
        font_stats: FontStats,
    ) -> list[DocumentZone]:
        """텍스트 블록을 의미적 영역으로 분류."""
        zones: list[DocumentZone] = []
        classified_blocks: set[int] = set()

        header_y = page_height * self.HEADER_RATIO
        footer_y = page_height * (1 - self.FOOTER_RATIO)

        # 1) 테이블 영역 존 등록 (테이블 내부 블록은 건너뜀)
        for table in tables:
            table_zone = DocumentZone(
                zone_type=ZoneType.TABLE,
                bbox=table.bbox,
                page_num=page_num,
                confidence=0.95,
                metadata={
                    "row_count": table.row_count,
                    "col_count": table.col_count,
                },
            )
            zones.append(table_zone)

            # 테이블 영역 내 텍스트 블록은 분류에서 제외
            for i, block in enumerate(text_blocks):
                if table.bbox.contains(block.bbox, tolerance=5.0):
                    classified_blocks.add(i)

        # 2) 이미지 영역 존 등록
        for img in images:
            # 페이지 전체를 덮는 배경 이미지는 제외
            if (img.bbox.width > page_width * 0.9 and
                    img.bbox.height > page_height * 0.7):
                continue
            zones.append(DocumentZone(
                zone_type=ZoneType.IMAGE,
                bbox=img.bbox,
                page_num=page_num,
                confidence=0.9,
                metadata={"xref": img.xref, "size": f"{img.width}x{img.height}"},
            ))

        # 3) 텍스트 블록 분류
        for i, block in enumerate(text_blocks):
            if i in classified_blocks:
                continue

            zone_type = self._classify_text_block(
                block, header_y, footer_y, page_width, page_height, font_stats
            )

            zone = DocumentZone(
                zone_type=zone_type,
                bbox=block.bbox,
                page_num=page_num,
                blocks=[block],
                confidence=0.8,
            )
            zones.append(zone)

        # 4) Y좌표 순으로 정렬
        zones.sort(key=lambda z: (z.bbox.y0, z.bbox.x0))

        return zones

    def _classify_text_block(
        self,
        block: TextBlock,
        header_y: float,
        footer_y: float,
        page_width: float,
        page_height: float,
        font_stats: FontStats,
    ) -> ZoneType:
        """개별 텍스트 블록의 존 유형 결정."""
        text = block.stripped_text
        font_size = block.dominant_font_size
        center_y = block.bbox.center_y
        center_x = block.bbox.center_x

        # 페이지 번호: 하단 + 짧은 숫자
        if center_y > footer_y and len(text) < 10:
            stripped = re.sub(r"[^\d/()]", "", text)
            if stripped and re.match(r"^\(?\d+[/]?\d*\)?$", stripped):
                return ZoneType.PAGE_NUMBER

        # 푸터: 하단 + 작은 폰트 + 긴 텍스트 (면책 조항 등)
        if center_y > footer_y and font_size <= font_stats.footnote_threshold:
            return ZoneType.FOOTER

        # 제목: 큰 폰트 + 중앙 정렬 + 짧은 텍스트
        if font_size >= font_stats.heading_threshold:
            # 페이지 중앙에 가까운지 확인
            x_center_ratio = center_x / page_width
            if 0.25 < x_center_ratio < 0.75 and len(text) < 50:
                return ZoneType.TITLE

        # Key-Value 패턴: 콜론으로 구분된 라벨:값
        if self._is_kv_block(block):
            return ZoneType.KEY_VALUE

        # 헤더: 상단 위치
        if center_y < header_y and font_size <= font_stats.body_size * 1.1:
            return ZoneType.HEADER

        return ZoneType.BODY_TEXT

    def _is_kv_block(self, block: TextBlock) -> bool:
        """블록이 Key-Value 패턴인지 판단."""
        for line in block.lines:
            text = line.stripped_text
            # 콜론 패턴
            if re.search(r"[:：]", text):
                # 콜론 앞에 한국어 라벨이 있는지
                match = re.match(r"^(.{1,20})\s*[:：]", text)
                if match:
                    label = match.group(1).strip()
                    # 일반적인 한국 공문서 라벨 키워드
                    if any(kw in label for kw in [
                        "번호", "명", "자", "일", "지", "태", "목",
                        "호", "서", "사업", "대표", "등록", "소재",
                        "법인", "상호", "개업", "발급",
                    ]):
                        return True
            # 스팬 수가 2개 이상이고, 콜론이 있는 경우
            if len(line.spans) >= 2:
                for span in line.spans:
                    if span.text.strip() in (":", "："):
                        return True
        return False

    def _compute_font_stats(self, sizes: list[float]) -> FontStats:
        """폰트 크기 분포 → 통계."""
        if not sizes:
            return FontStats(
                body_size=12.0,
                heading_threshold=15.6,
                footnote_threshold=10.2,
                size_distribution={},
            )

        counter = Counter(sizes)
        body_size = counter.most_common(1)[0][0]

        return FontStats(
            body_size=body_size,
            heading_threshold=body_size * self.TITLE_SIZE_MULTIPLIER,
            footnote_threshold=body_size * self.FOOTNOTE_SIZE_MULTIPLIER,
            size_distribution=dict(counter),
        )
