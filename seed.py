#!/usr/bin/env python3
"""
Seed script: creates demo resources against a Tribal instance.

Usage:
    python seed.py                                         # targets dev.tribal-app.xyz, no auth
    python seed.py --url http://localhost:8000             # custom URL
    python seed.py --api-key tribal_sk_abc123...           # authenticate with an API key
    python seed.py --url http://localhost:8000 --api-key tribal_sk_abc123...

Environment variable equivalents (flags take precedence):
    BASE_URL    Target base URL
    API_KEY     Tribal API key
"""
import argparse
import os
import random
import sys
from datetime import date, timedelta

import httpx


def _parse_args():
    parser = argparse.ArgumentParser(description="Seed demo resources into a Tribal instance.")
    parser.add_argument("--url", default=None, help="Base URL (default: $BASE_URL or https://dev.tribal-app.xyz)")
    parser.add_argument("--api-key", default=None, dest="api_key", help="Tribal API key for Bearer auth (default: $API_KEY)")
    return parser.parse_args()


args = _parse_args()
BASE_URL = (args.url or os.environ.get("BASE_URL", "https://dev.tribal-app.xyz")).rstrip("/")
API_KEY = args.api_key or os.environ.get("API_KEY", "")
API = f"{BASE_URL}/api/resources/"

HEADERS = {"Authorization": f"Bearer {API_KEY}"} if API_KEY else {}

