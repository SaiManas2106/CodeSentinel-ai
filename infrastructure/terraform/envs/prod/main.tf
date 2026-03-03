terraform {
  required_version = ">= 1.6.0"

  backend "s3" {
    bucket         = "codesentinel-terraform-state"
    key            = "prod/terraform.tfstate"
    region         = "us-east-1"
    dynamodb_table = "codesentinel-terraform-locks"
    encrypt        = true
  }

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.60"
    }
  }
}

provider "aws" {
  region = "us-east-1"
}

module "eks" {
  source       = "../../modules/eks"
  cluster_name = "codesentinel-prod"
  region       = "us-east-1"
}

module "rds" {
  source                    = "../../modules/rds"
  name                      = "codesentinel-prod"
  vpc_id                    = module.eks.vpc_id
  subnet_ids                = ["subnet-1", "subnet-2", "subnet-3"]
  allowed_security_group_id = module.eks.node_security_group_id
  db_username               = "codesentinel"
  db_password               = var.db_password
  multi_az                  = true
}

variable "db_password" {
  type      = string
  sensitive = true
}
