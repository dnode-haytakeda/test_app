output "cluster_name" {
  description = "ECS クラスタ名"
  value       = aws_ecs_cluster.main.name
}

output "service_name" {
  description = "ECS サービス名"
  value       = aws_ecs_service.backend.name
}

output "ecs_security_group_id" {
  description = "ECS セキュリティグループの ID"
  value       = aws_security_group.ecs.id
}

output "task_definition_family" {
  description = "タスク定義のファミリー名"
  value       = aws_ecs_task_definition.backend.family
}

output "execution_role_arn" {
  description = "ECS タスク実行ロールの ARN"
  value       = aws_iam_role.ecs_execution.arn
}

output "task_role_arn" {
  description = "ECS タスクロールの ARN"
  value       = aws_iam_role.ecs_task.arn
}
