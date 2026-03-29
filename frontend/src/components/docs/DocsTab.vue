<script setup lang="ts">
const trackItems = [
  {
    icon: '🔐',
    title: 'TLS Certificates',
    desc: 'Enter a domain or TLS endpoint URL. Tribal fetches the live certificate and automatically extracts the expiration date.',
  },
  {
    icon: '🔑',
    title: 'API Keys',
    desc: 'Paste any API key and Tribal identifies the provider, looks up the expiry if available, and pre-fills rotation instructions.',
  },
  {
    icon: '🗝️',
    title: 'SSH Keys',
    desc: 'Track SSH key pairs with expiration dates, owners, and rotation instructions.',
  },
  {
    icon: '📦',
    title: 'Custom Credentials',
    desc: 'Track any other secret or credential your team manages — database passwords, webhook secrets, signing keys.',
  },
]

const roles = [
  {
    name: 'Admin',
    color: 'bg-blue-500/20 text-blue-400',
    desc: 'Full control over all resources, users, and notification settings. The account creator cannot be demoted.',
  },
  {
    name: 'Member',
    color: 'bg-emerald-500/20 text-emerald-400',
    desc: 'Can create and manage resources, generate API keys, and download reports.',
  },
  {
    name: 'Read-only',
    color: 'bg-zinc-700/50 text-zinc-400',
    desc: 'Can view all resources and download reports, but cannot create, edit, or delete anything.',
  },
]

const detectionProviders = [
  'GitHub', 'GitLab', 'Stripe', 'OpenAI', 'Anthropic', 'AWS', 'Azure',
  'Slack', 'SendGrid', 'Terraform Cloud', 'DigitalOcean',
]

const providerExample = `import re
import httpx
from .base import Provider, IntrospectionResult

class MyServiceProvider(Provider):
    name = "My Service"

    patterns = [
        re.compile(r"^myservice_[A-Za-z0-9]{32}$"),
    ]

    async def introspect(self, key: str) -> IntrospectionResult:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    "https://api.myservice.com/v1/verify",
                    headers={"Authorization": f"Bearer {key}"},
                )
        except httpx.HTTPError:
            return IntrospectionResult(
                provider=self.name,
                metadata={"error": "Could not reach My Service API"},
                rotation_url="https://myservice.com/settings/api-keys",
                rotation_steps=self._steps(),
            )

        data = resp.json()
        return IntrospectionResult(
            provider=self.name,
            expires_at=data.get("expires_at"),   # date object or None
            metadata={"account": data.get("account_name")},
            rotation_url="https://myservice.com/settings/api-keys",
            rotation_steps=self._steps(),
        )

    @staticmethod
    def _steps() -> list[str]:
        return [
            "Go to https://myservice.com/settings/api-keys",
            "Click 'Generate New Key' and copy the new value",
            "Update the key in your secret manager",
            "Delete the old key from the dashboard",
        ]`
</script>

