resource "digitalocean_vpc" "tribal" {
  name   = "tribal-app"
  region = var.region
}

resource "digitalocean_database_cluster" "tribal_db" {
  name       = "tribal-db"
  engine     = "mysql"
  version    = "8"
  size       = var.db_size_slug
  region     = var.region
  node_count = 1

  private_network_uuid = digitalocean_vpc.tribal.id
}

resource "digitalocean_app" "tribal" {
  spec {
    name   = "tribal"
    region = var.app_region

    service {
      name               = "api"
      instance_count     = var.instance_count
      instance_size_slug = var.instance_size_slug
      http_port          = 8000

      image {
        registry_type = "DOCR"
        repository    = "tribal"
        tag           = var.image_tag
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
        key   = "DATABASE_URL"
        value = digitalocean_database_cluster.tribal_db.uri
        scope = "RUN_TIME"
        type  = "SECRET"
      }
    }
  }
}
