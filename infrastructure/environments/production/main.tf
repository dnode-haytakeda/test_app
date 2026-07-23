# environments/production/main.tf
module "networking" {
  source       = "../../modules/vpc"
  project_name = "test-app"
  environment  = "production"
  vpc_cidr     = "10.0.0.0/16"
}

module "ecs" {
  source        = "../../modules/ecs"
  environment   = "production"
  vpc_id        = module.networking.vpc_id
  subnet_ids    = module.networking.private_subnet_ids
  desired_count = 3
}