<template>
  <div class="space-y-8">
    <!-- Intro -->
    <section class="bg-tribal-panel rounded-xl border border-tribal-border p-6">
      <h2 class="text-lg font-semibold text-white mb-3">What is Tribal?</h2>
      <p class="text-zinc-400 leading-relaxed">
        Tribal is a credential lifecycle manager that tracks certificates, API keys, SSH keys, and
        other secrets your organization depends on. It sends automated Slack reminders before
        credentials expire and provides a full audit trail of every change.
      </p>
    </section>

    <!-- What Tribal tracks -->
    <section class="bg-tribal-panel rounded-xl border border-tribal-border p-6">
      <h2 class="text-lg font-semibold text-white mb-4">What Tribal Tracks</h2>
      <div class="grid grid-cols-2 gap-3">
        <div
          v-for="item in trackItems"
          :key="item.title"
          class="bg-tribal-card rounded-lg border border-tribal-border p-4"
        >
          <span class="text-xl mb-2 block">{{ item.icon }}</span>
          <h3 class="text-white font-medium text-sm mb-1">{{ item.title }}</h3>
          <p class="text-zinc-400 text-xs leading-relaxed">{{ item.desc }}</p>
        </div>
      </div>
    </section>

    <!-- Roles -->
    <section class="bg-tribal-panel rounded-xl border border-tribal-border p-6">
      <h2 class="text-lg font-semibold text-white mb-4">Roles</h2>
      <div class="space-y-3">
        <div
          v-for="role in roles"
          :key="role.name"
          class="flex gap-3 p-3 bg-tribal-card rounded-lg border border-tribal-border"
        >
          <span
            :class="[
              'shrink-0 px-2.5 py-0.5 rounded-full text-xs font-medium self-start mt-0.5',
              role.color,
            ]"
          >
            {{ role.name }}
          </span>
          <p class="text-zinc-400 text-sm leading-relaxed">{{ role.desc }}</p>
        </div>
      </div>
    </section>

    <!-- Admin features -->
    <section class="bg-tribal-panel rounded-xl border border-tribal-border p-6">
      <h2 class="text-lg font-semibold text-white mb-4">Admin Features</h2>
      <ul class="space-y-2 text-zinc-400 text-sm">
        <li class="flex gap-2"><span class="text-blue-400">•</span> Configure Slack notification schedules and reminder intervals</li>
        <li class="flex gap-2"><span class="text-blue-400">•</span> View the full audit log — every create, update, delete, and login event</li>
        <li class="flex gap-2"><span class="text-blue-400">•</span> Manage users and assign roles (Admin, Member, Read-only)</li>
        <li class="flex gap-2"><span class="text-blue-400">•</span> Soft-delete recovery — restore or permanently purge deleted resources</li>
        <li class="flex gap-2"><span class="text-blue-400">•</span> Download CSV reports: upcoming expiries, recent changes, and reviews due</li>
        <li class="flex gap-2"><span class="text-blue-400">•</span> Revoke API keys from any user in the system</li>
        <li class="flex gap-2"><span class="text-blue-400">•</span> Configure periodic review cadence for resources</li>
      </ul>
    </section>

    <!-- Timezone -->
    <section class="bg-tribal-panel rounded-xl border border-tribal-border p-6">
      <h2 class="text-lg font-semibold text-white mb-3">Timezone Support</h2>
      <p class="text-zinc-400 text-sm leading-relaxed">
        Tribal automatically detects your browser's timezone on first login and stores it with your
        account. All timestamps in the UI — audit logs, resource activity, API key usage — are
        displayed in your local timezone. You can change your timezone at any time from the user
        menu in the top-right corner.
      </p>
      <p class="text-zinc-400 text-sm leading-relaxed mt-3">
        CSV and PDF reports always use UTC and label timestamps accordingly, so they remain
        consistent regardless of who downloads them.
      </p>
    </section>

    <!-- Provider detection -->
    <section class="bg-tribal-panel rounded-xl border border-tribal-border p-6">
      <h2 class="text-lg font-semibold text-white mb-3">Automatic Key Detection</h2>
      <p class="text-zinc-400 text-sm leading-relaxed mb-4">
        When adding an API key resource, Tribal can identify the provider from the key's format and
        — where the provider's API supports it — automatically retrieve the expiration date and
        pre-fill rotation instructions. The key is never stored during identification; it exists
        only in memory for the duration of the request.
      </p>
      <div class="flex flex-wrap gap-2">
        <span
          v-for="p in detectionProviders"
          :key="p"
          class="px-2.5 py-1 bg-tribal-card border border-tribal-border rounded-full text-xs text-zinc-300"
        >{{ p }}</span>
      </div>
    </section>

    <!-- API Access -->
    <section class="bg-tribal-panel rounded-xl border border-tribal-border p-6">
      <h2 class="text-lg font-semibold text-white mb-3">API Access</h2>
      <p class="text-zinc-400 text-sm leading-relaxed mb-3">
        Tribal provides a full REST API with Bearer token authentication. Generate an API key from
        the user menu (API Keys). All API activity is attributed to your account in the audit log.
      </p>
      <p class="text-zinc-400 text-sm">
        The API supports all operations available in the UI: creating, updating, and deleting
        resources, as well as reading the audit log and generating reports.
      </p>
    </section>

    <!-- Terraform Provider -->
    <section class="bg-tribal-panel rounded-xl border border-tribal-border p-6">
      <h2 class="text-lg font-semibold text-white mb-3">Terraform Provider</h2>
      <p class="text-zinc-400 text-sm leading-relaxed mb-4">
        Manage credentials as infrastructure-as-code using the
        <a
          href="https://registry.terraform.io/providers/seaburr/tribal/latest"
          target="_blank"
          rel="noopener noreferrer"
          class="text-blue-400 hover:text-blue-300 underline"
        >seaburr/tribal</a>
        Terraform provider. Track resources alongside the infrastructure that uses them.
      </p>

      <pre class="bg-tribal-bg border border-tribal-border rounded-lg p-4 text-sm text-zinc-300 overflow-x-auto leading-relaxed"><code>terraform {
  required_providers {
    tribal = {
      source  = "seaburr/tribal"
      version = "~> 1.0"
    }
  }
}

