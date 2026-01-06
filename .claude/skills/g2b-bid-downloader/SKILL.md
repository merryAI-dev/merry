---
name: g2b-bid-downloader
description: "나라장터 입찰공고 검색, 파일 다운로드, SWOT 분석 자동화 스킬. 관심 분야 입찰을 검색하고 공고문/제안요청서를 다운로드하여 사업별 SWOT 분석과 전략을 제시합니다. 사용 시점: (1) 나라장터 입찰 검색, (2) 공공입찰 공고서 다운로드, (3) 입찰 적합도 분석, (4) 신규 공고 모니터링"
---

# 나라장터 입찰공고 검색 스킬

나라장터(g2b.go.kr)에서 입찰공고를 검색하고, 파일을 다운로드하며, SWOT 분석을 수행하는 스킬.

---

## Part 1. 설치 가이드 (비개발자용)

### 1.1 터미널 열기

Mac에서 터미널을 여는 방법:

1. `Cmd + Space` 를 눌러 Spotlight 검색 열기
2. "터미널" 또는 "Terminal" 입력
3. Enter 키 누르기

### 1.2 Homebrew 설치 확인

터미널에 아래 명령어를 복사해서 붙여넣고 Enter:

```bash
brew --version
```

결과 확인:
- `Homebrew 4.x.x` 같은 버전이 나오면 -> 다음 단계로
- `command not found` 가 나오면 -> 아래 명령어로 설치

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

### 1.3 Node.js 설치 확인

```bash
node --version
```

결과 확인:
- `v18.x.x` 이상이면 -> 다음 단계로
- `command not found` 면 -> 아래 명령어로 설치

```bash
brew install node
```

### 1.4 Claude Code 설치

```bash
npm install -g @anthropic-ai/claude-code
```

설치 확인:

```bash
claude --version
```

### 1.5 Claude Code 로그인

```bash
claude
```

1. 브라우저가 자동으로 열립니다
2. Anthropic 계정으로 로그인
3. "Claude Code 액세스 허용" 클릭
4. 터미널로 돌아오면 완료

### 1.6 프로젝트 폴더로 이동

Google Drive의 projection_helper 폴더로 이동:

```bash
cd "/Users/$(whoami)/Library/CloudStorage/GoogleDrive-본인이메일@mysc.co.kr/공유 드라이브/C. 조직 (랩, 팀, 위원회, 클럽)/00.AX솔루션/projection_helper"
```

(본인이메일 부분을 본인 구글 계정으로 변경)

폴더 이동이 안 되면:
- Finder에서 해당 폴더 열기
- 폴더를 터미널 창에 드래그 앤 드롭
- `cd ` 입력 후 붙여넣기

### 1.7 Python 패키지 설치

```bash
source venv/bin/activate
pip install playwright olefile requests pyhwp
playwright install chromium
```

### 1.8 HWP 파싱 안내

나라장터 HWP 파일은 특수 포맷을 사용하여 hwp5txt와 호환되지 않습니다.
대신 olefile + zlib 방식으로 텍스트를 추출합니다 (자동 처리).

```bash
# olefile 설치 확인 (1.7에서 이미 설치됨)
pip show olefile
```

참고: hwp5txt를 시도해도 "ColumnSet AssertionError"가 발생합니다.
이는 정상이며, Claude가 olefile 방식으로 자동 폴백합니다.

### 1.9 설치 확인

```bash
python scripts/g2b_file_downloader.py "테스트" --list-only
```

검색 결과가 나오면 설치 완료!

---

## Part 2. 사용법

### 2.1 Claude Code 실행

프로젝트 폴더에서:

```bash
claude
```

### 2.2 자연어로 검색

```
나라장터에서 액셀러레이팅 입찰 찾아줘
```

```
나라장터에서 창업지원 입찰 검색해줘
```

### 2.3 스킬 직접 실행

```
/g2b-bid-downloader 액셀러레이팅
```

### 2.4 검색 키워드 예시

