variable "project_name" {
  description = "プロジェクト名"
  type        = string
}

variable "aws_region" {
  description = "AWS リージョン"
  type        = string
  default     = "ap-northeast-1"
}

variable "vpc_cidr" {
  description = "VPC CIDR ブロック"
  type        = string
  default     = "10.0.0.0/16"
}

variable "availability_zones" {
  description = "アベイラビリティゾーン"
  type        = list(string)
  default     = ["ap-northeast-1a", "ap-northeast-1c"]
}

variable "certificate_arn" {
  description = "ALB 用 ACM 証明書 ARN"
  type        = string
  default     = ""
}

variable "image_tag" {
  description = "デプロイする Docker イメージのタグ"
  type        = string
  default     = "latest"
}

variable "task_cpu" {
  description = "ECS タスク CPU"
  type        = number
  default     = 256
}

variable "task_memory" {
  description = "ECS タスクメモリ (MB)"
  type        = number
  default     = 512
}

variable "desired_count" {
  description = "ECS サービス希望タスク数"
  type        = number
  default     = 1
}

variable "db_instance_class" {
  description = "RDS インスタンスクラス"
  type        = string
  default     = "db.t3.micro"
}

variable "db_allocated_storage" {
  description = "RDS 初期ストレージ (GB)"
  type        = number
  default     = 20
}

variable "db_max_storage" {
  description = "RDS 最大ストレージ (GB)"
  type        = number
  default     = 100
}

variable "db_name" {
  description = "データベース名"
  type        = string
  default     = "app"
}

variable "db_username" {
  description = "DB マスターユーザー名"
  type        = string
  default     = "postgres"
}

variable "multi_az" {
  description = "RDS マルチ AZ"
  type        = bool
  default     = false
}

variable "jwt_secret_arn" {
  description = "JWT シークレットの Secrets Manager ARN"
  type        = string
}

variable "cors_origins" {
  description = "CORS 許可オリジン"
  type        = list(string)
  default     = []
}

variable "frontend_domain_name" {
  description = "フロントエンドドメイン名（空文字で CloudFront デフォルト）"
  type        = string
  default     = ""
}

variable "frontend_certificate_arn" {
  description = "フロントエンド用 ACM 証明書 ARN（us-east-1、空文字でデフォルト）"
  type        = string
  default     = ""
}

variable "github_org" {
  description = "GitHub オーナー名"
  type        = string
}

variable "github_repo" {
  description = "GitHub リポジトリ名"
  type        = string
}
