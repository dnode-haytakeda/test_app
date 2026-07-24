# environments/production/main.tf
# 全モジュールを呼び出し、本番環境のインフラを構築する

terraform {
  required_version = ">= 1.5"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
  # aws-azure-login は default プロファイルに認証情報を書き込むため
  # profile 指定は不要 (デフォルトで default を使用)

  default_tags {
    tags = {
      Project     = var.project_name
      Environment = "production"
      ManagedBy   = "terraform"
    }
  }
}

# --- ネットワーク ---
module "vpc" {
  source             = "../../modules/vpc"
  project_name       = var.project_name
  environment        = "production"
  vpc_cidr           = var.vpc_cidr
  availability_zones = var.availability_zones
  aws_region         = var.aws_region
}

# --- コンテナレジストリ ---
module "ecr" {
  source       = "../../modules/ecr"
  project_name = var.project_name
  environment  = "production"
}

# --- ロードバランサー ---
module "alb" {
  source            = "../../modules/alb"
  project_name      = var.project_name
  environment       = "production"
  vpc_id            = module.vpc.vpc_id
  public_subnet_ids = module.vpc.public_subnet_ids
  certificate_arn   = var.certificate_arn
}

# --- コンテナ実行環境 ---
module "ecs" {
  source                = "../../modules/ecs"
  project_name          = var.project_name
  environment           = "production"
  vpc_id                = module.vpc.vpc_id
  private_subnet_ids    = module.vpc.private_subnet_ids
  ecr_repository_url    = module.ecr.repository_url
  image_tag             = var.image_tag
  alb_security_group_id = module.alb.alb_security_group_id
  target_group_arn      = module.alb.target_group_arn
  db_host               = module.rds.db_host
  db_name               = var.db_name
  db_secret_arn         = module.rds.db_secret_arn
  jwt_secret_arn        = var.jwt_secret_arn
  cors_origins          = var.cors_origins
  aws_region            = var.aws_region
  task_cpu              = var.task_cpu
  task_memory           = var.task_memory
  desired_count         = var.desired_count
}

# --- データベース ---
module "rds" {
  source                = "../../modules/rds"
  project_name          = var.project_name
  environment           = "production"
  vpc_id                = module.vpc.vpc_id
  database_subnet_ids   = module.vpc.database_subnet_ids
  ecs_security_group_id = module.ecs.ecs_security_group_id
  db_instance_class     = var.db_instance_class
  db_allocated_storage  = var.db_allocated_storage
  db_max_storage        = var.db_max_storage
  db_name               = var.db_name
  db_username           = var.db_username
  multi_az              = var.multi_az
}

# --- フロントエンド配信 ---
module "s3_cloudfront" {
  source          = "../../modules/s3-cloudfront"
  project_name    = var.project_name
  environment     = "production"
  domain_name     = var.frontend_domain_name
  certificate_arn = var.frontend_certificate_arn
}

# --- IAM (GitHub Actions OIDC) ---
module "iam" {
  source                     = "../../modules/iam"
  project_name               = var.project_name
  environment                = "production"
  github_org                 = var.github_org
  github_repo                = var.github_repo
  ecr_repository_arn         = module.ecr.repository_arn
  ecs_execution_role_arn     = module.ecs.execution_role_arn
  ecs_task_role_arn           = module.ecs.task_role_arn
  frontend_bucket_arn        = module.s3_cloudfront.s3_bucket_arn
  cloudfront_distribution_arn = "arn:aws:cloudfront::${data.aws_caller_identity.current.account_id}:distribution/${module.s3_cloudfront.cloudfront_distribution_id}"
}

data "aws_caller_identity" "current" {}