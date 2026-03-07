variable "do_token" {
  description = "DigitalOcean personal access token."
  type        = string
  sensitive   = true
}

variable "region" {
  description = "DigitalOcean region slug."
  type        = string
  default     = "nyc1"
}

variable "app_region" {
  description = "DigitalOcean App Platform region slug (nyc, ams, sfo, etc.)."
  type        = string
  default     = "nyc"
}

variable "instance_size_slug" {
  description = "App Platform instance size slug."
  type        = string
  default     = "apps-s-1vcpu-0.5gb"
}

variable "db_size_slug" {
  description = "Managed MySQL cluster size slug."
  type        = string
  default     = "db-s-1vcpu-1gb"
}
