# AWS デプロイ追加作業ガイド — コードの外で必要な全ステップ

> **対象読者**: Terraform コードと GitHub Actions ワークフローは完成したが、実際にデプロイするために何が足りないか知りたい方  
> **前提**: [task3-deploy-explainer.md](./task3-deploy-explainer.md) を読み、2 段階デプロイの全体像を理解していること

---

## 目次

- [全体チェックリスト](#全体チェックリスト)
- [Phase 1: AWS アカウントの準備](#phase-1-aws-アカウントの準備)
- [Phase 2: Terraform State の準備](#phase-2-terraform-state-の準備)
- [Phase 3: シークレットの作成](#phase-3-シークレットの作成)
- [Phase 4: Terraform の実行](#phase-4-terraform-の実行)
- [Phase 5: GitHub リポジトリの設定](#phase-5-github-リポジトリの設定)
- [Phase 6: 初回デプロイの実行](#phase-6-初回デプロイの実行)
- [Phase 7: 動作確認](#phase-7-動作確認)
- [トラブルシューティング](#トラブルシューティング)
- [コスト管理](#コスト管理)
- [リソースの削除（使い終わったら）](#リソースの削除使い終わったら)

---

## 全体チェックリスト

以下をすべて完了すると、`git push` でアプリが AWS にデプロイされるようになります。

```
Phase 1: AWS アカウント
  [ ] AWS アカウント作成
  [ ] MFA 有効化
  [ ] IAM ユーザー作成 (admin)
  [ ] AWS CLI インストール + aws configure
  [ ] Budget アラート設定 ($10)
  [ ] Terraform インストール

Phase 2: Terraform State
  [ ] S3 バケット作成 (terraform state 用)
  [ ] DynamoDB テーブル作成 (state lock 用)
  [ ] backend.tf のバケット名を更新

Phase 3: シークレット
  [ ] JWT シークレットを Secrets Manager に作成
  [ ] terraform.tfvars を更新

Phase 4: Terraform 実行
  [ ] terraform init
  [ ] terraform plan (エラーなし確認)
  [ ] terraform apply
  [ ] terraform output の値を控える

Phase 5: GitHub 設定
  [ ] Environment "production" を作成
  [ ] Secret: AWS_DEPLOY_ROLE_ARN を登録
  [ ] Secret: CLOUDFRONT_DISTRIBUTION_ID を登録

Phase 6: 初回デプロイ
  [ ] 初回イメージを手動で ECR に push
  [ ] DB マイグレーションを手動実行
  [ ] git push → deploy.yml が成功

Phase 7: 動作確認
  [ ] ALB DNS でバックエンド API にアクセス
  [ ] CloudFront URL でフロントエンドにアクセス
```

---

## Phase 1: AWS アカウントの準備

> 詳細は [task2-aws-deploy-guide.md](./task2-aws-deploy-guide.md) の「事前準備」セクションを参照。

### 1.1 AWS アカウント作成 + MFA

1. [aws.amazon.com](https://aws.amazon.com/) でアカウント作成
2. ルートユーザーに MFA を有効化（Google Authenticator / 1Password 等）

### 1.2 IAM ユーザー作成

```
AWS コンソール → IAM → ユーザー → 作成
  ユーザー名: admin
  ポリシー: AdministratorAccess
  コンソールアクセス: 有効
  → アクセスキーを作成 (CLI 用)
```

### 1.3 AWS CLI + Terraform インストール

```bash
# macOS
brew install awscli
brew tap hashicorp/tap && brew install hashicorp/tap/terraform

# 認証設定
aws configure
# Access Key ID:     [IAM ユーザーのキー]
# Secret Access Key: [IAM ユーザーのシークレット]
# Region:            ap-northeast-1
# Output:            json

# 確認
aws sts get-caller-identity
terraform --version
```

### 1.4 Budget アラート

```
AWS コンソール → Billing → Budgets → Create
  Type: Cost budget
  Amount: $10/月
  通知: メールアドレスを設定
```

---

## Phase 2: Terraform State の準備

Terraform は「現在のインフラの状態」を **state ファイル** に記録します。このファイルを安全に保管するため、S3 バケットを使います。

### 2.1 S3 バケット作成

```
AWS コンソール → S3 → バケットを作成
  バケット名: test-app-terraform-state-{アカウントID}
  リージョン: ap-northeast-1
  バージョニング: 有効
  暗号化: SSE-S3
  パブリックアクセス: すべてブロック
```

### 2.2 DynamoDB テーブル作成

```
AWS コンソール → DynamoDB → テーブルを作成
  テーブル名: test-app-terraform-lock
  パーティションキー: LockID (文字列)
  その他: デフォルト
```

### 2.3 backend.tf のバケット名を更新

`infrastructure/environments/production/backend.tf` のバケット名を、作成した実際のバケット名に変更します:

```hcl
terraform {
  backend "s3" {
    bucket         = "test-app-terraform-state-123456789012"  # ← 実際のバケット名
    key            = "production/terraform.tfstate"
    region         = "ap-northeast-1"
    encrypt        = true
    dynamodb_table = "test-app-terraform-lock"
  }
}
```

### 2.4 確認

```bash
aws s3 ls s3://test-app-terraform-state-{アカウントID}/ --region ap-northeast-1
aws dynamodb describe-table --table-name test-app-terraform-lock --query 'Table.TableStatus'
# → "ACTIVE"
```

---

## Phase 3: シークレットの作成

### 3.1 JWT シークレット

アプリの認証トークンに使う秘密鍵を Secrets Manager に保存します:

```bash
# ランダムな秘密鍵を生成して Secrets Manager に保存
aws secretsmanager create-secret \
  --name "test-app/jwt-secret" \
  --description "JWT signing key for test-app" \
  --secret-string "$(openssl rand -hex 32)" \
  --region ap-northeast-1

# 作成された ARN を控える（terraform.tfvars に設定する）
aws secretsmanager describe-secret \
  --secret-id "test-app/jwt-secret" \
  --query 'ARN' --output text
```

### 3.2 terraform.tfvars の更新

`infrastructure/environments/production/terraform.tfvars` に実際の値を設定します:

```hcl
# GitHub (自分のリポジトリ情報に変更)
github_org  = "your-actual-github-username"
github_repo = "test_app"

# JWT シークレット (Phase 3.1 で取得した ARN)
jwt_secret_arn = "arn:aws:secretsmanager:ap-northeast-1:123456789012:secret:test-app/jwt-secret-XXXXXX"

# CORS (CloudFront の URL。terraform apply 後に更新)
cors_origins = ["https://xxxxxxxx.cloudfront.net"]
```

> **ACM 証明書について**: カスタムドメインを使わない場合は `certificate_arn` は不要です。ALB には暫定的にダミーの自己署名証明書を設定するか、HTTP のみで動作確認した後にドメインを設定してください。

---

## Phase 4: Terraform の実行

### 4.1 初期化

```bash
cd infrastructure/environments/production
terraform init
```

出力例:
```
Initializing modules...
Initializing the backend...
Initializing provider plugins...
Terraform has been successfully initialized!
```

### 4.2 プラン確認

```bash
terraform plan
```

作成されるリソース数が表示されます。エラーがないことを確認してください。

### 4.3 適用

```bash
terraform apply
```

`Do you want to perform these actions?` と聞かれたら `yes` と入力します。  
5〜10 分程度かかります（RDS の作成に時間がかかります）。

### 4.4 出力値の確認

```bash
terraform output
```

以下の値を控えます（Phase 5 で使用）:

```
deploy_role_arn            = "arn:aws:iam::123456789012:role/test-app-github-actions-deploy"
cloudfront_distribution_id = "E1234567890ABC"
ecr_repository_url         = "123456789012.dkr.ecr.ap-northeast-1.amazonaws.com/test-app/backend"
alb_dns_name               = "test-app-alb-123456.ap-northeast-1.elb.amazonaws.com"
cloudfront_domain_name     = "d1234567890.cloudfront.net"
```

### 4.5 CORS の更新

CloudFront ドメインが判明したら、`terraform.tfvars` の `cors_origins` を更新して再度 `terraform apply`:

```hcl
cors_origins = ["https://d1234567890.cloudfront.net"]
```

```bash
terraform apply
```

---

## Phase 5: GitHub リポジトリの設定

### 5.1 Environment の作成

```
GitHub → Settings → Environments → New environment
  Name: production
  Protection rules (推奨):
    - Required reviewers: 1人以上
    - Wait timer: 0分
```

### 5.2 Secrets の登録

```
GitHub → Settings → Secrets and variables → Actions → New repository secret

1. Name: AWS_DEPLOY_ROLE_ARN
   Value: arn:aws:iam::123456789012:role/test-app-github-actions-deploy
   (Phase 4.4 の terraform output の値)

2. Name: CLOUDFRONT_DISTRIBUTION_ID
   Value: E1234567890ABC
   (Phase 4.4 の terraform output の値)
```

---

## Phase 6: 初回デプロイの実行

### 6.1 初回イメージの手動 push

ECS サービスはタスク定義にイメージが必要です。初回は手動で ECR にイメージを push します:

```bash
# ECR にログイン
aws ecr get-login-password --region ap-northeast-1 | \
  docker login --username AWS --password-stdin \
  123456789012.dkr.ecr.ap-northeast-1.amazonaws.com

# イメージをビルド
docker build -t test-app-backend -f backend/Dockerfile.prod backend/

# タグ付け
docker tag test-app-backend:latest \
  123456789012.dkr.ecr.ap-northeast-1.amazonaws.com/test-app/backend:initial

# push
docker push \
  123456789012.dkr.ecr.ap-northeast-1.amazonaws.com/test-app/backend:initial
```

### 6.2 DB マイグレーション

初回はローカルから直接実行するか、ECS Run Task で実行します:

```bash
# ECS Run Task でマイグレーション実行
aws ecs run-task \
  --cluster test-app-cluster \
  --task-definition test-app-backend \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={
    subnets=[subnet-xxx,subnet-yyy],
    securityGroups=[sg-xxx]
  }" \
  --overrides '{
    "containerOverrides": [{
      "name": "backend",
      "command": ["alembic", "upgrade", "head"]
    }]
  }'
```

> サブネット ID とセキュリティグループ ID は `terraform output` や AWS コンソールで確認してください。

### 6.3 GitHub Actions でのデプロイ

```bash
git add .
git commit -m "deploy: initial deployment"
git push origin main
```

GitHub の Actions タブで `deploy` ワークフローが実行されることを確認します。

---

## Phase 7: 動作確認

### 7.1 バックエンド API

```bash
# ALB の DNS 名でヘルスチェック
curl https://test-app-alb-123456.ap-northeast-1.elb.amazonaws.com/api/health/ready
# → {"status": "ok", "database": "connected", ...}
```

### 7.2 フロントエンド

ブラウザで CloudFront の URL にアクセス:
```
https://d1234567890.cloudfront.net
```

---

## トラブルシューティング

### terraform apply でエラーが出る

| エラー | 原因 | 対処 |
|--------|------|------|
| `Error: No valid credential sources found` | AWS CLI 未設定 | `aws configure` を実行 |
| `Error: S3 bucket does not exist` | state バケット未作成 | Phase 2 を実行 |
| `Error: creating RDS DB Instance: InvalidParameterValue` | パラメータ値の誤り | `terraform.tfvars` を確認 |
| `Error: certificate_arn is required` | ACM 証明書未設定 | ドメインなしで始める場合は ALB モジュールを一時的に調整 |

### GitHub Actions が失敗する

| エラー | 原因 | 対処 |
|--------|------|------|
| `Not authorized to perform: sts:AssumeRoleWithWebIdentity` | OIDC 設定の不一致 | `github_org` / `github_repo` を確認 |
| `AWS_DEPLOY_ROLE_ARN secret not set` | Secret 未登録 | Phase 5.2 を実行 |
| `no basic auth credentials` | ECR ログイン失敗 | IAM ロールの権限を確認 |

### ECS サービスが起動しない

```bash
# イベントログを確認
aws ecs describe-services \
  --cluster test-app-cluster \
  --services test-app-backend \
  --query 'services[0].events[:5]'

# タスクの停止理由を確認
aws ecs describe-tasks \
  --cluster test-app-cluster \
  --tasks $(aws ecs list-tasks --cluster test-app-cluster --query 'taskArns[0]' --output text) \
  --query 'tasks[0].stoppedReason'

# CloudWatch Logs を確認
aws logs tail /ecs/test-app/backend --follow
```

---

## コスト管理

### 月額コスト見積もり（最小構成）

| サービス | 構成 | 月額目安 |
|---------|------|---------|
| ECS Fargate | 0.25 vCPU + 0.5 GB RAM × 1 タスク | ~$10 |
| RDS | db.t3.micro (Free Tier 対象) | $0 (初年度) / ~$15 |
| ALB | 1 台 | ~$18 |
| S3 | 数 MB | ~$0 |
| CloudFront | 低トラフィック | ~$0 |
| VPC エンドポイント | Interface × 4 | ~$30 |
| **合計** | | **~$58〜73/月** |

> **コスト削減のポイント**: 
> - NAT Gateway ($32/AZ/月) を VPC エンドポイントに置き換え済み
> - RDS は Free Tier 対象インスタンスを使用
> - ECS は最小スペック構成

### 使わないときの停止

開発中は ECS サービスを停止してコストを削減できます:

```bash
# 停止
aws ecs update-service --cluster test-app-cluster --service test-app-backend --desired-count 0

# 再開
aws ecs update-service --cluster test-app-cluster --service test-app-backend --desired-count 1
```

---

## リソースの削除（使い終わったら）

```bash
cd infrastructure/environments/production

# 全リソースを削除
terraform destroy
# → "yes" と入力

# state 管理用リソースも手動で削除
aws s3 rb s3://test-app-terraform-state-{アカウントID} --force
aws dynamodb delete-table --table-name test-app-terraform-lock
```

> ⚠️ `terraform destroy` は**すべてのリソースを削除**します。データベースのデータも失われます。本番運用中は絶対に実行しないでください。
