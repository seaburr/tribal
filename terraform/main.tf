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

resource "digitalocean_app" "tribal_landing" {
  spec {
    name   = "tribal-landing"
    region = var.app_region

    domain {
      name = "tribal-app.xyz"
      type = "PRIMARY"
      zone = "tribal-app.xyz"
    }

    static_site {
      name           = "landing"
      source_dir     = "landing"
      index_document = "index.html"
      error_document = "index.html"

      github {
        repo           = "seaburr/Tribal"
        branch         = "main"
        deploy_on_push = true
      }
    }
  }
}

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

      # env {
      #   key   = "DATABASE_URL"
      #   value = digitalocean_database_cluster.tribal_db.private_uri
      #   scope = "RUN_TIME"
      #   type  = "SECRET"
      # }
    }
  }
}
