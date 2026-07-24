variable "project_name" {
  description = "プロジェクト名"
  type        = string
}

variable "environment" {
  description = "環境名"
  type        = string
}

variable "vpc_id" {
  description = "VPC の ID"
  type        = string
}

variable "public_subnet_ids" {
  description = "パブリックサブネットの ID リスト"
  type        = list(string)
}

variable "certificate_arn" {
  description = "ACM 証明書の ARN（HTTPS 用）"
  type        = string
}
