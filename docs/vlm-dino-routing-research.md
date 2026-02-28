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

### 라우터 개선 포인트 (우선순위 순)

1. **텍스트 Classifier 키워드 보완** (빠름): `등기사항전부증명서` 등 추가 → 11→12/13
2. **DINOv2 이진 분류기로 재설계**: "슬라이드형 vs 공문서형" 2-class 분류기로 한정하여 IR 자료 등 시각 자료 감지에만 사용
3. **VLM 라우터 역할**: 텍스트 없는 스캔 문서는 Nova Lite Hybrid로 직접 처리

### 모델 로드 성능

| 모델 | 최초 로드 | 추론 (1 page) | 장치 |
|------|-----------|---------------|------|
| DINOv2-base | ~33초 | 0.03~0.10초 | MPS |
| GroundingDINO-tiny | ~50초 | ~50초/page | CPU |

GroundingDINO는 속도 문제로 탈락. DINOv2는 추론 속도는 우수하나 공문서 종류 간 판별력 부족.

---

## 5. 관련 파일

```
ralph/
├── vlm/
│   ├── __init__.py          # 백엔드 팩토리 (RALPH_VLM_BACKEND 환경변수)
│   ├── base.py              # BaseVLMCaller, VLMResult
│   ├── bedrock_caller.py    # Claude Haiku (Bedrock, 문서별 프롬프트)
│   └── nova_caller.py       # Nova Lite Hybrid (텍스트=PyMuPDF, 시각=Nova)
├── dino_classifier.py       # DINOv2 시각 분류기
├── router.py                # 파일명 → 텍스트 → DINOv2 → none
└── batch_pipeline.py        # 다건 배치 처리 (규칙 → VLM 폴백)
scripts/
└── benchmark_router.py      # 라우팅 방법 비교 벤치마크
```
