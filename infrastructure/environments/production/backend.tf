# リモート state
terraform {
  backend "s3" {
    bucket         = "test-app-terraform-state"
    key            = "production/terraform.tfstate"
    region         = "ap-northeast-1"
    encrypt        = true
    dynamodb_table = "test-app-terraform-lock"
  }
}