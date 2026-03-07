resource "random_password" "jwt_secret" {
  length  = 64
  special = false
  # Regenerating this invalidates all active sessions. Taint intentionally if rotation is needed.
  lifecycle {
    ignore_changes = all
  }
}

# Note: DigitalOcean App Platform cannot be attached to a customer VPC.
# The VPC is provisioned here for the future managed MySQL cluster, which will
# use its private hostname to keep DB traffic off the public internet.
resource "digitalocean_vpc" "tribal" {
  name   = "tribal-app"
  region = var.region
}

# resource "digitalocean_database_cluster" "tribal_db" {
#   name       = "tribal-db"
#   engine     = "mysql"
#   version    = "8"
#   size       = var.db_size_slug
#   region     = var.region
#   node_count = 1
#
#   private_network_uuid = digitalocean_vpc.tribal.id
# }

resource "digitalocean_app" "tribal" {
  spec {
    name   = "tribal"
    region = var.app_region

    domain {
      name = "dev.tribal-app.xyz"
      type = "PRIMARY"
      zone = "tribal-app.xyz"
    }

    service {
      name               = "api"
      instance_count     = 1
      instance_size_slug = var.instance_size_slug
      http_port          = 8000

      image {
        registry_type = "DOCR"
        repository    = "tribal"
        tag           = "latest"
        deploy_on_push {
          enabled = true
        }
      }

      health_check {
        http_path             = "/healthz"
        initial_delay_seconds = 30
        period_seconds        = 30
        timeout_seconds       = 5
      }

      env {
        key   = "JWT_SECRET"
        value = random_password.jwt_secret.result
        scope = "RUN_TIME"
        type  = "SECRET"
      }

      # env {
      #   key   = "DATABASE_URL"
      #   value = digitalocean_database_cluster.tribal_db.private_uri
      #   scope = "RUN_TIME"
      #   type  = "SECRET"
      # }
    }
  }
}
