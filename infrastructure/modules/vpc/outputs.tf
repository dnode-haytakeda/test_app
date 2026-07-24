output "vpc_id" {
  description = "VPC の ID"
  value       = aws_vpc.main.id
}

output "public_subnet_ids" {
  description = "パブリックサブネットの ID リスト"
  value       = aws_subnet.public[*].id
}

output "private_subnet_ids" {
  description = "プライベートサブネットの ID リスト"
  value       = aws_subnet.private[*].id
}

output "database_subnet_ids" {
  description = "DB サブネットの ID リスト"
  value       = aws_subnet.database[*].id
}

output "vpc_cidr_block" {
  description = "VPC の CIDR ブロック"
  value       = aws_vpc.main.cidr_block
}
