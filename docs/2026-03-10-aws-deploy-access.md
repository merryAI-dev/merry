# AWS 비-root 배포 접근 정리

이 문서는 `471036546503` 계정에서 root 대신 배포용 자격을 만들기 위한 최소 절차를 정리한다.

대상 저장소 스크립트:

- `infra/aws/doctor.sh`
- `infra/aws/push_worker_image.sh`
- `infra/aws/deploy_worker_ecs.sh`

배포 대상 리소스:

- 계정: `471036546503`
- 리전: `ap-northeast-2`
- ECR: `merry-worker`
- ECS 클러스터: `merry`
- ECS 서비스: `merry-worker`
- DynamoDB: `merry-main`
- S3: `merry-private-apne2-seoul-471036546503`
- SQS: `merry-analysis-jobs`

## 1. 어떤 자격이 필요한가

현재 이 머신에는 재사용 가능한 비-root 자격이 없다.

- `~/.aws/credentials`: 비어 있음
- `~/.aws/config`: `default`가 만료된 root 기반 `login_session`만 가리킴

따라서 아래 둘 중 하나를 새로 만들어야 한다.

1. IAM 사용자 `merry-deploy` + access key
2. IAM Identity Center(SSO) 권한 세트 + `merry-prod` 프로필

운영상 더 안전한 건 `SSO`이고, 당장 빠른 건 `IAM 사용자`다.

## 2. IAM 사용자 방식

### 2-1. 콘솔에서 할 일

1. `471036546503` 계정의 AWS 콘솔로 들어간다.
2. IAM > Users > `Create user`
3. 사용자 이름을 `merry-deploy`로 만든다.
4. 권한은 inline policy 또는 customer managed policy로 [`infra/aws/policies/deployer-policy.json`](/Users/boram/merry/infra/aws/policies/deployer-policy.json)을 붙인다.
5. Access key를 생성한다.

주의:

- 이 정책은 "지속 배포" 기준 최소 권한이다.
- 처음부터 인프라를 만드는 bootstrap 권한은 포함하지 않는다.
- `merry-worker-task-role`, `merry-worker-exec-role`가 아직 없다면 관리자 권한으로 [`infra/aws/provision_iam.sh`](/Users/boram/merry/infra/aws/provision_iam.sh)을 먼저 실행해야 한다.

### 2-2. 로컬에서 할 일

```bash
aws configure --profile merry-prod
```

입력값:

- AWS Access Key ID: 콘솔에서 발급한 값
- AWS Secret Access Key: 콘솔에서 발급한 값
- Default region name: `ap-northeast-2`
- Default output format: `json`

검증:

```bash
aws sts get-caller-identity --profile merry-prod
```

여기서 `Account`가 반드시 `471036546503`여야 한다.

## 3. SSO 방식

`471036546503` 계정이 IAM Identity Center를 쓴다면 아래로 간다.

```bash
aws configure sso --profile merry-prod
aws sso login --profile merry-prod
aws sts get-caller-identity --profile merry-prod
```

역시 `Account = 471036546503`인지 확인한다.

## 4. 배포 순서

배포 전 확인:

```bash
AWS_PROFILE=merry-prod AWS_REGION=ap-northeast-2 \
MERRY_S3_BUCKET=merry-private-apne2-seoul-471036546503 \
MERRY_DDB_TABLE=merry-main \
MERRY_SQS_QUEUE_NAME=merry-analysis-jobs \
bash infra/aws/doctor.sh
```

worker 이미지 push:

```bash
AWS_PROFILE=merry-prod AWS_REGION=ap-northeast-2 \
MERRY_ECR_REPO=merry-worker \
bash infra/aws/push_worker_image.sh
```

worker ECS 배포:

```bash
AWS_PROFILE=merry-prod AWS_REGION=ap-northeast-2 \
ECR_IMAGE=471036546503.dkr.ecr.ap-northeast-2.amazonaws.com/merry-worker:latest \
MERRY_DDB_TABLE=merry-main \
MERRY_S3_BUCKET=merry-private-apne2-seoul-471036546503 \
MERRY_SQS_QUEUE_URL=https://sqs.ap-northeast-2.amazonaws.com/471036546503/merry-analysis-jobs \
LLM_PROVIDER=bedrock \
BEDROCK_MODEL_ID=anthropic.claude-3-5-sonnet-20241022-v2:0 \
bash infra/aws/deploy_worker_ecs.sh
```

## 5. 내가 먼저 확인할 체크리스트

아래 중 하나라도 `아니오`면 배포 전에 권한부터 정리해야 한다.

- `aws sts get-caller-identity --profile merry-prod`가 동작하는가
- 그 결과 `Account`가 `471036546503`인가
- `merry-worker-task-role`와 `merry-worker-exec-role`가 이미 존재하는가
- `merry-worker` ECR repo가 없더라도 만들 수 있는가

## 6. 이 정책으로 안 되는 것

아래는 의도적으로 빠져 있다.

- 새로운 ECS task role 생성
- 새로운 Lambda role 생성
- S3 버킷 / DDB / SQS bootstrap
- Vercel IAM 사용자 생성

이 작업은 초기 bootstrap 권한이 필요하므로 관리자 계정에서 처리해야 한다.
