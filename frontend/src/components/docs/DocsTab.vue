<script setup lang="ts">
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
  'GCP', 'Cloudflare', 'Fastly', 'Slack', 'SendGrid', 'PagerDuty',
  'Vercel', 'Terraform Cloud', 'DigitalOcean',
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
        Tribal is a credential lifecycle manager for teams who are tired of finding out a certificate
        or API key expired in production. It keeps all your secrets in one place, tells you what's
        expiring and when, and makes sure the right people know before it becomes an incident.
      </p>
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
      <h2 class="text-lg font-semibold text-white mb-3">Admin Features</h2>
      <p class="text-zinc-400 text-sm leading-relaxed mb-4">
        Admins have visibility and control over the full system — not just their own resources.
      </p>
      <ul class="space-y-2 text-zinc-400 text-sm">
        <li class="flex gap-2"><span class="text-blue-400">•</span> Full audit log of every create, update, delete, and login event</li>
        <li class="flex gap-2"><span class="text-blue-400">•</span> User management with role assignment</li>
        <li class="flex gap-2"><span class="text-blue-400">•</span> Slack notification scheduling and reminder intervals</li>
        <li class="flex gap-2"><span class="text-blue-400">•</span> Periodic review cadence enforcement — flag resources that haven't been reviewed recently</li>
        <li class="flex gap-2"><span class="text-blue-400">•</span> Soft-delete with recovery — restore accidentally deleted resources or purge them permanently</li>
        <li class="flex gap-2"><span class="text-blue-400">•</span> CSV reports for upcoming expiries, recent changes, and reviews due</li>
      </ul>
    </section>

    <!-- Smart key detection -->
    <section class="bg-tribal-panel rounded-xl border border-tribal-border p-6">
      <h2 class="text-lg font-semibold text-white mb-3">Smart Key Detection</h2>
      <p class="text-zinc-400 text-sm leading-relaxed mb-4">
        Paste an API key when adding a resource and Tribal identifies the provider, pulls the
        expiration date where available, and pre-fills rotation instructions — so you're not
        starting from scratch every time. Keys are never stored during this process.
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
      <p class="text-zinc-400 text-sm leading-relaxed">
        Everything you can do in the UI is available via the REST API — useful for integrating
        Tribal into your existing tooling, CI pipelines, or scripts. Generate an API key from the
        user menu to get started.
      </p>
    </section>

    <!-- Terraform Provider -->
    <section class="bg-tribal-panel rounded-xl border border-tribal-border p-6">
      <h2 class="text-lg font-semibold text-white mb-3">Terraform Provider</h2>
      <p class="text-zinc-400 text-sm leading-relaxed mb-4">
        If you're already managing infrastructure as code, you can manage your credentials the same
        way. The
        <a
          href="https://registry.terraform.io/providers/seaburr/tribal/latest"
          target="_blank"
          rel="noopener noreferrer"
          class="text-blue-400 hover:text-blue-300 underline"
        >seaburr/tribal</a>
        Terraform provider lets you track credentials alongside the infrastructure that uses them.
        Source on
        <a
          href="https://github.com/seaburr/terraform-provider-tribal"
          target="_blank"
          rel="noopener noreferrer"
          class="text-blue-400 hover:text-blue-300 underline"
        >GitHub</a>.
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
        Adding support for a new key provider means dropping a single file into
        <code class="text-zinc-300 bg-tribal-bg px-1 py-0.5 rounded text-xs">app/providers/</code>
        — no registration or wiring required.
      </p>

      <h3 class="text-white font-medium text-sm mb-2">How it works</h3>
      <ul class="space-y-1.5 text-zinc-400 text-sm mb-5">
        <li class="flex gap-2"><span class="text-blue-400">1.</span> Subclass <code class="text-zinc-300 bg-tribal-bg px-1 py-0.5 rounded text-xs">Provider</code> from <code class="text-zinc-300 bg-tribal-bg px-1 py-0.5 rounded text-xs">app/providers/base.py</code></li>
        <li class="flex gap-2"><span class="text-blue-400">2.</span> Define <code class="text-zinc-300 bg-tribal-bg px-1 py-0.5 rounded text-xs">name</code> and <code class="text-zinc-300 bg-tribal-bg px-1 py-0.5 rounded text-xs">patterns</code> — regexes that match the key format. If the key has no distinctive prefix, set <code class="text-zinc-300 bg-tribal-bg px-1 py-0.5 rounded text-xs">patterns = []</code> and users will select the provider manually from the dropdown.</li>
        <li class="flex gap-2"><span class="text-blue-400">3.</span> Implement <code class="text-zinc-300 bg-tribal-bg px-1 py-0.5 rounded text-xs">introspect(key)</code> — call the provider's API and return an <code class="text-zinc-300 bg-tribal-bg px-1 py-0.5 rounded text-xs">IntrospectionResult</code></li>
        <li class="flex gap-2"><span class="text-blue-400">4.</span> Keys are never logged or persisted — handle errors gracefully and always return a result</li>
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
