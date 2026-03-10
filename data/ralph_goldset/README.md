# RALPH Goldset

이 디렉토리는 조건검사 정확도 평가용 정답셋을 저장한다.

## 목적

- 자연어 정책을 측정 가능한 기준으로 고정한다.
- 정책별 precision / recall / false positive 사례를 반복 측정한다.
- reviewer correction을 evaluator 입력으로 축적한다.

## 파일

- `manifest.schema.json`: goldset JSONL 스키마
- `manifest.sample.jsonl`: 샘플 레코드

## 운영 규칙

1. 한 줄은 `문서 x 정책` 한 건이다.
2. `expected_result`는 reviewer-confirmed truth여야 한다.
3. `expected_evidence`에는 근거 문구 또는 키워드를 최소 1개 적는다.
4. 파일명 충돌이 있을 수 있으므로 가능하면 `record_id`와 `company_group_key`를 함께 유지한다.
5. 같은 문서를 재수집한 경우 새 줄을 추가하지 말고 기존 truth를 갱신한다.

## 예시 평가 흐름

```bash
./.tdd_venv/bin/python scripts/eval_condition_accuracy.py \
  --manifest data/ralph_goldset/manifest.sample.jsonl \
  --results /path/to/condition_check_results.json \
  --out /tmp/ralph_eval_report.json
```
