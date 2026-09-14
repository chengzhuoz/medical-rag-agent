variable "aws_region" { type = string default = "ap-southeast-1" }
variable "aws_account_id" { type = string }
variable "project_name" { type = string default = "medical-rag" }
variable "github_repository" { type = string description = "owner/repository" }
variable "task_cpu" { type = number default = 1024 }
variable "task_memory" { type = number default = 2048 }
variable "desired_count" { type = number default = 0 }
variable "database_url" { type = string sensitive = true }
variable "milvus_uri" { type = string }
variable "milvus_token" { type = string sensitive = true default = "" }
variable "milvus_collection" { type = string default = "public_health_chunks" }
variable "neo4j_uri" { type = string }
variable "neo4j_user" { type = string default = "neo4j" }
variable "neo4j_password" { type = string sensitive = true }
variable "ollama_base_url" { type = string }
variable "ollama_model" { type = string default = "qwen3:8b" }
