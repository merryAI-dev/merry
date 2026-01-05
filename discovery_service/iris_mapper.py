"""
IRIS+ Mapper

정책 테마를 IRIS+ 임팩트 메트릭에 매핑합니다.
"""

import json
import os
import re
from typing import Dict, Any, List, Optional
from pathlib import Path
from dotenv import load_dotenv

# 프로젝트 루트의 .env 파일 로드 (절대 경로 사용)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")


class IRISMapper:
    """
    IRIS+ 임팩트 메트릭 매퍼

    정책 테마와 산업을 IRIS+ 메트릭에 매핑하고 SDG 연계를 제공합니다.
    """

    def __init__(self, catalog_path: str = None):
        """
        IRISMapper 초기화

        Args:
            catalog_path: IRIS+ 카탈로그 JSON 경로 (없으면 기본 경로 사용)
        """
        if catalog_path is None:
            catalog_path = Path(__file__).parent.parent / "data" / "iris_plus_catalog.json"

        self.catalog = self._load_catalog(catalog_path)
        self._build_indexes()

    def _load_catalog(self, path: str) -> Dict[str, Any]:
        """카탈로그 로드"""
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"IRIS+ 카탈로그를 찾을 수 없습니다: {path}")

        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _build_indexes(self):
        """검색을 위한 인덱스 구축"""
        self.metrics_by_code = {}
        self.metrics_by_keyword = {}
        self.metrics_by_sdg = {}

        # 카테고리 순회
        for category in self.catalog.get("categories", []):
            for subcategory in category.get("subcategories", []):
                for metric in subcategory.get("metrics", []):
                    code = metric["code"]

                    # 코드별 인덱스
                    self.metrics_by_code[code] = {
                        **metric,
                        "category": category["id"],
                        "category_name": category["name_kr"],
                        "subcategory": subcategory["id"],
                        "subcategory_name": subcategory["name_kr"]
                    }

                    # 키워드별 인덱스
                    for keyword in metric.get("keywords_kr", []):
                        keyword_lower = keyword.lower()
                        if keyword_lower not in self.metrics_by_keyword:
                            self.metrics_by_keyword[keyword_lower] = []
                        self.metrics_by_keyword[keyword_lower].append(code)

                    # SDG별 인덱스
                    for sdg in metric.get("sdgs", []):
                        if sdg not in self.metrics_by_sdg:
                            self.metrics_by_sdg[sdg] = []
                        self.metrics_by_sdg[sdg].append(code)

        # 정책 테마 매핑 로드
        self.policy_theme_mapping = self.catalog.get("policy_theme_mapping", {})

        # SDG 정보 로드
        self.sdg_info = self.catalog.get("sdg_info", {})

    def search_metrics(
        self,
        query: str,
        category: str = None,
        sdg_filter: List[int] = None,
        top_k: int = 10
    ) -> Dict[str, Any]:
        """
        IRIS+ 카탈로그에서 메트릭 검색

        Args:
            query: 검색 키워드
            category: 카테고리 필터 (environmental, social, governance)
            sdg_filter: SDG 번호 필터
            top_k: 반환할 최대 결과 수

        Returns:
            {
                "success": bool,
                "query": str,
                "results": [
                    {
                        "code": "OI8590",
                        "name": "GHG Emissions Reduced",
                        "name_kr": "온실가스 감축량",
                        "category": "environmental",
                        "sdgs": [13],
                        "relevance_score": 0.95
                    }
                ],
                "total_found": int
            }
        """
        results = []
        query_lower = query.lower()
        query_words = set(query_lower.split())

        # 모든 메트릭 검색
        for code, metric in self.metrics_by_code.items():
            # 카테고리 필터
            if category and metric["category"] != category:
                continue

            # SDG 필터
            if sdg_filter:
                if not any(sdg in metric.get("sdgs", []) for sdg in sdg_filter):
                    continue

            # 관련도 점수 계산
            score = self._calculate_relevance(query_lower, query_words, metric)

            if score > 0:
                results.append({
                    "code": code,
                    "name": metric["name"],
                    "name_kr": metric["name_kr"],
                    "description": metric.get("description", ""),
                    "category": metric["category"],
                    "category_name": metric["category_name"],
                    "subcategory_name": metric["subcategory_name"],
                    "unit": metric.get("unit", ""),
                    "sdgs": metric.get("sdgs", []),
                    "relevance_score": score
                })

        # 점수순 정렬
        results.sort(key=lambda x: x["relevance_score"], reverse=True)

        return {
            "success": True,
            "query": query,
            "results": results[:top_k],
            "total_found": len(results)
        }

    def _calculate_relevance(
        self,
        query_lower: str,
        query_words: set,
        metric: Dict[str, Any]
    ) -> float:
        """관련도 점수 계산"""
        score = 0.0

        # 이름 매칭
        name_lower = metric["name"].lower()
        name_kr = metric.get("name_kr", "").lower()

        if query_lower in name_lower or query_lower in name_kr:
            score += 1.0

        # 키워드 매칭
        for keyword in metric.get("keywords_kr", []):
            keyword_lower = keyword.lower()
            if query_lower in keyword_lower:
                score += 0.8
            elif any(word in keyword_lower for word in query_words):
                score += 0.4

        # 설명 매칭
        description = metric.get("description", "").lower()
        if query_lower in description:
            score += 0.3
        elif any(word in description for word in query_words):
            score += 0.1

        return min(score, 1.0)  # 최대 1.0

    def map_themes_to_iris(
        self,
        themes: List[str],
        industries: List[str] = None,
        min_score: float = 0.3
    ) -> Dict[str, Any]:
        """
        정책 테마를 IRIS+ 메트릭에 매핑

        Args:
            themes: 정책 테마 리스트
            industries: 타겟 산업 리스트 (추가 매핑용)
            min_score: 최소 관련도 점수

        Returns:
            {
                "success": bool,
                "mappings": [
                    {
                        "theme": "탄소중립",
                        "iris_metrics": [
                            {
                                "code": "OI8590",
                                "name_kr": "온실가스 감축량",
                                "relevance": 0.95,
                                "sdgs": [13]
                            }
                        ],
                        "sdg_alignment": [7, 13],
                        "description": "설명"
                    }
                ],
                "aggregate_sdgs": [7, 13, ...],
                "aggregate_metrics": [...]
            }
        """
        mappings = []
        all_sdgs = set()
        all_metrics = set()

        # 테마별 매핑
        for theme in themes:
            theme_mapping = self._map_single_theme(theme)
            if theme_mapping:
                mappings.append(theme_mapping)
                all_sdgs.update(theme_mapping.get("sdg_alignment", []))
                for m in theme_mapping.get("iris_metrics", []):
                    all_metrics.add(m["code"])

        # 산업별 추가 매핑
        if industries:
            for industry in industries:
                industry_mapping = self._map_industry(industry, min_score)
                if industry_mapping:
                    mappings.append(industry_mapping)
                    all_sdgs.update(industry_mapping.get("sdg_alignment", []))
                    for m in industry_mapping.get("iris_metrics", []):
                        all_metrics.add(m["code"])

        return {
            "success": True,
            "mappings": mappings,
            "aggregate_sdgs": sorted(list(all_sdgs)),
            "aggregate_metrics": list(all_metrics),
            "sdg_details": self._get_sdg_details(list(all_sdgs))
        }

    def _map_single_theme(self, theme: str) -> Optional[Dict[str, Any]]:
        """단일 테마 매핑"""
        # 정책 테마 매핑 테이블에서 먼저 검색
        if theme in self.policy_theme_mapping:
            mapping_info = self.policy_theme_mapping[theme]
            iris_codes = mapping_info.get("iris_codes", [])
            sdgs = mapping_info.get("sdgs", [])

            metrics = []
            for code in iris_codes:
                if code in self.metrics_by_code:
                    metric = self.metrics_by_code[code]
                    metrics.append({
                        "code": code,
                        "name": metric["name"],
                        "name_kr": metric["name_kr"],
                        "category": metric["category_name"],
                        "relevance": 1.0,  # 직접 매핑
                        "sdgs": metric.get("sdgs", [])
                    })

            return {
                "source": "theme",
                "theme": theme,
                "iris_metrics": metrics,
                "sdg_alignment": sdgs,
                "description": mapping_info.get("description", "")
            }

        # 키워드 검색으로 폴백
        search_result = self.search_metrics(theme, top_k=5)
        if search_result.get("results"):
            metrics = []
            sdgs = set()

            for result in search_result["results"]:
                metrics.append({
                    "code": result["code"],
                    "name": result["name"],
                    "name_kr": result["name_kr"],
                    "category": result["category_name"],
                    "relevance": result["relevance_score"],
                    "sdgs": result["sdgs"]
                })
                sdgs.update(result["sdgs"])

            return {
                "source": "theme",
                "theme": theme,
                "iris_metrics": metrics,
                "sdg_alignment": sorted(list(sdgs)),
                "description": f"'{theme}' 키워드 기반 매핑"
            }

        return None

    def _map_industry(self, industry: str, min_score: float) -> Optional[Dict[str, Any]]:
        """산업 매핑"""
        search_result = self.search_metrics(industry, top_k=5)
        if not search_result.get("results"):
            return None

        metrics = []
        sdgs = set()

        for result in search_result["results"]:
            if result["relevance_score"] >= min_score:
                metrics.append({
                    "code": result["code"],
                    "name": result["name"],
                    "name_kr": result["name_kr"],
                    "category": result["category_name"],
                    "relevance": result["relevance_score"],
                    "sdgs": result["sdgs"]
                })
                sdgs.update(result["sdgs"])

        if not metrics:
            return None

        return {
            "source": "industry",
            "theme": industry,
            "iris_metrics": metrics,
            "sdg_alignment": sorted(list(sdgs)),
            "description": f"'{industry}' 산업 관련 임팩트 메트릭"
        }

    def _get_sdg_details(self, sdg_numbers: List[int]) -> List[Dict[str, Any]]:
        """SDG 상세 정보 반환"""
        details = []
        for num in sdg_numbers:
            str_num = str(num)
            if str_num in self.sdg_info:
                info = self.sdg_info[str_num]
                details.append({
                    "number": num,
                    "name": info["name"],
                    "name_kr": info["name_kr"]
                })
        return details

    def get_metric_by_code(self, code: str) -> Optional[Dict[str, Any]]:
        """코드로 메트릭 조회"""
        return self.metrics_by_code.get(code)

    def get_metrics_by_sdg(self, sdg_number: int) -> List[Dict[str, Any]]:
        """SDG 번호로 관련 메트릭 조회"""
        codes = self.metrics_by_sdg.get(sdg_number, [])
        return [self.metrics_by_code[code] for code in codes if code in self.metrics_by_code]

    def get_all_categories(self) -> List[Dict[str, Any]]:
        """모든 카테고리 목록 반환"""
        return [
            {
                "id": cat["id"],
                "name": cat["name"],
                "name_kr": cat["name_kr"],
                "subcategories": [
                    {
                        "id": sub["id"],
                        "name": sub["name"],
                        "name_kr": sub["name_kr"],
                        "metric_count": len(sub.get("metrics", []))
                    }
                    for sub in cat.get("subcategories", [])
                ]
            }
            for cat in self.catalog.get("categories", [])
        ]
