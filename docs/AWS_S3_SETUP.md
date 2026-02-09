# AWS S3 스토리지 설정 가이드

Phase 4-B에서 구현된 S3 백엔드를 설정하는 방법입니다.

## 📋 사전 준비

1. **AWS 계정** 보유
2. **boto3 설치** (requirements.txt에 포함됨)
   ```bash
   pip install boto3>=1.34.0
   ```

---

## 🪣 S3 버킷 생성

### 1. AWS CLI로 버킷 생성

```bash
# 버킷 생성 (서울 리전)
aws s3 mb s3://merry-training-data --region ap-northeast-2

# 버킷 암호화 활성화 (AES-256)
aws s3api put-bucket-encryption \
  --bucket merry-training-data \
  --server-side-encryption-configuration '{
    "Rules": [{
      "ApplyServerSideEncryptionByDefault": {
        "SSEAlgorithm": "AES256"
      },
      "BucketKeyEnabled": true
    }]
  }'

# 퍼블릭 액세스 차단 (보안)
aws s3api put-public-access-block \
  --bucket merry-training-data \
  --public-access-block-configuration \
  "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true"
```

### 2. AWS 콘솔로 버킷 생성

1. S3 콘솔 접속
2. "버킷 만들기" 클릭
3. 버킷 이름: `merry-training-data`
4. 리전: `ap-northeast-2` (서울)
5. "모든 퍼블릭 액세스 차단" 활성화
6. "서버 측 암호화" 활성화 (AES-256)
7. 버킷 생성

---

## 🔑 IAM 역할 및 정책 설정

### IAM 정책 JSON

`MerryTrainingDataPolicy.json`:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "ListBucket",
      "Effect": "Allow",
      "Action": [
        "s3:ListBucket",
        "s3:GetBucketLocation"
      ],
      "Resource": "arn:aws:s3:::merry-training-data"
    },
    {
      "Sid": "ReadWriteObjects",
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:DeleteObject"
      ],
      "Resource": "arn:aws:s3:::merry-training-data/*"
    }
  ]
}
```

### IAM 정책 생성 및 연결

#### 옵션 1: IAM 사용자 (개발 환경)

```bash
# 1. IAM 정책 생성
aws iam create-policy \
  --policy-name MerryTrainingDataPolicy \
  --policy-document file://MerryTrainingDataPolicy.json

# 2. IAM 사용자 생성
aws iam create-user --user-name merry-training-user

# 3. 정책 연결
aws iam attach-user-policy \
  --user-name merry-training-user \
  --policy-arn arn:aws:iam::YOUR_ACCOUNT_ID:policy/MerryTrainingDataPolicy

# 4. 액세스 키 생성
aws iam create-access-key --user-name merry-training-user
```

출력된 `AccessKeyId`와 `SecretAccessKey`를 `.env`에 저장:

```bash
# .env
AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE
AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
AWS_REGION=ap-northeast-2
```

#### 옵션 2: IAM 역할 (프로덕션 환경, 권장)

EC2/ECS에서 실행 시 IAM 역할 사용 (액세스 키 불필요):

```bash
# 1. 신뢰 정책 생성 (trust-policy.json)
cat > trust-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {
      "Service": "ec2.amazonaws.com"
    },
    "Action": "sts:AssumeRole"
  }]
}
EOF

# 2. IAM 역할 생성
aws iam create-role \
  --role-name MerryTrainingDataRole \
  --assume-role-policy-document file://trust-policy.json

# 3. 정책 연결
aws iam attach-role-policy \
  --role-name MerryTrainingDataRole \
  --policy-arn arn:aws:iam::YOUR_ACCOUNT_ID:policy/MerryTrainingDataPolicy

# 4. 인스턴스 프로파일 생성 및 연결
aws iam create-instance-profile \
  --instance-profile-name MerryTrainingDataProfile

aws iam add-role-to-instance-profile \
  --instance-profile-name MerryTrainingDataProfile \
  --role-name MerryTrainingDataRole