RESOURCES = [
    {
        "name": "AWS Production API Key",
        "type": "API Key",
        "dri": "alice@example.com",
        "purpose": "Grants programmatic access to the production AWS account for CI/CD pipelines.",
        "generation_instructions": "Generate via IAM → Users → Security credentials → Create access key. Store in AWS Secrets Manager.",
        "secret_manager_link": "https://console.aws.amazon.com/secretsmanager",
        "slack_webhook": "https://hooks.slack.com/services/DEMO/DEMO/DEMO",
    },
    {
        "name": "GitHub Actions Deploy Token",
        "type": "API Key",
        "dri": "bob@example.com",
        "purpose": "Fine-grained personal access token used by GitHub Actions to push releases.",
        "generation_instructions": "GitHub → Settings → Developer settings → Fine-grained tokens → Generate new token.",
        "secret_manager_link": "",
        "slack_webhook": "https://hooks.slack.com/services/DEMO/DEMO/DEMO",
    },
    {
        "name": "api.example.com TLS Certificate",
        "type": "Certificate",
        "dri": "certs@example.com",
        "purpose": "TLS certificate for the public-facing REST API endpoint.",
        "generation_instructions": "Renew via Certbot: `certbot renew --cert-name api.example.com`. Upload new PEM to the load balancer.",
        "secret_manager_link": "",
        "slack_webhook": "https://hooks.slack.com/services/DEMO/DEMO/DEMO",
    },
    {
        "name": "Datadog API Key",
        "type": "API Key",
        "dri": "ops@example.com",
        "purpose": "Sends metrics and traces from production services to Datadog.",
        "generation_instructions": "Datadog → Organization Settings → API Keys → New Key.",
        "secret_manager_link": "https://app.datadoghq.com/organization-settings/api-keys",
        "slack_webhook": "https://hooks.slack.com/services/DEMO/DEMO/DEMO",
    },
    {
        "name": "Production SSH Deploy Key",
        "type": "SSH Key",
        "dri": "infra@example.com",
        "purpose": "SSH key used by Ansible to deploy to production servers.",
        "generation_instructions": "Run `ssh-keygen -t ed25519 -C deploy@prod`. Add public key to authorized_keys on all targets.",
        "secret_manager_link": "",
        "slack_webhook": "https://hooks.slack.com/services/DEMO/DEMO/DEMO",
    },
    {
        "name": "Stripe Restricted API Key",
        "type": "API Key",
        "dri": "payments@example.com",
        "purpose": "Restricted key for reading payment intents from the billing service.",
        "generation_instructions": "Stripe Dashboard → Developers → API keys → Create restricted key.",
        "secret_manager_link": "https://dashboard.stripe.com/apikeys",
        "slack_webhook": "https://hooks.slack.com/services/DEMO/DEMO/DEMO",
    },
    {
        "name": "*.internal.example.com Wildcard Cert",
        "type": "Certificate",
        "dri": "certs@example.com",
        "purpose": "Wildcard TLS certificate for all internal services.",
        "generation_instructions": "Renew via internal CA. Run `make cert-renew` in the infra repo and distribute via Puppet.",
        "secret_manager_link": "",
        "slack_webhook": "https://hooks.slack.com/services/DEMO/DEMO/DEMO",
    },
    {
        "name": "PagerDuty Integration Key",
        "type": "API Key",
        "dri": "alice@example.com",
        "purpose": "Events API v2 key for routing alerts from monitoring to on-call schedules.",
        "generation_instructions": "PagerDuty → Services → Integrations → Add integration → Events API v2.",
        "secret_manager_link": "",
        "slack_webhook": "https://hooks.slack.com/services/DEMO/DEMO/DEMO",
    },
    {
        "name": "Kubernetes Service Account Token",
        "type": "Other",
        "dri": "infra@example.com",
        "purpose": "Long-lived token for the monitoring service account in the production cluster.",
        "generation_instructions": "Run `kubectl create token monitoring-sa --duration=8760h` and update the secret in Vault.",
        "secret_manager_link": "https://vault.internal.example.com",
        "slack_webhook": "https://hooks.slack.com/services/DEMO/DEMO/DEMO",
    },
    {
        "name": "SendGrid API Key",
        "type": "API Key",
        "dri": "bob@example.com",
        "purpose": "Used by the notification service to send transactional emails.",
        "generation_instructions": "SendGrid → Settings → API Keys → Create API Key (Restricted, Mail Send only).",
        "secret_manager_link": "https://app.sendgrid.com/settings/api_keys",
        "slack_webhook": "https://hooks.slack.com/services/DEMO/DEMO/DEMO",
    },
    {
        "name": "GitHub SSH Deploy Key (infra-repo)",
        "type": "SSH Key",
        "dri": "infra@example.com",
        "purpose": "Read-only deploy key for the infra repo, used by the CI runner.",
        "generation_instructions": "Run `ssh-keygen -t ed25519`. Add public key to repo → Settings → Deploy keys.",
        "secret_manager_link": "",
        "slack_webhook": "https://hooks.slack.com/services/DEMO/DEMO/DEMO",
    },
    {
        "name": "Cloudflare API Token",
        "type": "API Key",
        "dri": "ops@example.com",
        "purpose": "Manages DNS records and cache purging for the production zone.",
        "generation_instructions": "Cloudflare → My Profile → API Tokens → Create Token (Zone DNS Edit template).",
        "secret_manager_link": "https://dash.cloudflare.com/profile/api-tokens",
        "slack_webhook": "https://hooks.slack.com/services/DEMO/DEMO/DEMO",
    },
    {
        "name": "app.example.com TLS Certificate",
        "type": "Certificate",
        "dri": "certs@example.com",
        "purpose": "TLS certificate for the main customer-facing web application.",
        "generation_instructions": "Auto-renewed by Certbot. Verify renewal timer: `systemctl status certbot.timer`.",
        "secret_manager_link": "",
        "slack_webhook": "https://hooks.slack.com/services/DEMO/DEMO/DEMO",
    },
    {
        "name": "Terraform Cloud API Token",
        "type": "API Key",
        "dri": "infra@example.com",
        "purpose": "Team token for the platform workspace in Terraform Cloud, used by CI.",
        "generation_instructions": "Terraform Cloud → Organization → Teams → platform → Team API Token → Regenerate.",
        "secret_manager_link": "https://app.terraform.io/app/example/settings/teams",
        "slack_webhook": "https://hooks.slack.com/services/DEMO/DEMO/DEMO",
    },
    {
        "name": "SMTP Relay Credentials",
        "type": "Other",
        "dri": "alice@example.com",
        "purpose": "Username/password for the corporate SMTP relay used by internal tooling.",
        "generation_instructions": "Request rotation from IT via the helpdesk portal. Update secret in 1Password and restart the mail-forwarder service.",
        "secret_manager_link": "",
        "slack_webhook": "https://hooks.slack.com/services/DEMO/DEMO/DEMO",
    },
    {
        "name": "Sentry Auth Token",
        "type": "API Key",
        "dri": "bob@example.com",
        "purpose": "Uploads source maps and release artifacts to Sentry during CI builds.",
        "generation_instructions": "Sentry → Settings → Auth Tokens → Create New Token (project:releases scope).",
        "secret_manager_link": "https://sentry.io/settings/account/api/auth-tokens/",
        "slack_webhook": "https://hooks.slack.com/services/DEMO/DEMO/DEMO",
    },
    {
        "name": "VPN Gateway Certificate",
        "type": "Certificate",
        "dri": "infra@example.com",
        "purpose": "Client certificate issued to the VPN gateway for mutual TLS authentication.",
        "generation_instructions": "Re-issue via internal PKI: `easyrsa build-client-full vpn-gw nopass`. Update gateway config and restart OpenVPN.",
        "secret_manager_link": "",
        "slack_webhook": "https://hooks.slack.com/services/DEMO/DEMO/DEMO",
    },
    {
        "name": "New Relic License Key",
        "type": "API Key",
        "dri": "ops@example.com",
        "purpose": "Ingest key used by the APM agent on all application servers.",
        "generation_instructions": "New Relic → Administration → API keys → Create key (INGEST - LICENSE type). Roll out via config management.",
        "secret_manager_link": "https://one.newrelic.com/admin-portal/api-keys",
        "slack_webhook": "https://hooks.slack.com/services/DEMO/DEMO/DEMO",
    },
    {
        "name": "Database Backup Encryption Key",
        "type": "Other",
        "dri": "infra@example.com",
        "purpose": "AES-256 key used to encrypt offsite database backups before upload to S3.",
        "generation_instructions": "Generate with `openssl rand -base64 32`. Store in Vault at secret/backup/db-key and update the backup cron config.",
        "secret_manager_link": "https://vault.internal.example.com/ui/vault/secrets/secret/show/backup/db-key",
        "slack_webhook": "https://hooks.slack.com/services/DEMO/DEMO/DEMO",
    },
    {
        "name": "Twilio API Key",
        "type": "API Key",
        "dri": "payments@example.com",
        "purpose": "Used by the 2FA service to send SMS one-time passwords.",
        "generation_instructions": "Twilio Console → Account → API keys & tokens → Create API key (Standard). Update secret and restart auth-service.",
        "secret_manager_link": "https://console.twilio.com/us1/account/keys-credentials/api-keys",
        "slack_webhook": "https://hooks.slack.com/services/DEMO/DEMO/DEMO",
    },
    {
        "name": "GCP Service Account Key",
        "type": "API Key",
        "dri": "ops@example.com",
        "purpose": "Service account key for the data pipeline job that exports metrics to BigQuery.",
        "generation_instructions": "GCP Console → IAM → Service Accounts → data-pipeline-sa → Keys → Add Key → JSON. Store in Secret Manager.",
        "secret_manager_link": "https://console.cloud.google.com/iam-admin/serviceaccounts",
        "slack_webhook": "https://hooks.slack.com/services/DEMO/DEMO/DEMO",
        "_shared_expiry": True,
    },
    {
        "name": "Legacy SFTP Credentials",
        "type": "Other",
        "dri": "infra@example.com",
        "purpose": "SFTP username/password used by a legacy data transfer job to the finance system.",
        "generation_instructions": "Contact the finance team to reset credentials. Update in 1Password and the cron job config on transfer-host-01.",
        "secret_manager_link": "",
        "slack_webhook": "https://hooks.slack.com/services/DEMO/DEMO/DEMO",
        "_days_offset": -14,
    },
    {
        "name": "staging.example.com TLS Certificate",
        "type": "Certificate",
        "dri": "certs@example.com",
        "purpose": "TLS certificate for the staging environment load balancer.",
        "generation_instructions": "Renew via Certbot: `certbot renew --cert-name staging.example.com`. Restart nginx after renewal.",
        "secret_manager_link": "",
        "slack_webhook": "https://hooks.slack.com/services/DEMO/DEMO/DEMO",
        "_days_offset": 5,
    },
]


