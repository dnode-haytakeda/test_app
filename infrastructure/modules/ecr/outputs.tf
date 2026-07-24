output "repository_url" {
  description = "ECR リポジトリの URL"
  value       = aws_ecr_repository.backend.repository_url
}

output "repository_arn" {
  description = "ECR リポジトリの ARN"
  value       = aws_ecr_repository.backend.arn
}
