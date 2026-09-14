output "alb_url" { value = "http://${aws_lb.backend.dns_name}" }
output "ecr_repository" { value = aws_ecr_repository.backend.repository_url }
output "github_actions_role_arn" { value = aws_iam_role.github_actions.arn }
output "ecs_cluster" { value = aws_ecs_cluster.backend.name }
output "ecs_service" { value = aws_ecs_service.backend.name }
