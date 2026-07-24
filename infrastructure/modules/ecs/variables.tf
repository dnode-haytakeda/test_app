variable "project_name" {
  description = "プロジェクト名"
  type        = string
}

variable "environment" {
  description = "環境名 (production / staging)"
  type        = string
}

variable "vpc_id" {
  description = "VPC の ID"
  type        = string
}

variable "private_subnet_ids" {
  description = "プライベートサブネットの ID リスト"
  type        = list(string)
}

variable "ecr_repository_url" {
  description = "ECR リポジトリの URL"
  type        = string
}

variable "image_tag" {
  description = "デプロイする Docker イメージのタグ"
  type        = string
  default     = "latest"
}

variable "alb_security_group_id" {
  description = "ALB セキュリティグループの ID"
  type        = string
}

variable "target_group_arn" {
  description = "ALB ターゲットグループの ARN"
  type        = string
}

variable "db_host" {
  description = "RDS エンドポイント"
  type        = string
}

variable "db_name" {
  description = "データベース名"
  type        = string
}

variable "db_secret_arn" {
  description = "DB パスワードの Secrets Manager ARN"
  type        = string
}

variable "jwt_secret_arn" {
  description = "JWT シークレットキーの Secrets Manager ARN"
  type        = string
}

variable "cors_origins" {
  description = "CORS 許可オリジンのリスト"
  type        = list(string)
  default     = []
}

variable "aws_region" {
  description = "AWS リージョン"
  type        = string
  default     = "ap-northeast-1"
}

variable "task_cpu" {
  description = "タスクの CPU ユニット（256 = 0.25 vCPU）"
  type        = number
  default     = 256
}

variable "task_memory" {
  description = "タスクのメモリ（MB）"
  type        = number
  default     = 512
}

variable "desired_count" {
  description = "ECS サービスの希望タスク数"
  type        = number
  default     = 1
}
