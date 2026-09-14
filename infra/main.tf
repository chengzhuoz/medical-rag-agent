terraform {
  required_version = ">= 1.6.0"
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 5.0" }
  }
}

provider "aws" { region = var.aws_region }

data "aws_vpc" "default" { default = true }
data "aws_subnets" "default" { filter { name = "vpc-id" values = [data.aws_vpc.default.id] } }
data "aws_iam_openid_connect_provider" "github" { url = "https://token.actions.githubusercontent.com" }

resource "aws_ecr_repository" "backend" {
  name                 = "${var.project_name}-backend"
  image_tag_mutability = "MUTABLE"
  image_scanning_configuration { scan_on_push = true }
}

resource "aws_cloudwatch_log_group" "backend" {
  name              = "/ecs/${var.project_name}/backend"
  retention_in_days = 30
}

resource "aws_security_group" "alb" {
  name   = "${var.project_name}-alb"
  vpc_id = data.aws_vpc.default.id
  ingress { from_port = 80 to_port = 80 protocol = "tcp" cidr_blocks = ["0.0.0.0/0"] }
  ingress { from_port = 443 to_port = 443 protocol = "tcp" cidr_blocks = ["0.0.0.0/0"] }
  egress { from_port = 0 to_port = 0 protocol = "-1" cidr_blocks = ["0.0.0.0/0"] }
}

resource "aws_security_group" "service" {
  name   = "${var.project_name}-service"
  vpc_id = data.aws_vpc.default.id
  ingress { from_port = 8000 to_port = 8000 protocol = "tcp" security_groups = [aws_security_group.alb.id] }
  egress { from_port = 0 to_port = 0 protocol = "-1" cidr_blocks = ["0.0.0.0/0"] }
}

resource "aws_lb" "backend" {
  name               = "${var.project_name}-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = data.aws_subnets.default.ids
}

resource "aws_lb_target_group" "backend" {
  name        = "${var.project_name}-backend"
  port        = 8000
  protocol    = "HTTP"
  target_type = "ip"
  vpc_id      = data.aws_vpc.default.id
  health_check { path = "/healthz/" matcher = "200" interval = 30 timeout = 5 healthy_threshold = 2 unhealthy_threshold = 3 }
}

resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.backend.arn
  port              = 80
  protocol          = "HTTP"
  default_action { type = "forward" target_group_arn = aws_lb_target_group.backend.arn }
}

resource "aws_iam_role" "ecs_execution" {
  name = "${var.project_name}-ecs-execution"
  assume_role_policy = jsonencode({ Version = "2012-10-17", Statement = [{ Effect = "Allow", Principal = { Service = "ecs-tasks.amazonaws.com" }, Action = "sts:AssumeRole" }] })
}

resource "aws_iam_role_policy_attachment" "ecs_execution" {
  role       = aws_iam_role.ecs_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role" "github_actions" {
  name = "${var.project_name}-github-actions"
  assume_role_policy = jsonencode({ Version = "2012-10-17", Statement = [{ Effect = "Allow", Principal = { Federated = data.aws_iam_openid_connect_provider.github.arn }, Action = "sts:AssumeRoleWithWebIdentity", Condition = { StringEquals = { "token.actions.githubusercontent.com:aud" = "sts.amazonaws.com" }, StringLike = { "token.actions.githubusercontent.com:sub" = "repo:${var.github_repository}:ref:refs/heads/main" } } }] })
}

resource "aws_iam_role_policy" "github_actions" {
  role = aws_iam_role.github_actions.id
  policy = jsonencode({ Version = "2012-10-17", Statement = [
    { Effect = "Allow", Action = ["ecr:GetAuthorizationToken"], Resource = "*" },
    { Effect = "Allow", Action = ["ecr:BatchCheckLayerAvailability", "ecr:CompleteLayerUpload", "ecr:InitiateLayerUpload", "ecr:PutImage", "ecr:UploadLayerPart"], Resource = aws_ecr_repository.backend.arn },
    { Effect = "Allow", Action = ["ecs:DescribeServices", "ecs:DescribeTaskDefinition", "ecs:UpdateService"], Resource = "*" },
    { Effect = "Allow", Action = ["iam:PassRole"], Resource = aws_iam_role.ecs_execution.arn }
  ] })
}

resource "aws_ecs_cluster" "backend" { name = var.project_name }

resource "aws_ecs_task_definition" "backend" {
  family                   = "${var.project_name}-backend"
  requires_compatibilities = ["FARGATE"]
  network_mode              = "awsvpc"
  cpu                      = var.task_cpu
  memory                   = var.task_memory
  execution_role_arn       = aws_iam_role.ecs_execution.arn
  container_definitions = jsonencode([{ name = "backend", image = "${aws_ecr_repository.backend.repository_url}:bootstrap", essential = true, portMappings = [{ containerPort = 8000, protocol = "tcp" }], environment = [
    { name = "DEBUG", value = "0" }, { name = "ALLOWED_HOSTS", value = "*" }, { name = "VECTOR_BACKEND", value = "milvus" },
    { name = "DATABASE_URL", value = var.database_url }, { name = "MILVUS_URI", value = var.milvus_uri }, { name = "MILVUS_TOKEN", value = var.milvus_token },
    { name = "MILVUS_COLLECTION", value = var.milvus_collection }, { name = "NEO4J_URI", value = var.neo4j_uri }, { name = "NEO4J_USER", value = var.neo4j_user }, { name = "NEO4J_PASSWORD", value = var.neo4j_password },
    { name = "OLLAMA_BASE_URL", value = var.ollama_base_url }, { name = "OLLAMA_MODEL", value = var.ollama_model }, { name = "MAS_ENABLED", value = "1" }
  ], logConfiguration = { logDriver = "awslogs", options = { awslogs-group = aws_cloudwatch_log_group.backend.name, awslogs-region = var.aws_region, awslogs-stream-prefix = "backend" } } }])
}

resource "aws_ecs_service" "backend" {
  name            = var.project_name
  cluster         = aws_ecs_cluster.backend.id
  task_definition = aws_ecs_task_definition.backend.arn
  desired_count   = var.desired_count
  launch_type     = "FARGATE"
  network_configuration { subnets = data.aws_subnets.default.ids assign_public_ip = true security_groups = [aws_security_group.service.id] }
  load_balancer { target_group_arn = aws_lb_target_group.backend.arn container_name = "backend" container_port = 8000 }
  lifecycle { ignore_changes = [task_definition] }
}
