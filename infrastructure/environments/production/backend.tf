# リモート state
terraform {
  backend "s3" {
    bucket       = "test-app-terraform-state-146062274667"
    key          = "production/terraform.tfstate"
    region       = "ap-northeast-1"
    encrypt      = true
    use_lockfile = true
  }
}