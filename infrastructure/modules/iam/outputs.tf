output "deploy_role_arn" {
  description = "GitHub Actions デプロイ用 IAM ロールの ARN"
  value       = aws_iam_role.github_actions_deploy.arn
}

output "oidc_provider_arn" {
  description = "GitHub OIDC プロバイダの ARN"
  value       = aws_iam_openid_connect_provider.github.arn
}
