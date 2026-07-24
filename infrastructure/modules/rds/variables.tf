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

variable "database_subnet_ids" {
  description = "DB サブネットの ID リスト"
  type        = list(string)
}

variable "ecs_security_group_id" {
  description = "ECS タスクのセキュリティグループ ID（DB への接続許可用）"
  type        = string
}

variable "db_instance_class" {
  description = "RDS インスタンスクラス"
  type        = string
  default     = "db.t3.micro"
}

variable "db_allocated_storage" {
  description = "初期ストレージ容量（GB）"
  type        = number
  default     = 20
}

variable "db_max_storage" {
  description = "Auto Scaling 最大ストレージ容量（GB）"
  type        = number
  default     = 100
}

variable "db_name" {
  description = "データベース名"
  type        = string
  default     = "app"
}

variable "db_username" {
  description = "マスターユーザー名"
  type        = string
  default     = "postgres"
}

variable "multi_az" {
  description = "マルチ AZ 配置（本番は true 推奨）"
  type        = bool
  default     = false
}
