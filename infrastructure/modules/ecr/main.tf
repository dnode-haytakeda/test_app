resource "aws_ecr_repository" "backend" {
  name                 = "${var.project_name}/backend"
  image_tag_mutability = "IMMUTABLE" # 同じタグで上書き不可

  image_scanning_congiguration {
    scan_on_push = true # push 時に脆弱性スキャン
  }

  encryption_configuration {
    encryption_type = "AES256"
  }
}

resource "aws_ecr_lifecycle_policy" "backend" {
  repository = aws_ecr_repository.backend.name

  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "最新 20 イメージだけ保持"
      selection = {
        tagStatus   = "any"
        countType   = "imageCountMoreThan"
        countNumber = 20
      }
      action = { type = "expire" }
    }]
  })
}