```

EC2 인스턴스 시작 시 인스턴스 프로파일 연결 → 액세스 키 불필요

---

## 🗂️ Lifecycle 정책 설정

90일 후 Glacier로 아카이브:

`lifecycle-policy.json`:
```json
{
  "Rules": [
    {
      "Id": "ArchiveOldTrainingData",
      "Status": "Enabled",
      "Filter": {
        "Prefix": "training/"
      },
      "Transitions": [
        {
          "Days": 90,
          "StorageClass": "GLACIER"
        }
      ]
    }
  ]
}
```

적용:
```bash
aws s3api put-bucket-lifecycle-configuration \
  --bucket merry-training-data \
  --lifecycle-configuration file://lifecycle-policy.json
```

---

## ⚙️ 환경 변수 설정

### .env 파일

```bash
# 데이터 수집 활성화
ENABLE_TRAINING_COLLECTION=true

# 스토리지 백엔드 (local → s3 전환)
TRAINING_STORAGE_BACKEND=s3

# S3 설정
AWS_S3_BUCKET=merry-training-data
AWS_REGION=ap-northeast-2

# AWS 인증 (옵션 1: 액세스 키)
AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE
AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY

# 옵션 2: IAM 역할 사용 시 액세스 키 불필요
# (EC2/ECS에서 인스턴스 프로파일 자동 인식)

# PII 검증 (선택)
TRAINING_PII_STRICT=false
```

---

## 🚀 사용법

### 1. S3 백엔드 활성화

```bash
# .env에 추가
echo "TRAINING_STORAGE_BACKEND=s3" >> .env
echo "AWS_S3_BUCKET=merry-training-data" >> .env
echo "AWS_REGION=ap-northeast-2" >> .env

# Streamlit 재시작
streamlit run app.py
```

### 2. CLI로 S3 데이터 확인

```bash
# 통계 조회 (S3에서 자동 읽기)
python scripts/training_cli.py stats

# 파일 목록 (S3 URI 반환)
python scripts/training_cli.py list pdf_extraction
# 출력:
# s3://merry-training-data/training/pdf_extraction/2026/02/09/abc123.jsonl
# s3://merry-training-data/training/pdf_extraction/2026/02/09/def456.jsonl

# 데이터 내보내기 (S3 → 로컬 JSONL)
python scripts/training_cli.py export pdf_extraction output.jsonl

# PII 검증
python scripts/training_cli.py validate pdf_extraction --verbose
```

### 3. 직접 S3 확인

```bash
# AWS CLI로 S3 파일 목록 조회
aws s3 ls s3://merry-training-data/training/pdf_extraction/ --recursive

# 특정 파일 다운로드
aws s3 cp s3://merry-training-data/training/pdf_extraction/2026/02/09/abc123.jsonl ./

# 파일 내용 확인
cat abc123.jsonl | jq '.'
```

---

## 🔄 로컬 → S3 마이그레이션

### 기존 로컬 데이터를 S3로 업로드

```bash
# 1. 로컬 데이터 확인
ls -lh data/training/

# 2. S3로 동기화
aws s3 sync data/training/ s3://merry-training-data/training/

# 3. 업로드 확인
aws s3 ls s3://merry-training-data/training/ --recursive --human-readable

# 4. .env에서 백엔드 전환
sed -i 's/TRAINING_STORAGE_BACKEND=local/TRAINING_STORAGE_BACKEND=s3/' .env

# 5. Streamlit 재시작 후 동작 확인
streamlit run app.py
```

---

## 🛡️ 보안 체크리스트

- [ ] S3 버킷 암호화 활성화 (AES-256)
- [ ] 퍼블릭 액세스 차단 설정
- [ ] IAM 역할 기반 인증 (프로덕션)
- [ ] 액세스 키는 환경 변수 또는 AWS Secrets Manager 사용
- [ ] `.env` 파일은 `.gitignore`에 포함
- [ ] PII 스크러버 활성화 (`ENABLE_TRAINING_COLLECTION=true`)
- [ ] PII 검증 테스트 (`python scripts/training_cli.py validate`)
- [ ] Lifecycle 정책으로 장기 데이터 아카이브

---

## 🧪 테스트

### S3 연결 테스트

```python
# test_s3_connection.py
from shared.storage_backend import S3StorageBackend

