# フェデレーティッドユーザーによる AWS デプロイ完全手順書

> **対象**: AWS IAM Identity Center (SSO) 経由でフェデレーティッドユーザーとして認証するユーザー  
> **アプリ構成**: FastAPI (バックエンド) + React/Vite (フロントエンド) + PostgreSQL  
> **AWS 構成**: ECS Fargate + RDS + S3/CloudFront + ALB  
> **CI/CD**: GitHub Actions (OIDC 認証)

---

## フェデレーティッドユーザーとは

IAM ユーザー (長期アクセスキー) ではなく、以下のいずれかで AWS に一時認証するユーザーです:

| 認証方式 | 認証元 | コマンド |
|----------|--------|----------|
| **SAML フェデレーション (本環境)** | Azure AD (Microsoft Entra ID) | `aws-azure-login --mode=gui` |
| IAM Identity Center | 企業 IdP / AWS SSO | `aws sso login` |
| STS AssumeRole | 別 AWS アカウントのロール | `aws sts assume-role` |

**本環境の認証フロー**:
```
aws-azure-login → Azure AD 認証 (ブラウザ) → SAML アサーション → AWS STS
→ 一時認証情報 (~/.aws/credentials に書き込み) → 有効期限 1 時間
```

**重要な違い**: 認証情報は **1 時間** で自動失効します。Terraform apply や Docker push の途中でセッション切れに注意が必要です。

---

## 目次

