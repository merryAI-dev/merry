# VLM 백엔드 선정 & DINOv2 라우팅 실험 기록

> 작성일: 2026-02-28
> 관련 PR: feat/vlm-nova-hybrid-dino-router

---

## 배경

RALPH 파이프라인에서 규칙 기반 추출이 실패한 이미지 PDF(스캔 문서, 슬라이드 자료)를 처리하기 위해 VLM 폴백 레이어가 필요했다. 동시에 UUID 파일명(원본 파일명 없음) 환경에서의 문서 타입 라우팅 성능을 개선하기 위해 DINOv2 시각 분류 도입을 검토했다.

---

## 1. VLM 백엔드 선정

### 요구사항

- **데이터 보안**: 스타트업 IR 자료 등 기밀 문서를 외부 API(Anthropic direct)로 전송 불가
- **비용**: 문서당 처리 비용 최소화
- **정확도**: 시각 요소(차트, 다이어그램) 묘사 포함

### 검토한 옵션

| 옵션 | 비용 | 보안 | 결과 |
|------|------|------|------|
| Claude Sonnet (direct API) | 비쌈 | ✗ 외부 전송 | 탈락 |
| Claude Haiku (Bedrock Marketplace) | 중간 | ✓ | Vision 구독 필요, 탈락 |
| Amazon Nova Lite (Bedrock) | 저렴 | ✓ | 환각 문제 |
| Amazon Nova Pro (Bedrock) | 10× 비쌈 | ✓ | 정확하지만 과비용 |
| **Nova Lite Hybrid** (최종 선택) | **저렴** | **✓** | **환각 제어됨** |

### Nova Lite 단독 사용 시 문제: 텍스트 환각

Nova Lite에 슬라이드 전체 이미지를 넘기면 한국어 텍스트를 읽으려 시도하다 **환각(hallucination)** 이 발생했다. 특히 한글 자간이 넓거나 이미지 해상도가 낮은 문서에서 텍스트를 임의로 조합·변형하는 현상.

### 해결: 역할 분리 전략 (Nova Lite Hybrid)

```
텍스트 추출: PyMuPDF (정확, 0 API 비용)
시각 요소:  Nova Lite (차트/다이어그램 묘사만, 텍스트 읽기 명시 금지)
```

**환각 제어 원칙**:
1. Nova Lite에 "텍스트는 읽지 마세요" 프롬프트 명시
2. 시각 요소(차트 종류, 수치, 로고) 묘사만 요청
3. 불확실하면 "불명확" 출력 강제
4. `temperature=0` 고정

**결과**: 5페이지 IR 자료 기준 $0.00105, 환각 없음, confidence 1.0

### 모델 ID 정책

| 용도 | 환경변수 | 기본값 |
|------|---------|--------|
| 채팅 에이전트 | `BEDROCK_MODEL_ID` | claude-sonnet-4-5 |
| VLM 폴백 (Bedrock Claude) | `RALPH_VLM_MODEL_ID` | claude-haiku-4-5 |
| Nova Lite Hybrid | `RALPH_VLM_NOVA_MODEL_ID` | us.amazon.nova-lite-v1:0 |
| Nova region | `RALPH_VLM_NOVA_REGION` | us-east-1 |

---

## 2. 라우터 DINOv2 통합

### 라우팅 파이프라인

```
파일명 키워드 매칭 (conf 0.9)
    ↓ 실패
텍스트 Classifier (PyMuPDF + 키워드)
    ↓ 실패
DINOv2 시각 분류 (cosine similarity)
    ↓ 실패
none (HITL 수동 지정)
```

### DINOv2 도입 배경

- UUID 파일명 환경에서는 파일명 기반 라우팅 불가
- 스캔 이미지 PDF처럼 텍스트가 없는 문서는 텍스트 classifier도 실패
- DINOv2 (facebook/dinov2-base)는 이전 실험에서 슬라이드(IR 자료) vs 공문서 구별에 명확한 신호를 보임

---

## 3. DINOv2 라우팅 벤치마크 결과

### 테스트 설정

- 문서 수: 13개 (9개 타입)
- 조건 A: 원본 파일명 사용
- 조건 B: UUID 마스킹 (텍스트 classifier + DINOv2, leave-one-out)

### 결과

| 방법 | 정확도 | 비고 |
|------|--------|------|
| 파일명 기반 | **13/13 (100%)** | 한국어 키워드 매칭 |
| 텍스트 Classifier | **11/13 (84.6%)** | UUID 환경 |
| DINOv2 (LOO) | **3/13 (23.1%)** | UUID 환경, leave-one-out |

### 텍스트 Classifier 실패 케이스 (2개)

| 파일 | 실제 타입 | 이유 |
|------|-----------|------|
| IR 자료 (스캔 슬라이드) | investment_review | 텍스트 없음 → unknown |
| 법인등기부등본 | corp_registry | 키워드 미스 |

### DINOv2 실패 원인 분석

**핵심 문제: 한국 행정 공문서의 시각적 동질성**

공문서들(사업자등록증, 주주명부, 재무제표, 정관 등)은 모두 **A4 흰 배경 + 한국 행정 서식** 형태라 DINOv2 임베딩 공간에서 매우 가깝게 위치한다.

실측 cosine similarity:
- 인증서 ↔ 창업기업확인서: **0.944** (사실상 동일 시각 특성)
- 재무제표(4개) ↔ 타 공문서: **0.727~0.896** (높은 유사도)
- IR 슬라이드 ↔ 공문서: **0.205** (명확히 분리됨)

**Leave-one-out의 불리함**: 재무제표처럼 동일 타입이 4개면 1개 제외해도 레퍼런스 3개가 남아 KNN 투표에서 항상 우세.