# S3 백엔드 초기화
storage = S3StorageBackend(bucket_name="merry-training-data", prefix="training/")

# 테스트 샘플 작성
sample = {
    "input": {"test": "data"},
    "output": {"result": "success"},
}

try:
    path = storage.write_training_sample(
        task_type="test",
        sample=sample,
        metadata={"test": True}
    )
    print(f"✓ S3 write successful: {path}")

    # 읽기 테스트
    result = storage.read_sample(path)
    print(f"✓ S3 read successful: {result['count']} samples")

    # 목록 조회 테스트
    samples = storage.list_samples(task_type="test")
    print(f"✓ S3 list successful: {len(samples)} files")

    # 통계 조회 테스트
    stats = storage.get_dataset_stats(task_type="test")
    print(f"✓ S3 stats successful: {stats}")

except Exception as e:
    print(f"✗ S3 test failed: {e}")
```

실행:
```bash
python test_s3_connection.py
```

---

## 📊 비용 추정

### S3 스토리지 비용 (서울 리전 기준)

| 항목 | 가격 (USD) |
|------|-----------|
| 스토리지 (Standard) | $0.025/GB/월 |
| PUT/COPY/POST 요청 | $0.0055/1,000 요청 |
| GET/SELECT 요청 | $0.00044/1,000 요청 |
| Glacier 스토리지 (90일 후) | $0.005/GB/월 |

**예시**:
- 월간 1GB 데이터 수집
- 1만 건 PUT 요청
- 1만 건 GET 요청

→ **월 $0.08** (약 100원)

---

## 🔧 문제 해결

### Q: `NoCredentialsError: Unable to locate credentials`

**A**: AWS 인증 설정 확인

```bash
# AWS CLI 설정
aws configure

# 또는 .env에 직접 추가
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
```

### Q: `Access Denied` 오류

**A**: IAM 정책 확인

```bash
# 정책이 사용자/역할에 연결되었는지 확인
aws iam list-attached-user-policies --user-name merry-training-user

# 버킷 정책 확인
aws s3api get-bucket-policy --bucket merry-training-data
```

### Q: 속도가 느립니다

**A**:
- **get_dataset_stats()가 모든 파일을 읽음** → 샘플 수 계산 비용 높음
- 개선: S3 객체 메타데이터에 샘플 수 저장 (`x-amz-meta-sample-count`)
- 또는: stats 캐싱 (1시간 TTL)

### Q: Glacier에서 데이터 복원

```bash
# 복원 요청 (Standard 검색, 3-5시간)
aws s3api restore-object \
  --bucket merry-training-data \
  --key training/pdf_extraction/2026/01/01/abc123.jsonl \
  --restore-request Days=7,GlacierJobParameters={Tier=Standard}

# 복원 상태 확인
aws s3api head-object \
  --bucket merry-training-data \
  --key training/pdf_extraction/2026/01/01/abc123.jsonl
```

---

## 📚 참고 자료

- [AWS S3 공식 문서](https://docs.aws.amazon.com/s3/)
- [boto3 S3 문서](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3.html)
- [IAM 모범 사례](https://docs.aws.amazon.com/IAM/latest/UserGuide/best-practices.html)
- [S3 암호화 가이드](https://docs.aws.amazon.com/AmazonS3/latest/userguide/UsingEncryption.html)

---

## ✅ Phase 4-B 완료 체크리스트

- [x] boto3 설치 (requirements.txt)
- [x] S3StorageBackend 구현 (4개 메서드)
- [ ] S3 버킷 생성
- [ ] IAM 정책 및 역할 설정
- [ ] 환경 변수 설정 (.env)
- [ ] 연결 테스트 실행
- [ ] 로컬 데이터 마이그레이션 (선택)
- [ ] Lifecycle 정책 설정
- [ ] 보안 체크리스트 확인

**Phase 4-B 완료 후 → Phase 2 (문서 분류 + 스마트 청킹) 진행**
