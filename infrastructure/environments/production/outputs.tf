output "alb_dns_name" {
  description = "ALB の DNS 名（バックエンド API エンドポイント）"
  value       = module.alb.alb_dns_name
}

output "cloudfront_domain_name" {
  description = "CloudFront ドメイン名（フロントエンド）"
  value       = module.s3_cloudfront.cloudfront_domain_name
}

output "ecr_repository_url" {
  description = "ECR リポジトリ URL"
  value       = module.ecr.repository_url
}

output "ecs_cluster_name" {
  description = "ECS クラスタ名"
  value       = module.ecs.cluster_name
}

output "ecs_service_name" {
  description = "ECS サービス名"
  value       = module.ecs.service_name
}

output "deploy_role_arn" {
  description = "GitHub Actions デプロイ用ロール ARN"
  value       = module.iam.deploy_role_arn
}

output "s3_bucket_name" {
  description = "フロントエンド S3 バケット名"
  value       = module.s3_cloudfront.s3_bucket_name
}

output "cloudfront_distribution_id" {
  description = "CloudFront ディストリビューション ID"
  value       = module.s3_cloudfront.cloudfront_distribution_id
}

output "db_host" {
  description = "RDS エンドポイント"
  value       = module.rds.db_host
}
