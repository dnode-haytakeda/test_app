output "db_host" {
  description = "RDS エンドポイント"
  value       = aws_db_instance.main.address
}

output "db_port" {
  description = "RDS ポート"
  value       = aws_db_instance.main.port
}

output "db_secret_arn" {
  description = "Secrets Manager に保存されたマスターパスワードの ARN"
  value       = aws_db_instance.main.master_user_secret[0].secret_arn
}

output "db_name" {
  description = "データベース名"
  value       = aws_db_instance.main.db_name
}

output "rds_security_group_id" {
  description = "RDS セキュリティグループの ID"
  value       = aws_security_group.rds.id
}