### DINOv2가 유효한 케이스

| 시나리오 | 효과 |
|----------|------|
| 슬라이드(IR) vs 공문서 이진 분류 | ✓ 명확 (similarity 0.2 vs 0.85+) |
| 공문서 종류 간 구별 | ✗ 불가 (모두 A4 한국 행정서식) |

---

## 4. 결론 및 향후 방향

### 채택된 아키텍처

```
규칙 기반 추출 (confidence ≥ 0.7)
    ↓ 실패
Nova Lite Hybrid VLM 폴백
  - 텍스트: PyMuPDF
  - 시각: Nova Lite (visual-only prompt)
```

### 채택된 최종 라우터 파이프라인

```
1. 파일명 키워드 매칭     (conf 0.9,  0 API 비용)
2. 텍스트 Classifier     (PyMuPDF,   0 API 비용)
3. VLM OCR 2단계         (Nova Lite, ~$0.0001/문서)
   ├─ Step 1: VLM이 문서 제목만 읽기
   ├─ Step 2: Python 키워드 매칭 (결정적, 환각 차단)
   └─ Step 3: 미매칭 → unknown + 문서 설명 (HITL 에스컬레이션)
4. none                  (HITL 수동 지정)
```

---

## 5. CLIP 벤치마크 결과 (추가 실험)

### 테스트 전략 4종

| 전략 | 정확도 | 비고 |
|------|--------|------|
| English CLIP 전체 페이지 | **1/13 (7.7%)** | startup_cert 편향 |
| English CLIP 헤더크롭 25% | **3/13 (23.1%)** | DINOv2와 동률 |
| Multilingual CLIP 한국어 | 측정 불가 | 모델 다운로드 타임아웃 |

### CLIP 실패 원인

- 영어 CLIP은 한국 행정 문서를 학습한 적 없음
- Contrastive Learning 효과가 없는 OOD(Out-of-Distribution) 도메인
- 헤더크롭 시 약간 개선되나 여전히 한계
- **결론**: CLIP은 이 도메인에서 DINOv2와 마찬가지로 실용성 없음

### 시각 분류 한계 공통 원인

시각적 접근(DINOv2, CLIP)이 실패하는 이유는 동일:
- 한국 행정 공문서의 판별 신호가 **이미지 패턴이 아닌 텍스트**에 있음
- 모든 문서가 A4 흰 배경 한국 행정 서식 → 시각적으로 동질

---

## 6. VLM OCR 라우터 최종 벤치마크

### 알려진 문서 (UUID 마스킹 기준)

| 방법 | 정확도 | 미지 문서 처리 | API 비용 |
|------|--------|----------------|---------|
| 파일명 기반 | 100% (13/13) | — | 0 |
| 텍스트 Classifier | 85% (11/13) | ✗ 강제분류 | 0 |
| DINOv2 | 23% (3/13) | ✗ 강제분류 | 0 |
| English CLIP | 8% (1/13) | ✗ 강제분류 | 0 |
| **VLM OCR 2단계** | **85% (11/13)** | **✓ unknown+설명** | ~$0.0001 |

### 미지 문서 테스트 (영수증)

```
입력:  간이 영수증 PDF (아메리카노 2잔, 합계 23,650원)
결과:  ✓ unknown — "금액 결제 및 승인을 기록한 상업 또는 금융 문서"
처리:  HITL 에스컬레이션 (사람이 최종 확인)
```

### 수치 동일한 이유 (85% = 11/13)

VLM OCR이 텍스트 Classifier와 같은 85%이지만 의미가 다름:
- 텍스트 Classifier 실패 케이스: IR 자료(스캔), 법인등기부등본(스캔)
- VLM OCR가 맞게 잡은 케이스: IR 자료 (1단계에서 처음 성공, 2단계에서 다시 실패)
- **핵심 차이**: 오분류(높은 conf 오답) vs HITL 에스컬레이션(올바른 불확실성 표현)

### 2단계 VLM OCR 설계 원칙

**VLM에 판단을 맡기지 않는다 → 환각 억제**

```
1단계 시도 (1-step classify):  12/13 정확, BUT 영수증 오분류 (conf 0.95로 틀림)
2단계 설계 (2-step OCR+KW):    11/13 정확, BUT 영수증 ✓, 오분류 방지
```

오분류와 HITL 에스컬레이션 중 프로덕션에서는 **HITL이 항상 안전**.
VLM의 "알 수 없음"이 "투자검토자료"로 잘못 분류되는 것보다 훨씬 낫다.

---

## 7. 관련 파일

```
ralph/
├── vlm/
│   ├── __init__.py          # 백엔드 팩토리 (RALPH_VLM_BACKEND 환경변수)
│   ├── base.py              # BaseVLMCaller, VLMResult
│   ├── bedrock_caller.py    # Claude Haiku (Bedrock, 문서별 프롬프트)
│   ├── nova_caller.py       # Nova Lite Hybrid (텍스트=PyMuPDF, 시각=Nova)
│   └── doc_classifier.py    # VLM OCR 2단계 문서 분류기 (미지 문서 대응)
├── classifier.py            # 텍스트 키워드 분류기 (0 API, 빠른 경로)
├── dino_classifier.py       # DINOv2 시각 분류기 (벤치마크용, 기본 off)
├── router.py                # 4단계 폴백 라우터 (파일명→텍스트→VLM→none)
└── batch_pipeline.py        # 다건 배치 처리 (규칙 → VLM 폴백)
scripts/
├── benchmark_router.py      # DINOv2 vs 텍스트 vs 파일명 비교
├── benchmark_clip.py        # CLIP 4전략 비교
└── test_vlm_router.py       # VLM OCR 통합 테스트 (영수증 포함)
```
