variable "project_name" {
  description = "プロジェクト名"
  type        = string
}

variable "environment" {
  description = "環境名"
  type        = string
}

variable "domain_name" {
  description = "フロントエンドのカスタムドメイン（空文字で CloudFront デフォルトドメインを使用）"
  type        = string
  default     = ""
}

variable "certificate_arn" {
  description = "ACM 証明書の ARN（us-east-1 で発行済み。空文字でデフォルト証明書を使用）"
  type        = string
  default     = ""
}
