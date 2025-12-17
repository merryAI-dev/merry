"""Tool definitions for VC Investment Agent"""

import os
import sys
import json
import re
import subprocess
import shlex
import time
from functools import wraps
from pathlib import Path
from typing import Any, Dict, List, Callable

from shared.logging_config import get_logger

logger = get_logger("tools")

# 프로젝트 루트를 Python 경로에 추가
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# ========================================
# 재시도 데코레이터 (외부 API 호출용)
# ========================================

def retry_with_backoff(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    exceptions: tuple = (Exception,)
) -> Callable:
    """
    지수 백오프 재시도 데코레이터

    Args:
        max_retries: 최대 재시도 횟수
        base_delay: 기본 대기 시간 (초)
        max_delay: 최대 대기 시간 (초)
        exceptions: 재시도할 예외 튜플
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt == max_retries - 1:
                        logger.error(f"{func.__name__} failed after {max_retries} attempts: {e}")
                        raise
                    delay = min(base_delay * (2 ** attempt), max_delay)
                    logger.warning(f"{func.__name__} retry {attempt + 1}/{max_retries} after {delay:.1f}s: {e}")
                    time.sleep(delay)
            raise last_exception
        return wrapper
    return decorator


# ========================================
# 입력 검증 헬퍼 함수
# ========================================

def _sanitize_filename(filename: str) -> str:
    """파일명에서 위험한 문자 제거"""
    if not filename:
        return "unnamed"
    # 허용: 알파벳, 숫자, 한글, 언더스코어, 하이픈, 점, 공백
    sanitized = re.sub(r'[^\w\s가-힣.\-]', '_', filename, flags=re.UNICODE)
    # 연속된 언더스코어 정리
    sanitized = re.sub(r'_+', '_', sanitized)
    return sanitized.strip('_') or "unnamed"


def _validate_file_path(file_path: str, allowed_extensions: List[str] = None, require_temp_dir: bool = True) -> tuple:
    """
    파일 경로 검증 (보안 강화)

    Args:
        file_path: 검증할 파일 경로
        allowed_extensions: 허용된 확장자 리스트
        require_temp_dir: temp 디렉토리 내부 경로만 허용 (기본: True)

    Returns: (is_valid: bool, error_message: str or None)
    """
    if not file_path:
        return False, "파일 경로가 비어있습니다"

    # Path traversal 공격 방어
    try:
        path = Path(file_path).resolve()
        # 상대 경로로 상위 디렉토리 접근 시도 감지
        if ".." in file_path:
            logger.warning(f"Path traversal attempt detected: {file_path}")
            return False, "잘못된 파일 경로입니다"
    except Exception:
        return False, "파일 경로를 해석할 수 없습니다"

    # temp 디렉토리 내부 경로만 허용 (업로드된 파일만 접근 가능)
    if require_temp_dir:
        # 허용된 디렉토리: temp/<user_id>/ 패턴
        temp_dir = (PROJECT_ROOT / "temp").resolve()
        try:
            # path가 temp_dir의 하위 경로인지 확인
            path.relative_to(temp_dir)
        except ValueError:
            logger.warning(f"Access to file outside temp directory blocked: {file_path}")
            return False, "허용되지 않은 경로입니다. 업로드된 파일만 접근할 수 있습니다."

    # 확장자 검증
    if allowed_extensions:
        ext = path.suffix.lower()
        if ext not in [e.lower() if e.startswith('.') else f'.{e.lower()}' for e in allowed_extensions]:
            return False, f"허용되지 않은 파일 형식입니다. 허용: {', '.join(allowed_extensions)}"

    return True, None


def _validate_numeric_param(value: Any, param_name: str, min_val: float = None, max_val: float = None) -> tuple:
    """
    숫자 파라미터 검증
    Returns: (is_valid: bool, validated_value: float or None, error_message: str or None)
    """
    try:
        num_value = float(value)
        if min_val is not None and num_value < min_val:
            return False, None, f"{param_name}은(는) {min_val} 이상이어야 합니다"
        if max_val is not None and num_value > max_val:
            return False, None, f"{param_name}은(는) {max_val} 이하여야 합니다"
        return True, num_value, None
    except (TypeError, ValueError):
        return False, None, f"{param_name}은(는) 유효한 숫자여야 합니다"


def register_tools() -> List[Dict[str, Any]]:
    """에이전트가 사용할 도구 등록"""

    return [
        {
            "name": "read_excel_as_text",
            "description": "엑셀 파일을 텍스트로 변환하여 읽습니다. 모든 시트의 내용을 텍스트 형식으로 반환하므로, 엑셀 구조가 다양해도 유연하게 대응할 수 있습니다. 이 도구로 먼저 엑셀 내용을 읽은 후, 필요한 정보를 파악하세요.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "excel_path": {
                        "type": "string",
                        "description": "읽을 엑셀 파일 경로"
                    },
                    "sheet_names": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "읽을 시트 이름 리스트 (선택사항, 없으면 모든 시트)"
                    },
                    "max_rows": {
                        "type": "integer",
                        "description": "각 시트에서 읽을 최대 행 수 (기본값: 50)"
                    }
                },
                "required": ["excel_path"]
            }
        },
        {
            "name": "analyze_excel",
            "description": "투자 검토 엑셀 파일을 자동으로 분석하여 투자조건, IS요약(연도별 당기순이익), Cap Table(총발행주식수)을 추출합니다. 일반적인 엑셀 구조에서 작동하지만, 구조가 특이하면 read_excel_as_text를 사용하세요.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "excel_path": {
                        "type": "string",
                        "description": "분석할 엑셀 파일 경로"
                    }
                },
                "required": ["excel_path"]
            }
        },
        {
            "name": "analyze_and_generate_projection",
            "description": "엑셀 파일을 분석하고 즉시 Exit 프로젝션을 생성합니다. 파일에서 투자 조건과 재무 데이터를 자동으로 추출한 후, 지정된 연도와 PER 배수로 Exit 시나리오를 계산하여 새로운 엑셀 파일을 생성합니다.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "excel_path": {
                        "type": "string",
                        "description": "분석할 투자검토 엑셀 파일 경로"
                    },
                    "target_year": {
                        "type": "integer",
                        "description": "Exit 목표 연도 (예: 2028, 2030)"
                    },
                    "per_multiples": {
                        "type": "array",
                        "items": {"type": "number"},
                        "description": "PER 배수 리스트 (예: [10, 20, 30])"
                    },
                    "company_name": {
                        "type": "string",
                        "description": "회사명 (선택사항)"
                    },
                    "output_filename": {
                        "type": "string",
                        "description": "출력 파일명 (선택사항, 기본값: exit_projection_YYYYMMDD_HHMMSS.xlsx)"
                    }
                },
                "required": ["excel_path", "target_year", "per_multiples"]
            }
        },
        {
            "name": "calculate_valuation",
            "description": "다양한 방법론으로 기업가치를 계산합니다 (PER, EV/Revenue, EV/EBITDA 등)",
            "input_schema": {
                "type": "object",
                "properties": {
                    "method": {
                        "type": "string",
                        "enum": ["per", "ev_revenue", "ev_ebitda"],
                        "description": "밸류에이션 방법론"
                    },
                    "base_value": {
                        "type": "number",
                        "description": "기준 값 (순이익, 매출, EBITDA 등)"
                    },
                    "multiple": {
                        "type": "number",
                        "description": "적용할 배수"
                    }
                },
                "required": ["method", "base_value", "multiple"]
            }
        },
        {
            "name": "calculate_dilution",
            "description": "SAFE 전환, 신규 투자 라운드 등으로 인한 지분 희석 효과를 계산합니다.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "event_type": {
                        "type": "string",
                        "enum": ["safe", "new_round", "call_option"],
                        "description": "희석 이벤트 종류"
                    },
                    "current_shares": {
                        "type": "number",
                        "description": "현재 총 발행주식수"
                    },
                    "event_details": {
                        "type": "object",
                        "description": "이벤트 상세 정보 (investment_amount, valuation_cap 등)"
                    }
                },
                "required": ["event_type", "current_shares", "event_details"]
            }
        },
        {
            "name": "calculate_irr",
            "description": "현금흐름 기반으로 IRR(내부수익률)과 멀티플을 계산합니다.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "cash_flows": {
                        "type": "array",
                        "description": "현금흐름 리스트 [{year: 2025, amount: -300000000}, {year: 2029, amount: 3150000000}]",
                        "items": {
                            "type": "object",
                            "properties": {
                                "year": {"type": "number"},
                                "amount": {"type": "number"}
                            }
                        }
                    }
                },
                "required": ["cash_flows"]
            }
        },
        {
            "name": "generate_exit_projection",
            "description": "Exit 프로젝션 엑셀 파일을 생성합니다 (basic/advanced/complete 중 선택)",
            "input_schema": {
                "type": "object",
                "properties": {
                    "projection_type": {
                        "type": "string",
                        "enum": ["basic", "advanced", "complete"],
                        "description": "프로젝션 타입 (basic: 기본, advanced: 부분매각+NPV, complete: SAFE+콜옵션)"
                    },
                    "parameters": {
                        "type": "object",
                        "description": "생성에 필요한 파라미터 (investment_amount, company_name, per_multiples 등)"
                    }
                },
                "required": ["projection_type", "parameters"]
            }
        },
        # ========================================
        # Peer PER 분석 도구
        # ========================================
        {
            "name": "read_pdf_as_text",
            "description": "PDF 파일(기업 소개서, IR 자료, 사업계획서 등)을 텍스트로 변환하여 읽습니다. 비즈니스 모델, 산업 분류, 핵심 사업을 파악하기 위해 사용합니다.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "pdf_path": {
                        "type": "string",
                        "description": "읽을 PDF 파일 경로"
                    },
                    "max_pages": {
                        "type": "integer",
                        "description": "읽을 최대 페이지 수 (기본값: 30)"
                    }
                },
                "required": ["pdf_path"]
            }
        },
        {
            "name": "get_stock_financials",
            "description": "yfinance를 사용하여 상장 기업의 재무 지표를 조회합니다. PER, PSR, 매출, 영업이익률, 시가총액 등을 반환합니다. 한국 주식은 티커 뒤에 .KS(KOSPI) 또는 .KQ(KOSDAQ)를 붙입니다.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "ticker": {
                        "type": "string",
                        "description": "주식 티커 심볼 (예: AAPL, MSFT, 005930.KS, 035720.KQ)"
                    }
                },
                "required": ["ticker"]
            }
        },
        {
            "name": "analyze_peer_per",
            "description": "여러 Peer 기업의 PER을 일괄 조회하고 비교 분석합니다. 평균, 중간값, 범위를 계산하여 적정 PER 배수를 제안합니다.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "tickers": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "비교할 기업 티커 리스트 (예: ['AAPL', 'MSFT', 'GOOGL'])"
                    },
                    "include_forward_per": {
                        "type": "boolean",
                        "description": "Forward PER 포함 여부 (기본값: true)"
                    }
                },
                "required": ["tickers"]
            }
        }
    ]


# === Tool Execution Functions ===

def execute_read_excel_as_text(
    excel_path: str,
    sheet_names: List[str] = None,
    max_rows: int = 50
) -> Dict[str, Any]:
    """엑셀 파일을 텍스트로 변환하여 읽기"""
    # 입력 검증: 파일 경로 (temp 디렉토리 내부만 허용)
    is_valid, error = _validate_file_path(excel_path, allowed_extensions=['.xlsx', '.xls'], require_temp_dir=True)
    if not is_valid:
        return {"success": False, "error": error}

    wb = None
    try:
        from openpyxl import load_workbook

        # 파일 존재 확인
        if not os.path.exists(excel_path):
            return {"success": False, "error": f"파일을 찾을 수 없습니다: {excel_path}"}

        wb = load_workbook(excel_path, data_only=True)

        sheets_data = {}
        target_sheets = sheet_names if sheet_names else wb.sheetnames

        for sheet_name in target_sheets:
            if sheet_name not in wb.sheetnames:
                continue

            ws = wb[sheet_name]
            sheet_text = []

            for row_idx, row in enumerate(ws.iter_rows(values_only=True), start=1):
                if row_idx > max_rows:
                    break

                # None이 아닌 값들만 필터링
                row_values = [str(cell) if cell is not None else "" for cell in row]

                # 빈 행 스킵
                if not any(val.strip() for val in row_values):
                    continue

                # 행 텍스트 생성
                row_text = " | ".join(row_values[:15])  # 처음 15개 컬럼만
                sheet_text.append(f"Row {row_idx}: {row_text}")

            sheets_data[sheet_name] = "\n".join(sheet_text)

        # 텍스트 결과 생성
        result_text = ""
        for sheet_name, content in sheets_data.items():
            result_text += f"\n{'='*60}\n"
            result_text += f"시트: {sheet_name}\n"
            result_text += f"{'='*60}\n"
            result_text += content + "\n"

        logger.info(f"Excel read successfully: {excel_path} ({len(sheets_data)} sheets)")
        return {
            "success": True,
            "file_path": excel_path,
            "sheets": list(sheets_data.keys()),
            "content": result_text,
            "total_sheets": len(sheets_data)
        }

    except FileNotFoundError:
        return {"success": False, "error": f"파일을 찾을 수 없습니다: {excel_path}"}
    except PermissionError:
        return {"success": False, "error": f"파일 접근 권한이 없습니다: {excel_path}"}
    except Exception as e:
        logger.error(f"Failed to read excel {excel_path}: {e}", exc_info=True)
        return {"success": False, "error": f"엑셀 파일 읽기 실패: {str(e)}"}
    finally:
        if wb is not None:
            wb.close()


def execute_analyze_excel(excel_path: str) -> Dict[str, Any]:
    """엑셀 파일 분석 실행 - openpyxl로 직접 읽기"""
    # 입력 검증: 파일 경로 (temp 디렉토리 내부만 허용)
    is_valid, error = _validate_file_path(excel_path, allowed_extensions=['.xlsx', '.xls'], require_temp_dir=True)
    if not is_valid:
        return {"success": False, "error": error}

    from openpyxl import load_workbook

    wb = None
    try:
        # 파일 존재 확인
        if not os.path.exists(excel_path):
            return {"success": False, "error": f"파일을 찾을 수 없습니다: {excel_path}"}

        # 엑셀 파일 열기
        wb = load_workbook(excel_path, data_only=True)

        result = {
            "success": True,
            "file_path": excel_path,
            "sheets": wb.sheetnames,
            "investment_terms": {},
            "income_statement": {},
            "cap_table": {}
        }

        # IS요약 시트에서 순이익 데이터 추출
        is_sheet = None
        for sheet_name in wb.sheetnames:
            if 'IS' in sheet_name or '손익' in sheet_name:
                is_sheet = wb[sheet_name]
                break

        if is_sheet:
            # 헤더 행 찾기 (구분, 2021년, 2022년... 형태)
            year_row_idx = None
            year_cols = {}

            for row_idx, row in enumerate(is_sheet.iter_rows(min_row=1, max_row=10), start=1):
                for col_idx, cell in enumerate(row):
                    if cell.value and isinstance(cell.value, str) and '년' in cell.value:
                        try:
                            year_val = int(cell.value.replace('년', '').replace(',', ''))
                            if 2020 <= year_val <= 2040:
                                year_row_idx = row_idx
                                year_cols[year_val] = col_idx
                        except ValueError:
                            pass

            # 당기순이익 행 찾기
            net_income_data = {}
            if year_cols:
                for row in is_sheet.iter_rows(min_row=year_row_idx if year_row_idx else 1):
                    first_cell = row[1].value if len(row) > 1 else None  # 2번째 컬럼 확인
                    if first_cell and '당기순이익' in str(first_cell):
                        for year, col_idx in year_cols.items():
                            if col_idx < len(row):
                                value = row[col_idx].value
                                if value and isinstance(value, (int, float)):
                                    net_income_data[year] = int(value)
                        break

            result["income_statement"] = {
                "years": sorted(year_cols.keys()) if year_cols else [],
                "net_income": net_income_data
            }

        # Cap Table에서 총 발행주식수 추출
        cap_sheet = None
        for sheet_name in wb.sheetnames:
            if 'cap' in sheet_name.lower() or '주주' in sheet_name:
                cap_sheet = wb[sheet_name]
                break

        if cap_sheet:
            # "합계" 행에서 주식수 찾기
            for row in cap_sheet.iter_rows():
                first_cell = row[0].value if row else None
                if first_cell and '합계' in str(first_cell):
                    # Incorporation 라운드의 주식수 (4번째 컬럼)
                    if len(row) > 3 and row[3].value and isinstance(row[3].value, (int, float)):
                        incorporation_shares = int(row[3].value)
                        # Seed 라운드 주식수 (7번째 컬럼)
                        seed_shares = 0
                        if len(row) > 6 and row[6].value and isinstance(row[6].value, (int, float)):
                            seed_shares = int(row[6].value)

                        total_shares = incorporation_shares + seed_shares
                        result["cap_table"]["total_shares"] = total_shares
                        result["cap_table"]["incorporation_shares"] = incorporation_shares
                        result["cap_table"]["seed_shares"] = seed_shares
                        break

        # 투자조건 시트에서 투자 정보 추출
        invest_sheet = None
        for sheet_name in wb.sheetnames:
            if '투자조건' in sheet_name:
                invest_sheet = wb[sheet_name]
                break

        if invest_sheet:
            for row_idx, row in enumerate(invest_sheet.iter_rows(min_row=1, max_row=30)):
                # 두 번째 컬럼이 주 정보 컬럼
                if len(row) < 4:
                    continue

                second_cell = row[1].value if row[1] else None
                if not second_cell:
                    continue

                second_val = str(second_cell)

                # 투자금액(원)
                if '투자금액' in second_val and '원' in second_val:
                    # 4번째 컬럼부터 찾기 (투자조건 열)
                    for cell in row[3:]:
                        if cell.value and isinstance(cell.value, (int, float)):
                            result["investment_terms"]["investment_amount"] = int(cell.value)
                            break

                # 투자단가(원)
                if '투자단가' in second_val and '원' in second_val:
                    for cell in row[3:]:
                        if cell.value and isinstance(cell.value, (int, float)):
                            result["investment_terms"]["price_per_share"] = int(cell.value)
                            break

                # 투자주식수
                if '투자주식수' in second_val:
                    for cell in row[3:]:
                        if cell.value and isinstance(cell.value, (int, float)):
                            result["investment_terms"]["shares"] = int(cell.value)
                            break

        logger.info(f"Excel analyzed successfully: {excel_path}")
        return result

    except FileNotFoundError:
        return {"success": False, "error": f"파일을 찾을 수 없습니다: {excel_path}"}
    except PermissionError:
        return {"success": False, "error": f"파일 접근 권한이 없습니다: {excel_path}"}
    except Exception as e:
        logger.error(f"Failed to analyze excel {excel_path}: {e}", exc_info=True)
        return {
            "success": False,
            "error": f"엑셀 파일 분석 실패: {str(e)}"
        }
    finally:
        if wb is not None:
            wb.close()


def execute_calculate_valuation(
    method: str,
    base_value: float,
    multiple: float
) -> Dict[str, Any]:
    """기업가치 계산 실행"""

    enterprise_value = base_value * multiple

    return {
        "success": True,
        "method": method,
        "base_value": base_value,
        "multiple": multiple,
        "enterprise_value": enterprise_value,
        "formatted": f"{enterprise_value:,.0f}원"
    }


def execute_calculate_dilution(
    event_type: str,
    current_shares: float,
    event_details: Dict[str, Any]
) -> Dict[str, Any]:
    """지분 희석 계산 실행"""

    if event_type == "safe":
        safe_amount = event_details.get("safe_amount")
        valuation_cap = event_details.get("valuation_cap")

        new_shares = (safe_amount / valuation_cap) * current_shares

    elif event_type == "new_round":
        investment = event_details.get("investment_amount")
        pre_money = event_details.get("pre_money_valuation")

        new_shares = (investment / pre_money) * current_shares

    elif event_type == "call_option":
        new_shares = 0  # 콜옵션은 희석 없음 (주식 매입)

    else:
        return {
            "success": False,
            "error": f"Unknown event type: {event_type}"
        }

    total_shares = current_shares + new_shares
    dilution_ratio = new_shares / total_shares if total_shares > 0 else 0

    return {
        "success": True,
        "event_type": event_type,
        "current_shares": current_shares,
        "new_shares": new_shares,
        "total_shares": total_shares,
        "dilution_ratio": dilution_ratio,
        "dilution_percentage": f"{dilution_ratio * 100:.2f}%"
    }


def execute_calculate_irr(cash_flows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """IRR 계산 실행"""

    if len(cash_flows) < 2:
        return {
            "success": False,
            "error": "최소 2개의 현금흐름이 필요합니다 (투자 + 회수)"
        }

    # 간단한 IRR 계산 (Newton's method)
    def npv(rate, cfs):
        return sum([
            cf["amount"] / ((1 + rate) ** (cf["year"] - cfs[0]["year"]))
            for cf in cfs
        ])

    # IRR 추정 (초기값 10%)
    rate = 0.1
    for _ in range(100):  # 최대 100번 반복
        npv_value = npv(rate, cash_flows)

        # NPV가 0에 가까우면 종료
        if abs(npv_value) < 1:
            break

        # Newton's method로 업데이트
        delta = 0.0001
        npv_delta = npv(rate + delta, cash_flows)
        derivative = (npv_delta - npv_value) / delta

        if abs(derivative) < 1e-10:
            break

        rate = rate - npv_value / derivative

    # 멀티플 계산
    initial_investment = abs(cash_flows[0]["amount"])
    total_return = sum([cf["amount"] for cf in cash_flows[1:]])
    multiple = total_return / initial_investment if initial_investment > 0 else 0

    # 투자기간
    holding_period = cash_flows[-1]["year"] - cash_flows[0]["year"]

    return {
        "success": True,
        "irr": rate,
        "irr_percentage": f"{rate * 100:.1f}%",
        "multiple": multiple,
        "multiple_formatted": f"{multiple:.2f}x",
        "holding_period": holding_period,
        "cash_flows": cash_flows
    }


def execute_generate_exit_projection(
    projection_type: str,
    parameters: Dict[str, Any]
) -> Dict[str, Any]:
    """Exit 프로젝션 엑셀 생성 실행"""

    # 스크립트 선택 (화이트리스트 방식)
    script_map = {
        "basic": "generate_exit_projection.py",
        "advanced": "generate_advanced_exit_projection.py",
        "complete": "generate_complete_exit_projection.py"
    }

    script_name = script_map.get(projection_type)
    if not script_name:
        return {
            "success": False,
            "error": f"Unknown projection type: {projection_type}. 허용: basic, advanced, complete"
        }

    script_path = PROJECT_ROOT / "scripts" / script_name

    # 허용된 파라미터 키 화이트리스트
    allowed_params = {
        "investment_amount", "price_per_share", "shares", "total_shares",
        "net_income_company", "net_income_reviewer", "target_year",
        "company_name", "per_multiples", "output",
        "net_income_2029", "net_income_2030", "partial_exit_ratio", "discount_rate",
        "total_shares_before_safe", "safe_amount", "safe_valuation_cap",
        "call_option_price_multiplier"
    }

    # 파라미터를 CLI 인자로 변환 (화이트리스트 검증)
    cmd = [sys.executable, str(script_path)]

    for key, value in parameters.items():
        # 허용되지 않은 파라미터 키 거부
        if key not in allowed_params:
            logger.warning(f"Rejected unknown parameter: {key}")
            continue

        # 파라미터 키 검증 (알파벳, 숫자, 언더스코어만 허용)
        if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', key):
            logger.warning(f"Invalid parameter key format: {key}")
            continue

        # 값 sanitize
        if key == "company_name":
            value = _sanitize_filename(str(value))
        elif key == "output":
            value = _sanitize_filename(str(value))
            if not value.endswith('.xlsx'):
                value += '.xlsx'

        cmd.append(f"--{key}")
        cmd.append(str(value))

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )

        # 출력 파일 경로 추출 (stdout에서)
        output_file = None
        for line in result.stdout.split('\n'):
            if '생성 완료' in line or 'xlsx' in line:
                # 파일 경로 추출
                parts = line.split(':')
                if len(parts) > 1:
                    output_file = parts[-1].strip()

        return {
            "success": True,
            "projection_type": projection_type,
            "output_file": output_file,
            "message": result.stdout
        }

    except subprocess.CalledProcessError as e:
        return {
            "success": False,
            "error": e.stderr
        }


def execute_analyze_and_generate_projection(
    excel_path: str,
    target_year: int,
    per_multiples: List[float],
    company_name: str = None,
    output_filename: str = None
) -> Dict[str, Any]:
    """엑셀 파일 분석 후 즉시 Exit 프로젝션 생성"""

    # 입력 검증: 파일 경로
    is_valid, error = _validate_file_path(excel_path, allowed_extensions=['.xlsx', '.xls'])
    if not is_valid:
        return {"success": False, "error": error}

    # 입력 검증: target_year
    is_valid, year_val, error = _validate_numeric_param(target_year, "target_year", min_val=2020, max_val=2050)
    if not is_valid:
        return {"success": False, "error": error}
    target_year = int(year_val)

    # 입력 검증: per_multiples
    if not per_multiples or not isinstance(per_multiples, list):
        return {"success": False, "error": "PER 멀티플 리스트가 필요합니다"}
    validated_multiples = []
    for m in per_multiples:
        is_valid, val, error = _validate_numeric_param(m, "PER multiple", min_val=0.1, max_val=1000)
        if not is_valid:
            return {"success": False, "error": error}
        validated_multiples.append(val)
    per_multiples = validated_multiples

    # 1단계: 엑셀 파일 분석
    analysis = execute_analyze_excel(excel_path)

    if not analysis["success"]:
        return analysis

    data = analysis
    income_statement = data.get("income_statement", {})
    net_income_data = income_statement.get("net_income", {})
    investment_terms = data.get("investment_terms", {})
    cap_table = data.get("cap_table", {})

    # 2단계: 필수 데이터 검증
    if target_year not in net_income_data:
        return {
            "success": False,
            "error": f"{target_year}년 순이익 데이터를 찾을 수 없습니다. 사용 가능한 연도: {list(net_income_data.keys())}"
        }

    net_income = net_income_data[target_year]
    investment_amount = investment_terms.get("investment_amount")
    price_per_share = investment_terms.get("price_per_share")
    shares = investment_terms.get("shares")
    total_shares = cap_table.get("total_shares")

    if not all([investment_amount, price_per_share, shares, total_shares]):
        return {
            "success": False,
            "error": "필수 투자 정보가 부족합니다",
            "found_data": {
                "investment_amount": investment_amount,
                "price_per_share": price_per_share,
                "shares": shares,
                "total_shares": total_shares
            }
        }

    # 3단계: Exit 프로젝션 요약 계산 (UI/리포트용)
    from datetime import datetime

    investment_year = datetime.now().year
    holding_period_years = target_year - investment_year

    projection_summary: List[Dict[str, Any]] = []
    for per in per_multiples:
        enterprise_value = float(net_income) * float(per)
        proceeds = None
        multiple = None
        irr_pct = None

        try:
            per_share_value = enterprise_value / float(total_shares)
            proceeds = per_share_value * float(shares)
            multiple = proceeds / float(investment_amount)
            if holding_period_years > 0 and multiple > 0:
                irr_pct = (multiple ** (1 / holding_period_years) - 1) * 100
        except Exception:
            pass

        projection_summary.append({
            "PER": float(per),
            "IRR": irr_pct,
            "Multiple": multiple
        })

    # 4단계: Exit 프로젝션 생성 (사용자별 temp 디렉토리에 저장)

    # excel_path에서 user_id 추출 (temp/<user_id>/파일명 형식)
    excel_path_obj = Path(excel_path)
    user_id = "cli_user"  # 기본값
    try:
        # temp/<user_id>/파일명 형식인지 확인
        if "temp" in excel_path_obj.parts:
            temp_idx = excel_path_obj.parts.index("temp")
            if len(excel_path_obj.parts) > temp_idx + 1:
                user_id = excel_path_obj.parts[temp_idx + 1]
    except (ValueError, IndexError):
        pass

    # 출력 파일명 생성
    if not output_filename:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_filename = f"exit_projection_{timestamp}.xlsx"
    else:
        # 출력 파일명 sanitize
        output_filename = _sanitize_filename(output_filename)
        if not output_filename.endswith('.xlsx'):
            output_filename += '.xlsx'

    # temp/<user_id>/ 디렉토리에 저장
    output_dir = PROJECT_ROOT / "temp" / user_id
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / output_filename

    if not company_name:
        company_name = _sanitize_filename(Path(excel_path).stem)
    else:
        # 회사명 sanitize
        company_name = _sanitize_filename(company_name)

    # generate_exit_projection.py 스크립트 호출
    script_path = PROJECT_ROOT / "scripts" / "generate_exit_projection.py"

    cmd = [
        sys.executable, str(script_path),
        "--investment_amount", str(int(investment_amount)),
        "--price_per_share", str(int(price_per_share)),
        "--shares", str(int(shares)),
        "--total_shares", str(int(total_shares)),
        "--net_income_company", str(int(net_income)),
        "--net_income_reviewer", str(int(net_income)),  # 같은 값 사용
        "--target_year", str(target_year),
        "--company_name", company_name,
        "--per_multiples", ",".join(map(lambda x: str(int(x) if x == int(x) else x), per_multiples)),
        "--output", str(output_path)
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
            cwd=str(PROJECT_ROOT)
        )

        return {
            "success": True,
            "output_file": str(output_path),
            "assumptions": {
                "company_name": company_name,
                "target_year": target_year,
                "investment_year": investment_year,
                "holding_period_years": holding_period_years,
                "investment_amount": investment_amount,
                "shares": shares,
                "total_shares": total_shares,
                "net_income": net_income,
                "per_multiples": per_multiples
            },
            "projection_summary": projection_summary,
            "analysis_data": {
                "target_year": target_year,
                "net_income": net_income,
                "investment_amount": investment_amount,
                "per_multiples": per_multiples,
                "company_name": company_name
            },
            "message": f"Exit 프로젝션 생성 완료: {output_path.name}"
        }

    except subprocess.CalledProcessError as e:
        return {
            "success": False,
            "error": f"Exit 프로젝션 생성 실패: {e.stderr}"
        }


# ========================================
# Peer PER 분석 도구 실행 함수
# ========================================

def execute_read_pdf_as_text(
    pdf_path: str,
    max_pages: int = 30
) -> Dict[str, Any]:
    """PDF 파일을 텍스트로 변환하여 읽기"""
    # 입력 검증: 파일 경로 (temp 디렉토리 내부만 허용)
    is_valid, error = _validate_file_path(pdf_path, allowed_extensions=['.pdf'], require_temp_dir=True)
    if not is_valid:
        return {"success": False, "error": error}

    import fitz  # PyMuPDF

    doc = None
    try:
        # 파일 존재 확인
        if not os.path.exists(pdf_path):
            return {"success": False, "error": f"파일을 찾을 수 없습니다: {pdf_path}"}

        doc = fitz.open(pdf_path)
        total_pages = len(doc)
        pages_to_read = min(total_pages, max_pages)

        text_content = []

        for page_num in range(pages_to_read):
            page = doc[page_num]
            text = page.get_text()

            if text.strip():
                text_content.append(f"\n{'='*60}")
                text_content.append(f"페이지 {page_num + 1}")
                text_content.append(f"{'='*60}")
                text_content.append(text)

        full_text = "\n".join(text_content)

        logger.info(f"PDF read successfully: {pdf_path} ({pages_to_read}/{total_pages} pages)")
        return {
            "success": True,
            "file_path": pdf_path,
            "total_pages": total_pages,
            "pages_read": pages_to_read,
            "content": full_text,
            "char_count": len(full_text)
        }

    except FileNotFoundError:
        return {"success": False, "error": f"파일을 찾을 수 없습니다: {pdf_path}"}
    except PermissionError:
        return {"success": False, "error": f"파일 접근 권한이 없습니다: {pdf_path}"}
    except Exception as e:
        logger.error(f"Failed to read PDF {pdf_path}: {e}", exc_info=True)
        return {
            "success": False,
            "error": f"PDF 파일 읽기 실패: {str(e)}"
        }
    finally:
        if doc is not None:
            doc.close()


def _fetch_stock_info(ticker: str) -> dict:
    """yfinance에서 주식 정보 조회 (Rate Limit 대응)"""
    import yfinance as yf
    import random

    # Rate Limit 방지를 위한 딜레이 (5~10초)
    delay = random.uniform(5.0, 10.0)
    logger.info(f"Waiting {delay:.1f}s before fetching {ticker}...")
    time.sleep(delay)

    max_retries = 3
    for attempt in range(max_retries):
        try:
            stock = yf.Ticker(ticker)
            info = stock.info

            # Rate Limit 응답 체크 (빈 dict 또는 에러 메시지)
            if not info or (isinstance(info, dict) and info.get("error")):
                if attempt < max_retries - 1:
                    # 재시도 시 30초 대기
                    retry_delay = 30 + random.uniform(0, 10)
                    logger.warning(f"Rate limit detected for {ticker}, retrying in {retry_delay:.1f}s (attempt {attempt+1}/{max_retries})...")
                    time.sleep(retry_delay)
                    continue
            return info

        except Exception as e:
            if attempt < max_retries - 1:
                # 에러 시 30초 대기
                retry_delay = 30 + random.uniform(0, 10)
                logger.warning(f"Error fetching {ticker}: {e}, retrying in {retry_delay:.1f}s (attempt {attempt+1}/{max_retries})...")
                time.sleep(retry_delay)
            else:
                raise

    return {}


def execute_get_stock_financials(ticker: str) -> Dict[str, Any]:
    """yfinance로 상장 기업 재무 지표 조회"""

    try:
        info = _fetch_stock_info(ticker)

        # 기본 정보가 없으면 에러
        if not info or info.get("regularMarketPrice") is None:
            return {
                "success": False,
                "error": f"티커 '{ticker}'를 찾을 수 없습니다. 티커 형식을 확인하세요. (미국: AAPL, 한국 KOSPI: 005930.KS, KOSDAQ: 035720.KQ)"
            }

        # 재무 지표 추출
        result = {
            "success": True,
            "ticker": ticker,
            "company_name": info.get("longName") or info.get("shortName", "N/A"),
            "sector": info.get("sector", "N/A"),
            "industry": info.get("industry", "N/A"),
            "country": info.get("country", "N/A"),
            "currency": info.get("currency", "USD"),

            # 시가총액
            "market_cap": info.get("marketCap"),
            "market_cap_formatted": _format_large_number(info.get("marketCap")),

            # 밸류에이션 지표
            "trailing_per": info.get("trailingPE"),
            "forward_per": info.get("forwardPE"),
            "psr": info.get("priceToSalesTrailing12Months"),
            "pbr": info.get("priceToBook"),
            "ev_ebitda": info.get("enterpriseToEbitda"),
            "ev_revenue": info.get("enterpriseToRevenue"),

            # 수익성 지표
            "revenue": info.get("totalRevenue"),
            "revenue_formatted": _format_large_number(info.get("totalRevenue")),
            "net_income": info.get("netIncomeToCommon"),
            "net_income_formatted": _format_large_number(info.get("netIncomeToCommon")),
            "operating_margin": info.get("operatingMargins"),
            "profit_margin": info.get("profitMargins"),
            "gross_margin": info.get("grossMargins"),

            # 성장률
            "revenue_growth": info.get("revenueGrowth"),
            "earnings_growth": info.get("earningsGrowth"),

            # 기타
            "current_price": info.get("regularMarketPrice"),
            "52_week_high": info.get("fiftyTwoWeekHigh"),
            "52_week_low": info.get("fiftyTwoWeekLow")
        }

        return result

    except ImportError:
        return {
            "success": False,
            "error": "yfinance가 설치되지 않았습니다. pip install yfinance를 실행하세요."
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"주식 정보 조회 실패: {str(e)}"
        }


def execute_analyze_peer_per(
    tickers: List[str],
    include_forward_per: bool = True
) -> Dict[str, Any]:
    """여러 Peer 기업 PER 일괄 조회 및 비교 분석"""

    try:
        import statistics

        peer_data = []
        failed_tickers = []
        total = len(tickers)

        logger.info(f"[Peer PER 분석] 총 {total}개 기업 조회 시작 (예상 소요: {total * 8}~{total * 12}초)")

        for idx, ticker in enumerate(tickers, 1):
            logger.info(f"[{idx}/{total}] {ticker} 조회 중...")

            try:
                # 재시도 지원 헬퍼 함수 사용
                info = _fetch_stock_info(ticker)

                if not info or info.get("regularMarketPrice") is None:
                    logger.warning(f"[{idx}/{total}] {ticker} 조회 실패 - 데이터 없음")
                    failed_tickers.append(ticker)
                    continue

                company_name = info.get("longName") or info.get("shortName", "N/A")
                logger.info(f"[{idx}/{total}] {ticker} 완료 - {company_name}")

                data = {
                    "ticker": ticker,
                    "company_name": company_name,
                    "sector": info.get("sector", "N/A"),
                    "industry": info.get("industry", "N/A"),
                    "market_cap": info.get("marketCap"),
                    "market_cap_formatted": _format_large_number(info.get("marketCap")),
                    "trailing_per": info.get("trailingPE"),
                    "forward_per": info.get("forwardPE") if include_forward_per else None,
                    "revenue": info.get("totalRevenue"),
                    "revenue_formatted": _format_large_number(info.get("totalRevenue")),
                    "operating_margin": info.get("operatingMargins"),
                    "profit_margin": info.get("profitMargins"),
                    "revenue_growth": info.get("revenueGrowth")
                }

                peer_data.append(data)

            except Exception as e:
                logger.warning(f"[{idx}/{total}] {ticker} 조회 실패 - {e}")
                failed_tickers.append(ticker)

        logger.info(f"[Peer PER 분석] 완료 - 성공: {len(peer_data)}개, 실패: {len(failed_tickers)}개")

        if not peer_data:
            return {
                "success": False,
                "error": "유효한 티커가 없습니다.",
                "failed_tickers": failed_tickers
            }

        # 통계 계산
        trailing_pers = [d["trailing_per"] for d in peer_data if d["trailing_per"] is not None]
        forward_pers = [d["forward_per"] for d in peer_data if d.get("forward_per") is not None]
        operating_margins = [d["operating_margin"] for d in peer_data if d["operating_margin"] is not None]

        stats = {}

        if trailing_pers:
            stats["trailing_per"] = {
                "mean": round(statistics.mean(trailing_pers), 2),
                "median": round(statistics.median(trailing_pers), 2),
                "min": round(min(trailing_pers), 2),
                "max": round(max(trailing_pers), 2),
                "count": len(trailing_pers)
            }

        if forward_pers:
            stats["forward_per"] = {
                "mean": round(statistics.mean(forward_pers), 2),
                "median": round(statistics.median(forward_pers), 2),
                "min": round(min(forward_pers), 2),
                "max": round(max(forward_pers), 2),
                "count": len(forward_pers)
            }

        if operating_margins:
            stats["operating_margin"] = {
                "mean": round(statistics.mean(operating_margins) * 100, 2),
                "median": round(statistics.median(operating_margins) * 100, 2),
                "min": round(min(operating_margins) * 100, 2),
                "max": round(max(operating_margins) * 100, 2),
                "count": len(operating_margins)
            }

        return {
            "success": True,
            "peer_count": len(peer_data),
            "peers": peer_data,
            "statistics": stats,
            "failed_tickers": failed_tickers,
            "summary": _generate_per_summary(stats)
        }

    except ImportError:
        return {
            "success": False,
            "error": "yfinance가 설치되지 않았습니다. pip install yfinance를 실행하세요."
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Peer PER 분석 실패: {str(e)}"
        }


def _format_large_number(value) -> str:
    """큰 숫자를 읽기 쉬운 형식으로 변환"""
    if value is None:
        return "N/A"

    if abs(value) >= 1_000_000_000_000:  # 1조 이상
        return f"{value / 1_000_000_000_000:.2f}조"
    elif abs(value) >= 1_000_000_000:  # 10억 이상
        return f"{value / 1_000_000_000:.2f}B"
    elif abs(value) >= 1_000_000:  # 100만 이상
        return f"{value / 1_000_000:.2f}M"
    else:
        return f"{value:,.0f}"


def _generate_per_summary(stats: Dict[str, Any]) -> str:
    """PER 분석 요약 텍스트 생성"""
    summary_parts = []

    if "trailing_per" in stats:
        tp = stats["trailing_per"]
        summary_parts.append(f"Trailing PER: 평균 {tp['mean']}x, 중간값 {tp['median']}x (범위: {tp['min']}x ~ {tp['max']}x)")

    if "forward_per" in stats:
        fp = stats["forward_per"]
        summary_parts.append(f"Forward PER: 평균 {fp['mean']}x, 중간값 {fp['median']}x (범위: {fp['min']}x ~ {fp['max']}x)")

    if "operating_margin" in stats:
        om = stats["operating_margin"]
        summary_parts.append(f"영업이익률: 평균 {om['mean']}%, 중간값 {om['median']}% (범위: {om['min']}% ~ {om['max']}%)")

    return "\n".join(summary_parts)


# Tool 실행 함수 매핑
TOOL_EXECUTORS = {
    # Exit 프로젝션 도구
    "read_excel_as_text": execute_read_excel_as_text,
    "analyze_excel": execute_analyze_excel,
    "analyze_and_generate_projection": execute_analyze_and_generate_projection,
    "calculate_valuation": execute_calculate_valuation,
    "calculate_dilution": execute_calculate_dilution,
    "calculate_irr": execute_calculate_irr,
    "generate_exit_projection": execute_generate_exit_projection,
    # Peer PER 분석 도구
    "read_pdf_as_text": execute_read_pdf_as_text,
    "get_stock_financials": execute_get_stock_financials,
    "analyze_peer_per": execute_analyze_peer_per
}


def execute_tool(tool_name: str, tool_input: Dict[str, Any]) -> Dict[str, Any]:
    """도구 실행 디스패처"""

    executor = TOOL_EXECUTORS.get(tool_name)

    if not executor:
        return {
            "success": False,
            "error": f"Unknown tool: {tool_name}"
        }

    try:
        return executor(**tool_input)
    except Exception as e:
        return {
            "success": False,
            "error": f"Tool execution error: {str(e)}"
        }
