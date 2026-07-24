output "alb_dns_name" {
  description = "ALB の DNS 名"
  value       = aws_lb.main.dns_name
}

output "alb_zone_id" {
  description = "ALB のホストゾーン ID（Route 53 エイリアスレコード用）"
  value       = aws_lb.main.zone_id
}

output "target_group_arn" {
  description = "バックエンド用ターゲットグループの ARN"
  value       = aws_lb_target_group.backend.arn
}

output "alb_security_group_id" {
  description = "ALB セキュリティグループの ID"
  value       = aws_security_group.alb.id
}