- 액셀러레이팅: 액셀러레이터 관련 사업
- 창업지원: 창업 지원 프로그램
- 스타트업: 스타트업 관련 용역
- 컨설팅: 경영/기술 컨설팅
- 인공지능: AI 관련 사업

### 2.5 추가 요청

검색 후 추가로 요청:

```
MYSC 기준으로 SWOT 분석해줘
```

```
슬랙에 붙여넣을 수 있게 정리해줘
```

```
기보벤처캠프 공고 파일 다운로드해줘
```

---

## Part 3. 스킬 워크플로우

### Phase 1: 관심 분야 파악

```
AskUserQuestion:
question: "어떤 종류의 입찰공고에 관심이 있으신가요?"
options:
  - label: "액셀러레이팅/창업지원"
  - label: "소프트웨어/IT 개발"
  - label: "컨설팅/연구용역"
  - label: "직접 입력"
```

### Phase 2: 검색 및 목록 제시

크롤링으로 나라장터 검색 (기본 90일):

```bash
python scripts/g2b_file_downloader.py "<키워드>" --list-only
```

결과를 테이블로 정리 (이모지 없이):

```
| # | 공고명 | 발주기관 | 추정가격 | 마감일 | 상태 |
|---|--------|----------|----------|--------|------|
| 1 | 기보벤처캠프 액셀러레이팅 | 기술보증기금 | 6.8억 | 1/8 | D-2 |
```

### Phase 3: 파일 다운로드

```bash
python scripts/g2b_file_downloader.py "<키워드>" --indices 1,2
```

### Phase 4: 회사 역량 파악 (SWOT용)

```
AskUserQuestion:
question: "귀사의 주요 역량은 무엇인가요?"
multiSelect: true
options:
  - label: "액셀러레이팅/보육 운영 경험"
  - label: "SW 개발/시스템 구축"
  - label: "컨설팅/연구용역 수행"
  - label: "교육/멘토링 프로그램"

question: "TIPS 운영사 또는 중기부 등록 액셀러레이터인가요?"
options:
  - label: "TIPS 운영사"
  - label: "등록 액셀러레이터"
  - label: "둘 다"
  - label: "해당없음"
```

### Phase 5: 필요서류 추출 (HWP 파싱 + Opus 검증)

**Step 1: HWP 텍스트 추출** (olefile + zlib 방식)

```python
# 나라장터 HWP는 hwp5txt와 호환 안 됨 → olefile 폴백 사용
import olefile, zlib, re

ole = olefile.OleFileIO(hwp_path)
for entry in ole.listdir():
    if entry[0] == 'BodyText':
        data = ole.openstream(entry).read()
        text = zlib.decompress(data, -15).decode('utf-16le', errors='ignore')
        # 한글/영문/숫자만 추출
        clean = re.sub(r'[^\uAC00-\uD7A3a-zA-Z0-9\s\.\,\(\)\-\:\;\/]+', ' ', text)
```

**Step 2: 키워드 기반 섹션 추출**

추출 대상 키워드:
- 제출서류, 서식, 입찰참가, 신청서류
- 제출처, 제출방법, 마감, 유의사항

**Step 3: Opus 검증**

추출된 원문을 Opus에게 전달하여 다음을 검증/정리:
1. 필요 서류 목록 (완전한 리스트)
2. 제출처 및 방법
3. 마감일시 (정확한 날짜와 시간)
4. 유의사항 (핵심만)

```
Task(subagent_type="general-purpose"):
prompt: "HWP에서 추출한 원문을 검증하고 슬랙용 형식으로 정리해주세요"
```

### Phase 6: SWOT 분석 및 결과 출력

---

## Part 4. 출력 형식 (슬랙용)

슬랙 붙여넣기용 형식 (이모지 없음, 테이블 없음):