def main():
    today = date.today()
    created = []
    failed = []

    # Pre-generate a shared expiry date used by resource[0] and the last entry (_shared_expiry)
    shared_expiry = today + timedelta(days=random.randint(14, 150))

    total = len(RESOURCES)
    auth_note = f"  (API key: {API_KEY[:18]}...)" if API_KEY else "  (no API key — ensure you have a valid session or the server allows unauthenticated access)"
    print(f"Seeding {total} resources → {API}{auth_note}\n")

    for i, resource in enumerate(RESOURCES):
        resource = {k: v for k, v in resource.items() if k not in ("_shared_expiry", "_days_offset")}
        if RESOURCES[i].get("_days_offset") is not None:
            expiry = today + timedelta(days=RESOURCES[i]["_days_offset"])
        elif i == 0 or RESOURCES[i].get("_shared_expiry"):
            expiry = shared_expiry
        else:
            days = random.randint(14, 150)
            expiry = today + timedelta(days=days)
        payload = {**resource, "expiration_date": expiry.isoformat()}

        try:
            resp = httpx.post(API, json=payload, headers=HEADERS, timeout=15, follow_redirects=True)
            resp.raise_for_status()
            rid = resp.json()["id"]
            shared_note = " ← shared date" if expiry == shared_expiry else ""
            print(f"  [{i+1:02d}/{total}] ✓ {resource['name'][:50]:<50}  expires {expiry}{shared_note}  (id={rid})")
            created.append(rid)
        except httpx.HTTPStatusError as e:
            print(f"  [{i+1:02d}/{total}] ✗ {resource['name'][:50]:<50}  HTTP {e.response.status_code}: {e.response.text[:80]}")
            failed.append(resource["name"])
        except Exception as e:
            print(f"  [{i+1:02d}/{total}] ✗ {resource['name'][:50]:<50}  {e}")
            failed.append(resource["name"])

    print(f"\nDone. {len(created)} created, {len(failed)} failed.")
    print(f"Shared expiry date: {shared_expiry} (AWS Production API Key + GCP Service Account Key)")
    if failed:
        print("Failed:")
        for name in failed:
            print(f"  - {name}")
    sys.exit(0 if not failed else 1)


if __name__ == "__main__":
    main()