resource "tribal_resource" "github_token" {
  name                    = "GitHub Actions Token"
  type                    = "API Key"
  dri                     = "platform-team"
  expiration_date         = "2025-12-31"
  purpose                 = "CI/CD pipeline authentication"
  generation_instructions = "Generate in GitHub Settings > Developer settings > PATs"
  slack_webhook           = "https://hooks.slack.com/..."
}</code></pre>
    </section>

    <!-- Contributing: Provider Plugins -->
    <section class="bg-tribal-panel rounded-xl border border-tribal-border p-6">
      <h2 class="text-lg font-semibold text-white mb-1">Contributing: Provider Plugins</h2>
      <p class="text-zinc-400 text-sm leading-relaxed mb-4">
        Tribal is open source at
        <a
          href="https://github.com/seaburr/Tribal"
          target="_blank"
          rel="noopener noreferrer"
          class="text-blue-400 hover:text-blue-300 underline"
        >github.com/seaburr/Tribal</a>.
        The provider system is designed to make adding new key detection plugins straightforward —
        drop a single file in <code class="text-zinc-300 bg-tribal-bg px-1 py-0.5 rounded text-xs">app/providers/</code>
        and it's automatically discovered at startup with no registration required.
      </p>

      <h3 class="text-white font-medium text-sm mb-2">How it works</h3>
      <ul class="space-y-1.5 text-zinc-400 text-sm mb-5">
        <li class="flex gap-2"><span class="text-blue-400">1.</span> Subclass <code class="text-zinc-300 bg-tribal-bg px-1 py-0.5 rounded text-xs">Provider</code> from <code class="text-zinc-300 bg-tribal-bg px-1 py-0.5 rounded text-xs">app/providers/base.py</code></li>
        <li class="flex gap-2"><span class="text-blue-400">2.</span> Define <code class="text-zinc-300 bg-tribal-bg px-1 py-0.5 rounded text-xs">name</code> (display string) and <code class="text-zinc-300 bg-tribal-bg px-1 py-0.5 rounded text-xs">patterns</code> (list of compiled regexes that match the key format)</li>
        <li class="flex gap-2"><span class="text-blue-400">3.</span> Implement <code class="text-zinc-300 bg-tribal-bg px-1 py-0.5 rounded text-xs">introspect(key)</code> — call the provider's API and return an <code class="text-zinc-300 bg-tribal-bg px-1 py-0.5 rounded text-xs">IntrospectionResult</code></li>
        <li class="flex gap-2"><span class="text-blue-400">4.</span> The key is never logged or persisted — treat it as transient and handle errors gracefully</li>
      </ul>

      <h3 class="text-white font-medium text-sm mb-2">IntrospectionResult fields</h3>
      <div class="grid grid-cols-2 gap-2 mb-5">
        <div v-for="field in [
          { name: 'provider', desc: 'Display name of the provider' },
          { name: 'expires_at', desc: 'date object, or None if unknown' },
          { name: 'metadata', desc: 'Dict of extra info shown in the UI' },
          { name: 'rotation_url', desc: 'Link to the provider\'s key management page' },
          { name: 'rotation_steps', desc: 'Step-by-step rotation instructions' },
        ]" :key="field.name" class="bg-tribal-bg border border-tribal-border rounded-lg p-3">
          <code class="text-blue-300 text-xs">{{ field.name }}</code>
          <p class="text-zinc-500 text-xs mt-0.5">{{ field.desc }}</p>
        </div>
      </div>

      <h3 class="text-white font-medium text-sm mb-2">Example provider</h3>
      <pre class="bg-tribal-bg border border-tribal-border rounded-lg p-4 text-xs text-zinc-300 overflow-x-auto leading-relaxed"><code>{{ providerExample }}</code></pre>
    </section>
  </div>
</template>