```
나라장터 입찰공고 상세 (YYYY.MM.DD 기준)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. [사업명]

[기본 정보]
• 사업명: (긴급) 2026년 기보벤처캠프 액셀러레이팅 위탁운영 용역
• 발주기관: 기술보증기금 벤처혁신금융부
• 공고번호: R25BK01251130-000
• 추정가격: 6.8억원
• 마감: 2026.1.8.(목) 18:00 (D-2)

[수행 자격]
• 중소벤처기업부 등록 창업기획자(액셀러레이터) 또는 TIPS 운영사

[수행 범위]
• 참여기업 선정: 모집 홍보, 협의회 구성, 서류/발표평가 참여
• 프로그램 운영: 비즈니스 진단, 맞춤형 컨설팅/멘토링
• 투자유치 지원: IR피칭 트레이닝, 데모데이, 직접투자 검토
• 성과관리: 사례집 발간, 네트워킹 운영, 성과보고서 제출

[필요 서류]
• 입찰참가신청서 (서식 1-1, 1-2)
• 사용인감계 (필요시)
• 유사용역 수행 실적 (서식 2-1, 2-2)
• 용역실적 증명원 (최근 2년 이내)
• 신용평가등급 확인서 (G2B 조회 가능)
• 제안서 + 가격입찰서 (별도 밀봉)
• 제출처: 부산 남구 문현금융로 33 기술보증기금 7층
• 제출방법: 우편만 가능 (방문 불가)

[SWOT 분석 - MYSC 기준]
• S 강점: TIPS+등록AC 자격 충족 / AC 운영경험 풍부 / ESG 전문성 차별화 / IR코칭 역량
• W 약점: 보육공간 확인 필요 / 부산 발주처(물리적 거리) / 기보 네트워크 부족 가능
• O 기회: 최대 규모(6.8억) / 연간 반복사업 / 딜소싱 기회
• T 위협: D-2 마감 / 기존 수행사 경쟁 / 가격제한(기업당 600만원)

적합도: 5/5 - 필수자격 충족, ESG 차별화 가능

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

---

## Part 5. SWOT 분석 기준

### 강점(S) 평가 항목
- 필수 자격요건 충족 여부 (TIPS, 등록AC 등)
- 유사 사업 수행 경험
- 차별화 가능한 전문성 (ESG, 글로벌, 특정 산업 등)
- 핵심 인력/멘토 네트워크

### 약점(W) 평가 항목
- 물리적 제약 (보육공간, 지역)
- 발주처 네트워크/관계
- 요구 역량 대비 부족한 부분
- 가격 경쟁력

### 기회(O) 평가 항목
- 사업 규모 및 성장성
- 연속 사업 가능성
- 부가 기회 (투자, 네트워킹 등)
- 시장/정책 트렌드 부합

### 위협(T) 평가 항목
- 마감 일정
- 기존 수행사 경쟁
- 가격/조건 제약
- 평가 불확실성

---

## Part 6. 문제 해결

### Q1. "command not found: claude" 에러
Claude Code 설치 안 됨. 1.4 단계 다시 진행.

### Q2. "permission denied" 에러
```bash
sudo npm install -g @anthropic-ai/claude-code
```

### Q3. 검색 결과가 안 나와요
나라장터 서버 상태 문제. 잠시 후 재시도.

### Q4. 파일 다운로드가 안 돼요
```bash
playwright install chromium
```

### Q5. Google Drive 폴더를 못 찾아요
Finder에서 폴더를 터미널에 드래그 앤 드롭.

---

## Part 7. 자주 쓰는 명령어

```bash
# Claude Code 실행
claude

# 가상환경 활성화
source venv/bin/activate

# 입찰공고 검색만
python scripts/g2b_file_downloader.py "키워드" --list-only

# 특정 공고 파일 다운로드
python scripts/g2b_file_downloader.py "키워드" --indices 1,2,3
```

---

## Part 8. 기술 스택

- 크롤링: requests + 나라장터 API
- 파일 다운로드: Playwright + Raonkupload k00
- HWP 파싱: olefile + zlib (나라장터 HWP 전용)
  - 참고: hwp5txt는 나라장터 HWP와 호환 안 됨 (ColumnSet 오류)
- 검증: Claude Opus를 통한 추출 내용 검증
- 분석: Claude를 통한 요구사항 분석 및 SWOT 도출

---

마지막 업데이트: 2026.01.06