- [前提条件](#前提条件)
- [Phase 1: AWS 認証のセットアップ (aws-azure-login)](#phase-1-aws-認証のセットアップ-aws-azure-login)
- [Phase 1C: AWS コンソールへのログイン](#phase-1c-aws-コンソールへのログイン)
- [Phase 2: ツールのインストール](#phase-2-ツールのインストール)
- [Phase 3: Terraform State バックエンド準備](#phase-3-terraform-state-バックエンド準備)
- [Phase 4: シークレットの作成](#phase-4-シークレットの作成)
- [Phase 5: Terraform によるインフラ構築](#phase-5-terraform-によるインフラ構築)
- [Phase 6: 初回デプロイ (手動)](#phase-6-初回デプロイ-手動)
- [Phase 7: GitHub Actions の設定](#phase-7-github-actions-の設定)
- [Phase 8: 動作確認](#phase-8-動作確認)
- [トラブルシューティング](#トラブルシューティング)
- [認証情報の有効期限と更新](#認証情報の有効期限と更新)

---

## 前提条件

- 組織管理者から以下を取得済み:
  - Azure Tenant ID (例: `36da45f1-dd2c-4d1f-af13-5abe46b99921`)
  - Azure App ID URI (例: `https://signin.aws.amazon.com/saml#146062274667`)
  - 組織アカウント (例: `a-haytakeda@tohmatsu.co.jp`)
  - AWS アカウント ID (例: `146062274667`)
- macOS / Linux ターミナル環境
- Node.js (aws-azure-login のインストールに必要)
- Git, Docker Desktop インストール済み
- このリポジトリをローカルに clone 済み

---

## Phase 1: AWS 認証のセットアップ (aws-azure-login)

### 1.1 aws-azure-login のインストール

```bash
npm install -g aws-azure-login
```

### 1.2 プロファイルの設定

```bash
aws-azure-login --configure
```

対話プロンプトに以下を入力:

```
? Azure Tenant ID: 36da45f1-dd2c-4d1f-af13-5abe46b99921
? Azure App ID URI: https://signin.aws.amazon.com/saml#146062274667
? Default Username: a-haytakeda@tohmatsu.co.jp
? Stay logged in: skip authentication while refreshing aws credentials (true|false): false
? Default Role ARN (if multiple): (空欄 — ロールが 1 つなら省略可)
? Default Session Duration Hours (up to 12): 1
? AWS Region: ap-northeast-1
```

これにより `~/.aws/config` に以下が設定されます:

```ini
[profile default]
azure_tenant_id = 36da45f1-dd2c-4d1f-af13-5abe46b99921
azure_app_id_uri = https://signin.aws.amazon.com/saml#146062274667
azure_default_username = a-haytakeda@tohmatsu.co.jp
azure_default_session_duration_hours = 1
region = ap-northeast-1
```

### 1.3 ログインとテスト

```bash
# Azure AD 認証 (ブラウザが開く)
aws-azure-login --mode=gui

# 認証確認
aws sts get-caller-identity
```

期待される出力:

```json
{
  "UserId": "AROASEAP5OBVVBN5B6AWU:a-haytakeda@tohmatsu.co.jp",
  "Account": "146062274667",
  "Arn": "arn:aws:sts::146062274667:assumed-role/AWS_146062274667_Admin/a-haytakeda@tohmatsu.co.jp"
}
```

> **注意**: `aws-azure-login` は `~/.aws/credentials` の `[default]` プロファイルに一時認証情報 (AccessKeyId, SecretAccessKey, SessionToken) を書き込みます。`--profile` 指定は不要です。

### 1.4 セッション有効期限

| 項目 | 値 |
|------|----|
| セッション持続時間 | **1 時間** (設定値) |
| 最大延長可能 | 12 時間 (管理者設定に依存) |
| 再認証方法 | `aws-azure-login --mode=gui` を再実行 |

> ⚠️ **1 時間は短いです。** `terraform apply` (10〜15分) や Docker build + push の前に必ず再認証してください。

---

## Phase 1C: AWS コンソールへのログイン

フェデレーティッドユーザーは **Azure AD** 経由で AWS マネジメントコンソールにアクセスします。

### コンソールログイン手順

1. **Azure ポータルまたは myapps からアクセス**
   ```
   方法 A: https://myapps.microsoft.com → AWS アプリタイルをクリック
   方法 B: 組織が配布した AWS コンソールへの直リンク
   ```

2. **Azure AD 認証**
   - 組織アカウント (`a-haytakeda@tohmatsu.co.jp`) でログイン
   - MFA が要求された場合は認証を完了

3. **ロールの選択 (複数ロールがある場合)**
   ```
   ロール一覧が表示される場合:
     → AWS_146062274667_Admin を選択
   ロールが 1 つの場合:
     → 自動的にコンソールが開く
   ```

4. **コンソールが開く**
   - 右上のヘッダーに `AWS_146062274667_Admin/a-haytakeda@tohmatsu.co.jp` と表示されることを確認
   - リージョンが `ap-northeast-1 (東京)` であることを確認 (異なる場合は右上のリージョンセレクターで変更)

### コンソールセッションの注意事項

- コンソールセッションの有効期限: **1 時間** (SAML のセッション時間に準拠)
- 期限切れ時は Azure ポータルから再度ログインが必要
- CLI (`aws-azure-login`) とコンソールのセッションは独立 — 片方が切れてももう片方は有効

---

## Phase 2: ツールのインストール

```bash
# AWS CLI v2
brew install awscli

# Terraform
brew tap hashicorp/tap && brew install hashicorp/tap/terraform

# Docker (Docker Desktop がインストール済みであること)
docker --version

# 確認
aws --version         # >= 2.x
terraform --version   # >= 1.5
docker --version      # >= 24.x
aws-azure-login --version
```

---

## Phase 2C: Budget アラートの設定 (推奨)

予期しない課金を防ぐため、コスト予算アラートを設定します。

<details>
<summary><b>CLI で実行する場合</b></summary>

```bash
cat > /tmp/budget.json << 'EOF'
{
  "BudgetName": "test-app-monthly",
  "BudgetLimit": {"Amount": "10", "Unit": "USD"},
  "TimeUnit": "MONTHLY",
  "BudgetType": "COST"
}
EOF

cat > /tmp/notifications.json << 'EOF'
[
  {
    "Notification": {
      "NotificationType": "ACTUAL",
      "ComparisonOperator": "GREATER_THAN",
      "Threshold": 80,
      "ThresholdType": "PERCENTAGE"
    },
    "Subscribers": [
      {"SubscriptionType": "EMAIL", "Address": "your-email@example.com"}
    ]
  }
]
EOF

ACCOUNT_ID=$(aws sts get-caller-identity --query 'Account' --output text)
aws budgets create-budget \
  --account-id "${ACCOUNT_ID}" \
  --budget file:///tmp/budget.json \
  --notifications-with-subscribers file:///tmp/notifications.json
```

</details>

<details>
<summary><b>コンソールから実行する場合</b></summary>

1. **Billing コンソールを開く**
   ```
   AWS コンソール → 右上のアカウント名 → 「請求とコスト管理」
   または: サービス → AWS Budgets
   ```

2. **予算を作成**
   ```
   左メニュー「予算」→ 「予算を作成」
   ```

3. **予算設定**
   ```
   予算タイプ: コスト予算
   予算名: test-app-monthly
   期間: 月次
   予算額: $10.00
   ```

4. **アラート設定**
   ```
   アラートの閾値:
     - 実績コストが予算の 80% を超えた場合
     - 通知先: your-email@example.com
   ```

5. **「予算を作成」をクリック**

</details>

---

## Phase 3: Terraform State バックエンド準備

Terraform の状態ファイルを安全に管理する S3 バケットと DynamoDB テーブルを作成します。

### 3.1 S3 バケット作成

<details>
<summary><b>CLI で実行する場合</b></summary>

```bash
ACCOUNT_ID=$(aws sts get-caller-identity --query 'Account' --output text)
BUCKET_NAME="test-app-terraform-state-${ACCOUNT_ID}"

aws s3api create-bucket \
  --bucket "${BUCKET_NAME}" \
  --region ap-northeast-1 \
  --create-bucket-configuration LocationConstraint=ap-northeast-1

# バージョニング有効化
aws s3api put-bucket-versioning \
  --bucket "${BUCKET_NAME}" \
  --versioning-configuration Status=Enabled

# 暗号化有効化
aws s3api put-bucket-encryption \
  --bucket "${BUCKET_NAME}" \
  --server-side-encryption-configuration '{
    "Rules": [{"ApplyServerSideEncryptionByDefault": {"SSEAlgorithm": "AES256"}}]
  }'

# パブリックアクセス完全ブロック
aws s3api put-public-access-block \
  --bucket "${BUCKET_NAME}" \
  --public-access-block-configuration \
    BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true
```

</details>

<details>
<summary><b>コンソールから実行する場合</b></summary>

1. **S3 コンソールを開く**
   ```
   AWS コンソール → サービス → S3 → 「バケットを作成」
   ```

2. **バケット設定**
   ```
   バケット名: test-app-terraform-state-{アカウントID}
   リージョン: アジアパシフィック (東京) ap-northeast-1
   オブジェクト所有者: ACL 無効
   ```

3. **パブリックアクセス設定**
   ```
   「パブリックアクセスをすべてブロック」: ✅ チェック
   ```

4. **バージョニング**
   ```
   バケットのバージョニング: 有効にする
   ```

5. **暗号化**
   ```
   サーバー側の暗号化: 有効
   暗号化タイプ: Amazon S3 マネージドキー (SSE-S3)
   バケットキー: 有効
   ```

6. **「バケットを作成」をクリック**

</details>

### 3.2 DynamoDB テーブル作成 (State ロック用)

<details>
<summary><b>CLI で実行する場合</b></summary>

```bash
aws dynamodb create-table \
  --table-name test-app-terraform-lock \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --region ap-northeast-1
```

</details>

<details>
<summary><b>コンソールから実行する場合</b></summary>

1. **DynamoDB コンソールを開く**
   ```
   AWS コンソール → サービス → DynamoDB → 「テーブルの作成」
   ```

2. **テーブル設定**
   ```
   テーブル名: test-app-terraform-lock
   パーティションキー: LockID (文字列 / String)
   ソートキー: (空欄 — 追加しない)
   ```

3. **テーブル設定 (キャパシティ)**
   ```
   テーブルクラス: DynamoDB Standard
   キャパシティモード: オンデマンド
   ```

4. **「テーブルの作成」をクリック**

5. **ステータスが「アクティブ」になるまで待機** (数秒)

</details>

### 3.3 backend.tf の更新

`infrastructure/environments/production/backend.tf` を実際のバケット名に更新:

```hcl
terraform {
  backend "s3" {
    bucket         = "test-app-terraform-state-146062274667"  # ← 実際のアカウント ID
    key            = "production/terraform.tfstate"
    region         = "ap-northeast-1"
    encrypt        = true
    dynamodb_table = "test-app-terraform-lock"
  }
}
```

> **注意**: `aws-azure-login` は `default` プロファイルに認証情報を書き込むため、`profile` 指定は不要です。

### 3.4 確認

```bash
aws s3 ls s3://${BUCKET_NAME}/ --region ap-northeast-1
aws dynamodb describe-table --table-name test-app-terraform-lock --query 'Table.TableStatus'
# → "ACTIVE"
```

---

## Phase 4: シークレットの作成

### 4.1 JWT シークレット

<details>
<summary><b>CLI で実行する場合</b></summary>

```bash
aws secretsmanager create-secret \
  --name "test-app/jwt-secret" \
  --description "JWT signing key for test-app" \
  --secret-string "$(openssl rand -hex 32)" \
  --region ap-northeast-1

# ARN を控える
JWT_SECRET_ARN=$(aws secretsmanager describe-secret \
  --secret-id "test-app/jwt-secret" \
  --query 'ARN' --output text)
echo "JWT Secret ARN: ${JWT_SECRET_ARN}"
```

</details>

<details>
<summary><b>コンソールから実行する場合</b></summary>

1. **Secrets Manager コンソールを開く**
   ```
   AWS コンソール → サービス → Secrets Manager → 「新しいシークレットを保存する」
   ```

2. **シークレットのタイプ**
   ```
   シークレットのタイプ: その他のシークレットのタイプ
   ```

3. **シークレットの名前と値**
   ```
   シークレットの名前: test-app/jwt-secret
   説明: JWT signing key for test-app
   プレーンテキスト: (事前にローカルで生成した値を貼り付け)
   ```

   ローカルでランダム値を生成:
   ```bash
   openssl rand -hex 32
   # → 出力された 64 文字の文字列をコピー
   ```

4. **ローテーション設定**
   ```
   自動ローテーション: 無効
   ```

5. **「保存」をクリック**

6. **ARN を控える**
   ```
   シークレット詳細ページ → 「シークレットの ARN」をコピー
   例: arn:aws:secretsmanager:ap-northeast-1:146062274667:secret:test-app/jwt-secret-AbCdEf
   ```

</details>

### 4.2 terraform.tfvars の更新

`infrastructure/environments/production/terraform.tfvars` を編集:

```hcl
project_name = "test-app"
aws_region   = "ap-northeast-1"

# ネットワーク
vpc_cidr           = "10.0.0.0/16"
availability_zones = ["ap-northeast-1a", "ap-northeast-1c"]

# ECS
task_cpu      = 256
task_memory   = 512
desired_count = 1

# RDS
db_instance_class    = "db.t3.micro"
db_allocated_storage = 20
db_max_storage       = 100
db_name              = "app"
db_username          = "postgres"
multi_az             = false

# GitHub (自分のリポジトリに変更)
github_org  = "your-github-username"
github_repo = "test_app"

# JWT シークレット (Phase 4.1 で取得した ARN)
jwt_secret_arn = "arn:aws:secretsmanager:ap-northeast-1:146062274667:secret:test-app/jwt-secret-XXXXXX"

# ACM 証明書 (ドメインなしの場合はコメントアウトのまま)
# certificate_arn          = "arn:aws:acm:ap-northeast-1:ACCOUNT_ID:certificate/CERT_ID"
# frontend_domain_name     = "app.example.com"
# frontend_certificate_arn = "arn:aws:acm:us-east-1:ACCOUNT_ID:certificate/CERT_ID"
```

---

## Phase 5: Terraform によるインフラ構築

### 5.1 Terraform provider の確認

`infrastructure/environments/production/main.tf` の provider ブロック:

```hcl
provider "aws" {
  region = var.aws_region
  # aws-azure-login は default プロファイルに認証情報を書き込むため
  # profile 指定は不要 (デフォルトで default を使用)

  default_tags {
    tags = {
      Project     = var.project_name
      Environment = "production"
      ManagedBy   = "terraform"
    }
  }
}
```

> **ポイント**: `aws-azure-login` は `~/.aws/credentials` の `[default]` セクションに一時認証情報を書き込みます。Terraform は自動的にこれを読み取るので、`profile` を明示的に指定する必要はありません。

### 5.2 ログインの確認

Terraform 実行前に必ず認証が有効であることを確認:

```bash
# セッションが切れている場合は再ログイン
aws-azure-login --mode=gui

# 確認
aws sts get-caller-identity
```

### 5.3 Terraform 初期化

```bash
cd infrastructure/environments/production
terraform init
```

期待される出力:

```
Initializing modules...
- alb in ../../modules/alb
- ecr in ../../modules/ecr
- ecs in ../../modules/ecs
- iam in ../../modules/iam
- rds in ../../modules/rds
- s3_cloudfront in ../../modules/s3-cloudfront
- vpc in ../../modules/vpc

Initializing the backend...
Successfully configured the backend "s3"!

Terraform has been successfully initialized!
```

### 5.4 プラン確認

```bash
terraform plan -out=tfplan
```

作成されるリソース一覧が表示されます。エラーがないことを確認してください。

主要なリソース:
- VPC + サブネット (パブリック / プライベート / DB)
- NAT Gateway
- ALB + ターゲットグループ
- ECS クラスタ + サービス + タスク定義
- ECR リポジトリ
- RDS PostgreSQL インスタンス
- S3 バケット + CloudFront ディストリビューション
- IAM ロール (ECS 実行ロール, GitHub Actions OIDC ロール)

### 5.5 適用

```bash
terraform apply tfplan
```

**所要時間**: 10〜15 分 (RDS と NAT Gateway の作成に時間がかかります)

> ⚠️ セッション有効期限は **1 時間** です。`terraform apply` が長時間かかる場合、途中でセッションが切れることがあります。実行直前に `aws-azure-login --mode=gui` で再認証してください。

### 5.6 出力値の取得

```bash
terraform output
```

以下の値を控えます:

```
alb_dns_name               = "test-app-alb-xxxxx.ap-northeast-1.elb.amazonaws.com"
cloudfront_distribution_id = "E1234567890ABC"
cloudfront_domain_name     = "d1234567890.cloudfront.net"
deploy_role_arn            = "arn:aws:iam::146062274667:role/test-app-github-actions-deploy"
ecr_repository_url         = "146062274667.dkr.ecr.ap-northeast-1.amazonaws.com/test-app/backend"
ecs_cluster_name           = "test-app-cluster"
ecs_service_name           = "test-app-backend"
s3_bucket_name             = "test-app-frontend-production"
db_host                    = "test-app-db.xxxxxx.ap-northeast-1.rds.amazonaws.com"
```

<details>
<summary><b>コンソールで各リソースの値を確認する方法</b></summary>

`terraform output` が使えない場合、以下でコンソールから各値を取得できます:

| 値 | コンソールでの確認方法 |
|----|----------------------|
| ALB DNS 名 | EC2 → ロードバランサー → test-app-alb → 「DNS 名」 |
| CloudFront Distribution ID | CloudFront → ディストリビューション一覧 → 「ID」列 |
| CloudFront ドメイン名 | CloudFront → ディストリビューション一覧 → 「ドメイン名」列 |
| Deploy Role ARN | IAM → ロール → test-app-github-actions-deploy → 「ARN」 |
| ECR リポジトリ URL | ECR → リポジトリ → test-app/backend → 「URI」 |
| ECS クラスタ名 | ECS → クラスター → 名前列 |
| S3 バケット名 | S3 → バケット一覧 → test-app-frontend-production |
| RDS エンドポイント | RDS → データベース → test-app-db → 「接続とセキュリティ」→「エンドポイント」 |

</details>

### 5.7 CORS 設定の更新

CloudFront ドメインが判明したら `terraform.tfvars` を更新:

```hcl
cors_origins = ["https://d1234567890.cloudfront.net"]
```

```bash
terraform plan -out=tfplan && terraform apply tfplan
```

---

## Phase 6: 初回デプロイ (手動)

GitHub Actions による自動デプロイの前に、初回は手動でイメージを push し、DB マイグレーションを実行します。

### 6.1 ECR ログイン

<details>
<summary><b>CLI で実行する場合</b></summary>

```bash
ECR_URL=$(terraform output -raw ecr_repository_url)
ACCOUNT_ID=$(aws sts get-caller-identity --query 'Account' --output text)
REGION="ap-northeast-1"

# ECR にログイン (フェデレーティッドユーザーの一時認証情報を使用)
aws ecr get-login-password --region ${REGION} | \
  docker login --username AWS --password-stdin \
  "${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com"
```

> **注意**: ECR ログイントークンは 12 時間有効ですが、`aws-azure-login` のセッションが 1 時間なので、Docker push はログイン直後に実行してください。

</details>

<details>
<summary><b>コンソールで確認する場合</b></summary>

ECR への Docker push は CLI が必須ですが、コンソールでリポジトリの存在と push コマンドを確認できます:

1. **ECR コンソールを開く**
   ```
   AWS コンソール → サービス → Elastic Container Registry
   ```

2. **リポジトリを確認**
   ```
   プライベートリポジトリ → test-app/backend が表示されることを確認
   ```

3. **Push コマンドの取得**
   ```
   リポジトリをクリック → 右上「プッシュコマンドの表示」
   → macOS / Linux タブのコマンドをコピーしてターミナルで実行
   ```

</details>

### 6.2 バックエンドイメージのビルドと push

```bash
cd /Users/haytakeda/projects/test_app

# 本番イメージをビルド
docker build -t test-app-backend:initial -f backend/Dockerfile.prod backend/

# タグ付け
docker tag test-app-backend:initial "${ECR_URL}:initial"

# push
docker push "${ECR_URL}:initial"
```

### 6.3 DB マイグレーション

ECS Run Task でマイグレーションを実行します。サブネット ID とセキュリティグループ ID が必要です:

<details>
<summary><b>CLI で実行する場合</b></summary>

```bash
# サブネット ID を取得
PRIVATE_SUBNETS=$(aws ec2 describe-subnets \
  --filters "Name=tag:Name,Values=test-app-private-*" \
  --query 'Subnets[*].SubnetId' --output text | tr '\t' ',')

# ECS セキュリティグループ ID を取得
ECS_SG=$(aws ec2 describe-security-groups \
  --filters "Name=group-name,Values=test-app-ecs-sg" \
  --query 'SecurityGroups[0].GroupId' --output text)

echo "Subnets: ${PRIVATE_SUBNETS}"
echo "Security Group: ${ECS_SG}"
```

```bash
# マイグレーション実行
aws ecs run-task \
  --cluster test-app-cluster \
  --task-definition test-app-backend \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={
    subnets=[${PRIVATE_SUBNETS}],
    securityGroups=[${ECS_SG}],
    assignPublicIp=DISABLED
  }" \
  --overrides '{
    "containerOverrides": [{
      "name": "backend",
      "command": ["alembic", "upgrade", "head"]
    }]
  }'
```

タスクの状態を確認:

```bash
# 直近のタスクを確認
aws ecs list-tasks --cluster test-app-cluster --desired-status STOPPED --query 'taskArns[0]' --output text | \
  xargs -I {} aws ecs describe-tasks --cluster test-app-cluster --tasks {} --query 'tasks[0].{status:lastStatus,exit:containers[0].exitCode}'
```

</details>

<details>
<summary><b>コンソールで実行する場合</b></summary>

1. **サブネット ID とセキュリティグループ ID を取得**
   ```
   VPC → サブネット → フィルタ: Name = test-app-private-*
   → サブネット ID をメモ (2つ)

   EC2 → セキュリティグループ → フィルタ: グループ名 = test-app-ecs-sg
   → セキュリティグループ ID をメモ
   ```

2. **ECS から Run Task を実行**
   ```
   ECS → クラスター → test-app-cluster
   → 「タスク」タブ → 「新しいタスクの実行」
   ```

3. **タスク設定**
   ```
   起動タイプ: FARGATE
   オペレーティングシステム: Linux/X86_64
   タスク定義: test-app-backend (最新リビジョン)
   ```

4. **ネットワーク設定**
   ```
   VPC: test-app-vpc
   サブネット: test-app-private-* (プライベートサブネットを選択)
   セキュリティグループ: test-app-ecs-sg
   パブリック IP の自動割り当て: DISABLED (オフ)
   ```

5. **コンテナのオーバーライド**
   ```
   「コンテナのオーバーライド」を展開
   → コンテナ名: backend
   → コマンドのオーバーライド: alembic,upgrade,head
      (カンマ区切りで入力)
   ```

6. **「タスクを実行」をクリック**

7. **結果の確認**
   ```
   タスク一覧 → 実行したタスクをクリック
   → ステータスが「STOPPED」になるまで待機
   → 「コンテナ」セクション → 終了コード: 0 なら成功
   → 失敗時は「ログ」タブでエラーを確認
   ```

</details>

### 6.4 ECS サービスの初回起動確認

<details>
<summary><b>CLI で確認する場合</b></summary>

```bash
aws ecs describe-services \
  --cluster test-app-cluster \
  --services test-app-backend \
  --query 'services[0].{desired:desiredCount,running:runningCount,status:status}'
```

タスクが起動しない場合はログを確認:

```bash
aws logs tail /ecs/test-app/backend --since 10m
```

</details>

<details>
<summary><b>コンソールで確認する場合</b></summary>

1. **ECS コンソールを開く**
   ```
   AWS コンソール → サービス → Elastic Container Service
   ```

2. **クラスターを確認**
   ```
   クラスター → test-app-cluster をクリック
   ```

3. **サービスの状態を確認**
   ```
   サービスタブ → test-app-backend をクリック
   確認項目:
     - ステータス: ACTIVE
     - 実行中のタスク: 1 (希望数と一致)
     - デプロイメント: PRIMARY が 1 つのみ
   ```

4. **タスクが起動しない場合のデバッグ**
   ```
   サービス詳細 → 「イベント」タブ
   → 最新のイベントで停止理由を確認

   タスクタブ → 停止済みタスクをクリック
   → 「停止理由」と「コンテナ」セクションを確認
   ```

5. **ログの確認**
   ```
   タスク詳細 → 「ログ」タブ
   または:
   AWS コンソール → CloudWatch → ロググループ → /ecs/test-app/backend
   → 最新のログストリームをクリック
   ```

</details>

---

## Phase 7: GitHub Actions の設定

### 7.1 GitHub Environment の作成

```
GitHub リポジトリ → Settings → Environments → New environment
  Name: production
  (任意) Protection rules:
    - Required reviewers: 有効にして承認者を追加
```

### 7.2 Secrets の登録

`Settings → Secrets and variables → Actions → New repository secret` で以下を登録:

| Secret 名 | 値の取得元 |
|-----------|-----------|
| `AWS_DEPLOY_ROLE_ARN` | `terraform output deploy_role_arn` |
| `CLOUDFRONT_DISTRIBUTION_ID` | `terraform output cloudfront_distribution_id` |

```bash
# 値を確認
terraform output deploy_role_arn
terraform output cloudfront_distribution_id
```

### 7.3 デプロイワークフローの確認

`.github/workflows/deploy.yml` が以下を実行します:

1. **テスト**: バックエンド (pytest) + フロントエンド (lint + build)
2. **バックエンドデプロイ**: ECR push → タスク定義更新 → ECS サービス更新
3. **フロントエンドデプロイ**: `npm run build` → S3 sync → CloudFront invalidation

GitHub Actions は **OIDC フェデレーション** で AWS に認証します。あなたの SSO 認証情報とは独立しています。

### 7.4 初回 CI/CD の実行

```bash
git add .
git commit -m "deploy: configure production infrastructure"
git push origin main
```

GitHub の Actions タブで `deploy` ワークフローの実行状況を確認します。

---

## Phase 8: 動作確認

### 8.1 バックエンド API

<details>
<summary><b>CLI で確認する場合</b></summary>

```bash
ALB_DNS=$(terraform output -raw alb_dns_name)
curl -s "http://${ALB_DNS}/api/health/live" | jq .
# → {"status": "ok"}

curl -s "http://${ALB_DNS}/api/health/ready" | jq .
# → {"status": "ok", "database": "connected", ...}
```

</details>

<details>
<summary><b>コンソールで確認する場合</b></summary>

1. **ALB の DNS 名を取得**
   ```
   AWS コンソール → EC2 → ロードバランサー
   → test-app-alb をクリック
   → 「DNS 名」をコピー
   ```

2. **ブラウザでアクセス**
   ```
   http://{ALBのDNS名}/api/health/live
   → {"status": "ok"} が表示されれば成功
   ```

3. **ターゲットグループのヘルスチェック**
   ```
   EC2 → ターゲットグループ → test-app-tg
   → 「ターゲット」タブで Healthy が 1 以上
   ```

</details>

### 8.2 フロントエンド

<details>
<summary><b>CLI で確認する場合</b></summary>

```bash
CF_DOMAIN=$(terraform output -raw cloudfront_domain_name)
echo "https://${CF_DOMAIN}"
# ブラウザでアクセス
```

</details>

<details>
<summary><b>コンソールで確認する場合</b></summary>

1. **CloudFront コンソールを開く**
   ```
   AWS コンソール → サービス → CloudFront
   ```

2. **ディストリビューションを確認**
   ```
   ディストリビューション一覧 → 「ドメイン名」列の d1234567890.cloudfront.net をコピー
   ステータス: Deployed (デプロイ済み) であることを確認
   ```

3. **ブラウザでアクセス**
   ```
   https://d1234567890.cloudfront.net
   → React アプリが表示されれば成功
   ```

</details>

### 8.3 ECS サービスの安定性確認

<details>
<summary><b>CLI で確認する場合</b></summary>

```bash
aws ecs describe-services \
  --cluster test-app-cluster \
  --services test-app-backend \
  --query 'services[0].{
    status: status,
    desired: desiredCount,
    running: runningCount,
    deployments: length(deployments)
  }'
```

</details>

<details>
<summary><b>コンソールで確認する場合</b></summary>

1. **ECS コンソール**
   ```
   ECS → クラスター → test-app-cluster → サービス → test-app-backend
   ```

2. **確認項目**
   ```
   デプロイメントタブ:
     - PRIMARY デプロイメントが 1 つのみ
     - 実行中タスク数 = 希望タスク数 = 1

   ヘルスチェックタブ:
     - タスクが「Healthy」であること

   メトリクスタブ:
     - CPU / メモリ使用率が安定していること
   ```

3. **RDS の接続確認**
   ```
   AWS コンソール → RDS → データベース
   → test-app-db をクリック
   → ステータス: 「利用可能」
   → 接続とセキュリティ: エンドポイントを確認
   ```

</details>

---

## トラブルシューティング

### 認証関連

| 症状 | 原因 | 対処 |
|------|------|------|
| `ExpiredToken: The security token included in the request is expired` | セッション 1 時間経過 | `aws-azure-login --mode=gui` で再認証 |
| `An error occurred (ExpiredTokenException)` | 同上 | 同上 |
| `Unable to locate credentials` | 認証未実施 / credentials が空 | `aws-azure-login --mode=gui` を実行 |
| `Could not load credentials from any providers` | 同上 | 同上 |
| aws-azure-login でブラウザが開かない | GUI モード非対応 | `--mode=gui` を確認、Puppeteer 依存チェック |
| `Assuming role ...` 後にエラー | SAML ロールの権限不足 | 組織管理者に確認 |
| コンソールで「セッションの有効期限切れ」表示 | コンソールセッション期限切れ | Azure ポータルから再ログイン |
| コンソールで「権限がありません」表示 | ロールの権限不足 | 組織管理者にロールポリシー変更を依頼 |
| コンソールで別リージョンのリソースが見えない | リージョン未選択 | 右上のリージョンセレクターで `ap-northeast-1` を選択 |

### Terraform 関連

| 症状 | 原因 | 対処 |
|------|------|------|
| `Error configuring S3 Backend: no valid credential sources` | 認証未実施または期限切れ | `aws-azure-login --mode=gui` 後に `terraform init` |
| `Error: Incompatible provider version` | Terraform/Provider バージョン | `terraform init -upgrade` |
| `Error: creating RDS DB Instance` | パラメータ不正 | `terraform.tfvars` の DB 設定確認 |
| `Error: creating ECS Service: InvalidParameterException` | イメージが ECR に存在しない | Phase 6.2 の手動 push を先に実施 |

### Docker / ECR 関連

| 症状 | 原因 | 対処 |
|------|------|------|
| `no basic auth credentials` | ECR ログインの期限切れ (12 時間) | `aws ecr get-login-password` を再実行 |
| `denied: Your authorization token has expired` | 同上 | 同上 |
| `Error response from daemon: pull access denied` | ECR リポジトリが存在しない | `terraform apply` が完了しているか確認 |

### GitHub Actions 関連

| 症状 | 原因 | 対処 |
|------|------|------|
| `Not authorized to perform: sts:AssumeRoleWithWebIdentity` | OIDC 設定不一致 | `github_org` / `github_repo` を確認して `terraform apply` |
| `Error: Environment 'production' not found` | Environment 未作成 | Phase 7.1 を実施 |
| `secret not found: AWS_DEPLOY_ROLE_ARN` | Secret 未登録 | Phase 7.2 を実施 |

### ECS 関連

<details>
<summary><b>CLI でデバッグする場合</b></summary>

```bash
# タスクの停止理由を確認
aws ecs list-tasks --cluster test-app-cluster --desired-status STOPPED | \
  jq -r '.taskArns[0]' | \
  xargs -I {} aws ecs describe-tasks --cluster test-app-cluster --tasks {} \
  --query 'tasks[0].{reason:stoppedReason,exit:containers[0].exitCode,lastStatus:lastStatus}'

# ログの確認
aws logs tail /ecs/test-app/backend --since 30m --follow
```

</details>

<details>
<summary><b>コンソールでデバッグする場合</b></summary>

1. **停止理由を確認**
   ```
   ECS → クラスター → test-app-cluster → サービス → test-app-backend
   → 「イベント」タブ: 直近のエラーメッセージを確認
   → 「タスク」タブ → フィルタ「停止済み」→ タスクをクリック
   → 「停止理由」と「コンテナ」セクションを確認
   ```

2. **ログを確認**
   ```
   タスク詳細 → 「ログ」タブ
   または:
   CloudWatch → ロググループ → /ecs/test-app/backend
   → 最新のログストリームをクリック
   ```

3. **よくある停止理由と対処**
   ```
   "Essential container in task exited"
     → コンテナがクラッシュ。ログでエラーを確認

   "Task failed ELB health checks"
     → ヘルスチェックパス /api/health/live が応答しない
     → EC2 → ターゲットグループ → ヘルスチェック設定を確認

   "CannotPullContainerError"
     → ECR にイメージが存在しない、またはタスク実行ロールの権限不足

   "ResourceInitializationError: unable to pull secrets"
     → Secrets Manager のアクセス権限不足
     → タスク実行ロールのポリシーを確認
   ```

</details>

---

## 認証情報の有効期限と更新

### セッションの有効期限

| 項目 | 有効期限 | 備考 |
|------|-----------|------|
| aws-azure-login セッション | **1 時間** (設定値) | `--configure` で最大 12 時間に変更可 |
| ECR ログイントークン | 12 時間 | 固定 |
| コンソールセッション | 1 時間 | SAML セッションに準拠 |

### 認証更新のベストプラクティス

```bash
# 作業開始時に必ず実行
aws-azure-login --mode=gui

# セッションの有効性確認 (スクリプト化推奨)
aws sts get-caller-identity 2>/dev/null || \
  (echo "Session expired. Re-authenticating..." && aws-azure-login --mode=gui)
```

### シェルエイリアス (推奨)

`~/.zshrc` に追加:

```bash
# AWS 再認証
alias awslogin='aws-azure-login --mode=gui'

# 認証確認付き Terraform
alias tf='aws sts get-caller-identity >/dev/null 2>&1 || aws-azure-login --mode=gui; terraform'

# ECR ログイン
alias ecr-login='aws ecr get-login-password --region ap-northeast-1 | docker login --username AWS --password-stdin $(aws sts get-caller-identity --query Account --output text).dkr.ecr.ap-northeast-1.amazonaws.com'
```

---

## クイックリファレンス: コマンド一覧

```bash
# === 認証 ===
aws-azure-login --mode=gui
aws sts get-caller-identity

# === Terraform ===
cd infrastructure/environments/production
terraform init
terraform plan -out=tfplan
terraform apply tfplan
terraform output

# === Docker / ECR ===
ACCOUNT_ID=$(aws sts get-caller-identity --query 'Account' --output text)
aws ecr get-login-password --region ap-northeast-1 | \
  docker login --username AWS --password-stdin \
  ${ACCOUNT_ID}.dkr.ecr.ap-northeast-1.amazonaws.com

docker build -t test-app-backend -f backend/Dockerfile.prod backend/
docker tag test-app-backend:latest ${ECR_URL}:${TAG}
docker push ${ECR_URL}:${TAG}

# === ECS 操作 ===
aws ecs describe-services --cluster test-app-cluster --services test-app-backend
aws logs tail /ecs/test-app/backend --since 10m --follow

# === デプロイ (通常は git push で自動) ===
git push origin main
```

---

## リソースの削除 (不要になったら)

> ⚠️ **この操作は不可逆です。** 全データが削除されます。

<details>
<summary><b>CLI で実行する場合</b></summary>

```bash
cd infrastructure/environments/production

# 再認証
aws-azure-login --mode=gui

# 事前確認
terraform plan -destroy

# 削除実行
terraform destroy
```

削除後に残るリソース (手動で削除):
- S3 バケット (terraform state 用) — バージョニング有効の場合、全バージョンを削除してからバケット削除
- DynamoDB テーブル (terraform lock 用)
- Secrets Manager のシークレット (30 日間の回復期間後に自動削除)
- CloudWatch ロググループ (保持期間後に自動削除)

```bash
# State バケットの削除 (全バージョン削除が必要)
aws s3api delete-objects --bucket ${BUCKET_NAME} \
  --delete "$(aws s3api list-object-versions --bucket ${BUCKET_NAME} \
  --query '{Objects: Versions[].{Key: Key, VersionId: VersionId}}' --output json)"
aws s3api delete-bucket --bucket ${BUCKET_NAME}

# DynamoDB テーブル削除
aws dynamodb delete-table --table-name test-app-terraform-lock
```

</details>

<details>
<summary><b>コンソールから手動削除する場合</b></summary>

> `terraform destroy` は CLI 必須です。コンソールからの完全削除は推奨しませんが、残存リソースのクリーンアップは以下で行えます:

1. **S3 バケット (State 用) の削除**
   ```
   S3 → test-app-terraform-state-{ID} を選択
   → 「空にする」をクリック (バージョニング含む全オブジェクトが削除)
   → 「削除」をクリック
   ```

2. **DynamoDB テーブルの削除**
   ```
   DynamoDB → テーブル → test-app-terraform-lock を選択
   → 「削除」をクリック
   → テーブル名を入力して確認
   ```

3. **Secrets Manager のシークレット削除**
   ```
   Secrets Manager → test-app/jwt-secret をクリック
   → アクション → 「シークレットを削除」
   → 復元期間: 7 日 (最短) または即時削除
   ```

4. **CloudWatch ロググループの削除**
   ```
   CloudWatch → ロググループ → /ecs/test-app/backend
   → アクション → 「ロググループの削除」
   ```

</details>

---

## 付録: aws-azure-login の詳細設定

### セッション時間を延長する

Terraform apply でタイムアウトする場合、セッション時間を延長できます:

```bash
aws-azure-login --configure
# ? Default Session Duration Hours (up to 12): 4  ← 4 時間に変更
```

> 管理者が許可している最大値を超えるとエラーになります。

### 名前付きプロファイルを使う場合

複数の AWS アカウントを使い分ける場合:

```bash
# 別プロファイルで設定
aws-azure-login --configure --profile test-app-prod

# ログイン時にプロファイル指定
aws-azure-login --mode=gui --profile test-app-prod

# Terraform 実行時
export AWS_PROFILE=test-app-prod
terraform plan
```

### 現在の環境情報

| 項目 | 値 |
|------|----|
| AWS アカウント ID | `146062274667` |
| ロール | `arn:aws:iam::146062274667:role/DCSLayer0/AWS_146062274667_Admin` |
| リージョン | `ap-northeast-1` |
| Azure Tenant ID | `36da45f1-dd2c-4d1f-af13-5abe46b99921` |
| ユーザー | `a-haytakeda@tohmatsu.co.jp` |
