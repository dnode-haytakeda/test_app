# 本番環境のパラメータ値
# ⚠️ 実際のデプロイ前に各値を自身の環境に合わせて変更してください

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
github_org  = "dnode-haytakeda"
github_repo = "test_app"

# JWT シークレット (Phase 4.1 で取得した ARN)
jwt_secret_arn = "arn:aws:secretsmanager:ap-northeast-1:146062274667:secret:test-app/jwt-secret-PtuCxk"

# CORS 許可オリジン (Phase 5.7)
cors_origins = ["https://d2f6421cgskxko.cloudfront.net"]

# ACM 証明書 (ドメインなしの場合はコメントアウトのまま)
# certificate_arn          = "arn:aws:acm:ap-northeast-1:ACCOUNT_ID:certificate/CERT_ID"
# frontend_domain_name     = "app.example.com"
# frontend_certificate_arn = "arn:aws:acm:us-east-1:ACCOUNT_ID:certificate/CERT_ID"