variable "project_name" {
  description = "プロジェクト名"
  type        = string
}

variable "environment" {
  description = "環境名"
  type        = string
}

variable "github_org" {
  description = "GitHub オーナー名（ユーザー名 or 組織名）"
  type        = string
}

variable "github_repo" {
  description = "GitHub リポジトリ名"
  type        = string
}

variable "ecr_repository_arn" {
  description = "ECR リポジトリの ARN"
  type        = string
}

variable "ecs_execution_role_arn" {
  description = "ECS タスク実行ロールの ARN（iam:PassRole 用）"
  type        = string
  default     = ""
}

variable "ecs_task_role_arn" {
  description = "ECS タスクロールの ARN（iam:PassRole 用）"
  type        = string
  default     = ""
}

variable "frontend_bucket_arn" {
  description = "フロントエンド S3 バケットの ARN"
  type        = string
}

variable "cloudfront_distribution_arn" {
  description = "CloudFront ディストリビューションの ARN"
  type        = string
  default     = ""
}
