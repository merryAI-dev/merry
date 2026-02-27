"""
RALPH v2 레이아웃 분석 데이터 모델.

PyMuPDF get_text("dict") 출력을 구조화된 레이아웃 객체로 변환.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class ZoneType(Enum):
    """문서 내 의미적 영역 유형."""
    HEADER = "header"           # 문서 상단 헤더 (발급기관, 문서번호)
    TITLE = "title"             # 문서 제목
    KEY_VALUE = "key_value"     # 라벨:값 형식 필드
    TABLE = "table"             # 테이블 영역
    BODY_TEXT = "body_text"     # 일반 본문
    FOOTER = "footer"           # 하단 푸터
    PAGE_NUMBER = "page_number" # 페이지 번호
    STAMP = "stamp"             # 직인/도장
    IMAGE = "image"             # 래스터 이미지
    CHART = "chart"             # 차트 영역
    WATERMARK = "watermark"     # 워터마크


class DrawingType(Enum):
    """벡터 드로잉 유형."""
    LINE = "line"
    RECT = "rect"
    RECT_FILLED = "rect_filled"
    CURVE = "curve"
    TABLE_BORDER = "table_border"
    CHART_ELEMENT = "chart_element"
    UNKNOWN = "unknown"


@dataclass
class BBox:
    """바운딩 박스 (PDF 좌표계, 72 DPI)."""
    x0: float
    y0: float
    x1: float
    y1: float

    @property
    def width(self) -> float:
        return self.x1 - self.x0

    @property
    def height(self) -> float:
        return self.y1 - self.y0

    @property
    def center_x(self) -> float:
        return (self.x0 + self.x1) / 2

    @property
    def center_y(self) -> float:
        return (self.y0 + self.y1) / 2

    @property
    def area(self) -> float:
        return max(0, self.width) * max(0, self.height)

    def overlap(self, other: BBox) -> BBox | None:
        """두 bbox의 교집합. 겹치지 않으면 None."""
        x0 = max(self.x0, other.x0)
        y0 = max(self.y0, other.y0)
        x1 = min(self.x1, other.x1)
        y1 = min(self.y1, other.y1)
        if x0 < x1 and y0 < y1:
            return BBox(x0, y0, x1, y1)
        return None

    def overlap_ratio(self, other: BBox) -> float:
        """교집합 면적 / 자신의 면적."""
        inter = self.overlap(other)
        if inter is None or self.area == 0:
            return 0.0
        return inter.area / self.area

    def contains(self, other: BBox, tolerance: float = 2.0) -> bool:
        """other가 self 안에 포함되는지 (tolerance 허용)."""
        return (self.x0 - tolerance <= other.x0 and
                self.y0 - tolerance <= other.y0 and
                self.x1 + tolerance >= other.x1 and
                self.y1 + tolerance >= other.y1)

    def y_overlaps(self, other: BBox, tolerance: float = 3.0) -> bool:
        """Y축으로 겹치는지 (같은 라인 여부 판단)."""
        return (self.y0 - tolerance < other.y1 and
                self.y1 + tolerance > other.y0)

    def distance_to(self, other: BBox) -> float:
        """두 bbox 간 최소 거리."""
        dx = max(0, max(self.x0 - other.x1, other.x0 - self.x1))
        dy = max(0, max(self.y0 - other.y1, other.y0 - self.y1))
        return (dx**2 + dy**2) ** 0.5

    def expand(self, margin: float) -> BBox:
        return BBox(self.x0 - margin, self.y0 - margin,
                    self.x1 + margin, self.y1 + margin)

    @classmethod
    def from_tuple(cls, t: tuple | list) -> BBox:
        return cls(t[0], t[1], t[2], t[3])

    def to_tuple(self) -> tuple[float, float, float, float]:
        return (self.x0, self.y0, self.x1, self.y1)


@dataclass
class TextSpan:
    """개별 텍스트 스팬 (폰트/좌표 메타데이터 포함)."""
    text: str
    bbox: BBox
    font_name: str
    font_size: float
    font_flags: int     # PyMuPDF flags (bit 4 = bold, bit 1 = italic)
    color: int          # RGB as integer

    @property
    def is_bold(self) -> bool:
        return bool(self.font_flags & (1 << 4))

    @property
    def is_italic(self) -> bool:
        return bool(self.font_flags & (1 << 1))

    @property
    def is_empty(self) -> bool:
        return not self.text.strip()


@dataclass
class TextLine:
    """텍스트 라인 (여러 스팬으로 구성)."""
    spans: list[TextSpan]
    bbox: BBox

    @property
    def text(self) -> str:
        return "".join(s.text for s in self.spans)

    @property
    def stripped_text(self) -> str:
        return self.text.strip()

    @property
    def dominant_font_size(self) -> float:
        """가장 많은 텍스트를 차지하는 폰트 크기."""
        if not self.spans:
            return 0.0
        size_lengths: dict[float, int] = {}
        for s in self.spans:
            rounded = round(s.font_size, 1)
            size_lengths[rounded] = size_lengths.get(rounded, 0) + len(s.text)
        return max(size_lengths, key=size_lengths.get)

    @property
    def is_bold(self) -> bool:
        """라인의 과반수 텍스트가 볼드인지."""
        bold_len = sum(len(s.text) for s in self.spans if s.is_bold)
        total_len = sum(len(s.text) for s in self.spans)
        return bold_len > total_len / 2 if total_len > 0 else False


@dataclass
class TextBlock:
    """텍스트 블록 (여러 라인으로 구성)."""
    lines: list[TextLine]
    bbox: BBox
    block_num: int = 0

    @property
    def text(self) -> str:
        return "\n".join(line.text for line in self.lines)

    @property
    def stripped_text(self) -> str:
        return self.text.strip()

    @property
    def dominant_font_size(self) -> float:
        if not self.lines:
            return 0.0
        sizes = [line.dominant_font_size for line in self.lines]
        return max(set(sizes), key=sizes.count)

    @property
    def line_count(self) -> int:
        return len(self.lines)


@dataclass
class DocumentZone:
    """문서 내 의미적 영역."""
    zone_type: ZoneType
    bbox: BBox
    page_num: int
    blocks: list[TextBlock] = field(default_factory=list)
    confidence: float = 1.0
    metadata: dict = field(default_factory=dict)

    @property
    def text(self) -> str:
        return "\n".join(b.text for b in self.blocks)

    @property
    def lines(self) -> list[TextLine]:
        return [line for b in self.blocks for line in b.lines]


@dataclass
class Drawing:
    """벡터 드로잉 요소."""
    drawing_type: DrawingType
    bbox: BBox
    color: tuple[float, ...] | None = None
    fill: tuple[float, ...] | None = None
    width: float = 0.0
    items: list = field(default_factory=list)


@dataclass
class ImageInfo:
    """래스터 이미지 정보."""
    bbox: BBox
    xref: int
    width: int
    height: int
    colorspace: str
    page_num: int


@dataclass
class TableInfo:
    """PyMuPDF find_tables() 결과를 래핑."""
    bbox: BBox
    row_count: int
    col_count: int
    cells: list[list[str | None]]   # [row][col]
    header_row: int = 0             # 헤더로 추정되는 행 인덱스
    page_num: int = 0


@dataclass
class LayoutPage:
    """단일 페이지의 레이아웃 분석 결과."""
    page_num: int
    width: float
    height: float
    text_blocks: list[TextBlock]
    zones: list[DocumentZone]
    drawings: list[Drawing]
    images: list[ImageInfo]
    tables: list[TableInfo]

    @property
    def full_text(self) -> str:
        return "\n".join(b.text for b in self.text_blocks)

    def get_zones_by_type(self, zone_type: ZoneType) -> list[DocumentZone]:
        return [z for z in self.zones if z.zone_type == zone_type]


@dataclass
class FontStats:
    """페이지/문서 전체의 폰트 통계."""
    body_size: float            # 가장 빈번한 폰트 크기 (본문)
    heading_threshold: float    # 이 이상이면 제목
    footnote_threshold: float   # 이 이하이면 각주
    size_distribution: dict[float, int]  # {크기: 스팬 수}


@dataclass
class LayoutResult:
    """전체 문서의 레이아웃 분석 결과."""
    pages: list[LayoutPage]
    font_stats: FontStats
    total_text_blocks: int
    total_drawings: int
    total_images: int
    total_tables: int
    source_path: str = ""
    has_charts: bool = False
    has_raster_images: bool = False

    @property
    def full_text(self) -> str:
        return "\n\n".join(p.full_text for p in self.pages)

    @property
    def page_count(self) -> int:
        return len(self.pages)

    def all_zones(self, zone_type: ZoneType | None = None) -> list[DocumentZone]:
        zones = [z for p in self.pages for z in p.zones]
        if zone_type:
            zones = [z for z in zones if z.zone_type == zone_type]
        return zones

    def all_tables(self) -> list[TableInfo]:
        return [t for p in self.pages for t in p.tables]
