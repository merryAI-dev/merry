"""
기업명 정규화 모듈

특수문자, 괄호 형식 차이를 자동으로 매칭합니다.
"""

import re
from typing import List


def normalize_company_name(name: str) -> List[str]:
    """
    기업명을 여러 변형으로 정규화

    Args:
        name: 원본 기업명

    Returns:
        가능한 모든 변형 리스트

    Examples:
        >>> normalize_company_name("(주)요벨")
        ["㈜요벨", "(주)요벨", "주식회사요벨", "주식회사 요벨", "요벨"]
    """
    variants = [name]  # 원본 포함

    # 1. (주) ↔ ㈜ 변환
    if "(주)" in name:
        variants.append(name.replace("(주)", "㈜"))
        variants.append(name.replace("(주)", "주식회사"))
        variants.append(name.replace("(주)", "주식회사 "))
    elif "㈜" in name:
        variants.append(name.replace("㈜", "(주)"))
        variants.append(name.replace("㈜", "주식회사"))
        variants.append(name.replace("㈜", "주식회사 "))
    elif name.startswith("주식회사"):
        core = name.replace("주식회사", "").strip()
        variants.append(f"㈜{core}")
        variants.append(f"(주){core}")

    # 2. 회사 suffix 제거 (순수 이름만)
    for prefix in ["㈜", "(주)", "주식회사", "주식회사 ", "(사)", "㈜ "]:
        if name.startswith(prefix):
            core_name = name.replace(prefix, "", 1).strip()
            if core_name and core_name not in variants:
                variants.append(core_name)

    # 3. 공백 제거 버전
    for v in list(variants):
        no_space = v.replace(" ", "")
        if no_space != v and no_space not in variants:
            variants.append(no_space)

    # 4. 특수문자 제거
    for v in list(variants):
        cleaned = re.sub(r'[^\w가-힣]', '', v)
        if cleaned and cleaned not in variants:
            variants.append(cleaned)

    return list(set(variants))  # 중복 제거


def fuzzy_match_company(query: str, company_list: List[dict]) -> List[dict]:
    """
    기업명을 퍼지 매칭하여 검색

    Args:
        query: 사용자 검색어
        company_list: 기업 레코드 리스트 (각 dict에 '기업명' 키 필요)

    Returns:
        매칭된 기업 리스트
    """
    query_variants = normalize_company_name(query.strip())
    matched = []

    for company in company_list:
        company_name = company.get("기업명", "").strip()
        if not company_name:
            continue

        company_variants = normalize_company_name(company_name)

        # 정확히 일치
        for q_var in query_variants:
            for c_var in company_variants:
                if q_var == c_var:
                    if company not in matched:
                        matched.append(company)
                        break

        # 부분 일치 (핵심 이름 포함)
        if not matched or company not in matched:
            for q_var in query_variants:
                for c_var in company_variants:
                    if q_var in c_var or c_var in q_var:
                        if company not in matched:
                            matched.append(company)
                            break

    return matched


def get_company_search_variants(query: str) -> List[str]:
    """
    기업 검색용 변형 리스트 생성 (Airtable filters용)

    Args:
        query: 사용자 입력 기업명

    Returns:
        Airtable 필터에 사용할 변형 리스트

    Examples:
        >>> get_company_search_variants("(주)요벨")
        ["㈜요벨", "(주)요벨", "요벨"]
    """
    variants = normalize_company_name(query)

    # 너무 많으면 상위 5개만 (Airtable OR 제한)
    # 우선순위: 특수문자 버전 > 원본 > 순수 이름
    prioritized = []

    for v in variants:
        if v.startswith("㈜") or v.startswith("(주)"):
            prioritized.insert(0, v)  # 최우선
        elif v == query:
            prioritized.insert(1 if prioritized else 0, v)  # 원본
        else:
            prioritized.append(v)  # 나머지

    return prioritized[:5]  # 최대 5개
