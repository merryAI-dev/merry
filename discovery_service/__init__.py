"""
Discovery Service Package

AC(액셀러레이터) 스타트업 발굴 지원을 위한 서비스 모듈

Components:
- PolicyAnalyzer: 정부 정책 PDF/아티클 분석
- IRISMapper: IRIS+ 임팩트 메트릭 매핑
- IndustryRecommender: 유망 산업 추천 엔진
- HypothesisGenerator: 관심 분야 기반 가설 생성
"""

from .policy_analyzer import PolicyAnalyzer
from .iris_mapper import IRISMapper
from .industry_recommender import IndustryRecommender
from .hypothesis_generator import HypothesisGenerator

__all__ = [
    "PolicyAnalyzer",
    "IRISMapper",
    "IndustryRecommender",
    "HypothesisGenerator",
]

__version__ = "0.1.0"
