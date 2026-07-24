variable "project_name" {
  description = "プロジェクト名（リソース名のプレフィックス）"
  type        = string
}

variable "environment" {
  description = "環境名 (production / staging)"
  type        = string
}

variable "vpc_cidr" {
  description = "VPC の CIDR ブロック"
  type        = string
  default     = "10.0.0.0/16"
}

variable "availability_zones" {
  description = "使用するアベイラビリティゾーンのリスト"
  type        = list(string)
  default     = ["ap-northeast-1a", "ap-northeast-1c"]
}

variable "aws_region" {
  description = "AWS リージョン（VPC エンドポイントのサービス名に使用）"
  type        = string
  default     = "ap-northeast-1"
}
