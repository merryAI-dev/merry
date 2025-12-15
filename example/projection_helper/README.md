# projection_helper (example)

이 폴더는 프로젝트의 예제용 `projection_helper` 스크립트 복사본을 보관합니다. 원본 스크립트들은 상위 `scripts/` 폴더에 있습니다.

복사된 스크립트

- `analyze_valuation.py` — 투자 검토 엑셀(.xlsx)을 파싱해 투자조건, IS(손익), Cap Table 정보를 JSON으로 출력합니다.
- `generate_advanced_exit_projection.py` — 고급 Exit(부분 매각, NPV 등) 엑셀 시트 생성기.
- `generate_complete_exit_projection.py` — SAFE 전환, 콜옵션 등을 포함한 완전판 Exit 엑셀 생성기.
- `generate_exit_projection.py` — 기본 PER 기반 Exit 프로젝션 엑셀 생성기.

간단 사용법

1. Python 3.8+ 권장
2. 필요 패키지 설치:

```bash
python3 -m pip install --user openpyxl
```

3. 스크립트 실행 예시:

```bash
# Exit 프로젝션 생성 예시
python3 example/projection_helper/generate_exit_projection.py \
  --investment_amount 50000000 \
  --price_per_share 10000 \
  --shares 5000 \
  --total_shares 1000000 \
  --net_income_company 200000000 \
  --net_income_reviewer 150000000 \
  --target_year 2029 \
  --company_name "ExampleCorp" \
  --per_multiples "7,10,15" \
  -o "ExampleCorp_2029_Exit_Projection.xlsx"
```

주의 및 참고

- 이 폴더는 예제 보관용입니다. 원본 스크립트는 `scripts/` 폴더를 유지 관리하세요.
- 스크립트들은 `openpyxl`을 사용해 엑셀 파일을 생성/읽기 합니다.
- 필요하면 이 폴더에서 스크립트를 수정해 예제 실행용으로 커스터마이징 하실 수 있습니다.

문의 사항이 있으면 알려주세요.