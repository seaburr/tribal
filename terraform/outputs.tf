output "app_url" {
  description = "Live URL of the deployed application."
  value       = digitalocean_app.tribal.live_url
}

output "app_id" {
  description = "DigitalOcean App Platform app ID."
  value       = digitalocean_app.tribal.id
}

output "db_host" {
  description = "Managed MySQL public hostname."
  value       = digitalocean_database_cluster.tribal_db.host
}

output "db_port" {
  description = "Managed MySQL port."
  value       = digitalocean_database_cluster.tribal_db.port
}

output "db_uri" {
  description = "Full MySQL connection URI (sensitive)."
  value       = digitalocean_database_cluster.tribal_db.uri
  sensitive   = true
}
