output "s3_bucket_name" {
  description = "フロントエンド S3 バケット名"
  value       = aws_s3_bucket.frontend.id
}

output "s3_bucket_arn" {
  description = "フロントエンド S3 バケット ARN"
  value       = aws_s3_bucket.frontend.arn
}

output "cloudfront_distribution_id" {
  description = "CloudFront ディストリビューション ID"
  value       = aws_cloudfront_distribution.frontend.id
}

output "cloudfront_domain_name" {
  description = "CloudFront ドメイン名"
  value       = aws_cloudfront_distribution.frontend.domain_name
}
