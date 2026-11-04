<script setup lang="ts">
const roles = [
  {
    name: 'Admin',
    color: 'badge-info',
    desc: 'Full control over all resources, users, and notification settings. The account creator cannot be demoted.',
  },
  {
    name: 'Member',
    color: 'badge-ok',
    desc: 'Can create and manage resources, generate API keys, and download reports.',
  },
  {
    name: 'Read-only',
    color: 'badge-neutral',
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
  <div class="space-y-4">
    <!-- Intro -->
    <section class="card card-pad">
      <h2 class="section-title mb-2">What is Tribal?</h2>
      <p class="text-sm leading-relaxed text-zinc-300">
        Tribal is a credential lifecycle manager for teams who are tired of finding out a certificate
        or API key expired in production. It keeps all your secrets in one place, tells you what's
        expiring and when, and makes sure the right people know before it becomes an incident.
      </p>
    </section>

    <!-- Roles -->
    <section class="card card-pad">
      <h2 class="section-title mb-3">Roles</h2>
      <div class="space-y-3">
        <div
          v-for="role in roles"
          :key="role.name"
          class="flex gap-3 rounded-md border border-tribal-border bg-tribal-card p-3"
        >
          <span
            :class="['mt-0.5 shrink-0 self-start', role.color]"
          >
            {{ role.name }}
          </span>
          <p class="text-sm leading-relaxed text-zinc-300">{{ role.desc }}</p>
        </div>
      </div>
    </section>

    <!-- Admin features -->
    <section class="card card-pad">
      <h2 class="section-title mb-2">Admin features</h2>
      <p class="text-sm leading-relaxed text-zinc-300 mb-4">
        Admins have visibility and control over the full system — not just their own resources.
      </p>
      <ul class="space-y-2 text-sm text-zinc-300">
        <li class="flex gap-2"><span class="text-accent-blue-light" aria-hidden="true">•</span> Full audit log of every create, update, delete, and login event</li>
        <li class="flex gap-2"><span class="text-accent-blue-light" aria-hidden="true">•</span> User management with role assignment</li>
        <li class="flex gap-2"><span class="text-accent-blue-light" aria-hidden="true">•</span> Slack notification scheduling and reminder intervals</li>
        <li class="flex gap-2"><span class="text-accent-blue-light" aria-hidden="true">•</span> Periodic review cadence enforcement — flag resources that haven't been reviewed recently</li>
        <li class="flex gap-2"><span class="text-accent-blue-light" aria-hidden="true">•</span> Soft-delete with recovery — restore accidentally deleted resources or purge them permanently</li>
        <li class="flex gap-2"><span class="text-accent-blue-light" aria-hidden="true">•</span> CSV reports for upcoming expiries, recent changes, and reviews due</li>
      </ul>
    </section>

    <!-- Smart key detection -->
    <section class="card card-pad">
      <h2 class="section-title mb-2">Smart key detection</h2>
      <p class="text-sm leading-relaxed text-zinc-300 mb-4">
        Paste an API key when adding a resource and Tribal identifies the provider, pulls the
        expiration date where available, and pre-fills rotation instructions — so you're not
        starting from scratch every time. Keys are never stored during this process.
      </p>
      <div class="flex flex-wrap gap-2">
        <span
          v-for="p in detectionProviders"
          :key="p"
          class="badge-neutral"
        >{{ p }}</span>
      </div>
    </section>

    <!-- API Access -->
    <section class="card card-pad">
      <h2 class="section-title mb-2">API access</h2>
      <p class="text-sm leading-relaxed text-zinc-300">
        Everything you can do in the UI is available via the REST API — useful for integrating
        Tribal into your existing tooling, CI pipelines, or scripts. Generate an API key from the
        user menu to get started.
      </p>
    </section>

    <!-- Terraform Provider -->
    <section class="card card-pad">
      <h2 class="section-title mb-2">Terraform provider</h2>
      <p class="text-sm leading-relaxed text-zinc-300 mb-4">
        If you're already managing infrastructure as code, you can manage your credentials the same
        way. The
        <a
          href="https://registry.terraform.io/providers/seaburr/tribal/latest"
          target="_blank"
          rel="noopener noreferrer"
          class="link underline"
        >seaburr/tribal</a>
        Terraform provider lets you track credentials alongside the infrastructure that uses them.
        Source on
        <a
          href="https://github.com/seaburr/terraform-provider-tribal"
          target="_blank"
          rel="noopener noreferrer"
          class="link underline"
        >GitHub</a>.
      </p>

      <pre class="overflow-x-auto rounded-md border border-tribal-border bg-tribal-bg p-3 text-xs leading-relaxed text-zinc-300"><code>terraform {
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

    <!-- Contributing: provider plugins -->
    <section class="card card-pad">
      <h2 class="section-title mb-1">Contributing: provider plugins</h2>
      <p class="text-sm leading-relaxed text-zinc-300 mb-4">
        Tribal is open source at
        <a
          href="https://github.com/seaburr/Tribal"
          target="_blank"
          rel="noopener noreferrer"
          class="link underline"
        >github.com/seaburr/Tribal</a>.
        Adding support for a new key provider means dropping a single file into
        <code class="mono rounded-sm bg-tribal-bg px-1 py-0.5 text-zinc-200">app/providers/</code>
        — no registration or wiring required.
      </p>

      <h3 class="mb-2 text-sm font-medium text-white">How it works</h3>
      <ul class="space-y-1.5 text-sm text-zinc-300 mb-5">
        <li class="flex gap-2"><span class="text-accent-blue-light" aria-hidden="true">1.</span> Subclass <code class="mono rounded-sm bg-tribal-bg px-1 py-0.5 text-zinc-200">Provider</code> from <code class="mono rounded-sm bg-tribal-bg px-1 py-0.5 text-zinc-200">app/providers/base.py</code></li>
        <li class="flex gap-2"><span class="text-accent-blue-light" aria-hidden="true">2.</span> Define <code class="mono rounded-sm bg-tribal-bg px-1 py-0.5 text-zinc-200">name</code> and <code class="mono rounded-sm bg-tribal-bg px-1 py-0.5 text-zinc-200">patterns</code> — regexes that match the key format. If the key has no distinctive prefix, set <code class="mono rounded-sm bg-tribal-bg px-1 py-0.5 text-zinc-200">patterns = []</code> and users will select the provider manually from the dropdown.</li>
        <li class="flex gap-2"><span class="text-accent-blue-light" aria-hidden="true">3.</span> Implement <code class="mono rounded-sm bg-tribal-bg px-1 py-0.5 text-zinc-200">introspect(key)</code> — call the provider's API and return an <code class="mono rounded-sm bg-tribal-bg px-1 py-0.5 text-zinc-200">IntrospectionResult</code></li>
        <li class="flex gap-2"><span class="text-accent-blue-light" aria-hidden="true">4.</span> Keys are never logged or persisted — handle errors gracefully and always return a result</li>
      </ul>

      <h3 class="mb-2 text-sm font-medium text-white">IntrospectionResult fields</h3>
      <div class="mb-5 grid grid-cols-1 gap-2 sm:grid-cols-2">
        <div v-for="field in [
          { name: 'provider', desc: 'Display name of the provider' },
          { name: 'expires_at', desc: 'date object, or None if unknown' },
          { name: 'metadata', desc: 'Dict of extra info shown in the UI' },
          { name: 'rotation_url', desc: 'Link to the provider\'s key management page' },
          { name: 'rotation_steps', desc: 'Step-by-step rotation instructions' },
        ]" :key="field.name" class="rounded-md border border-tribal-border bg-tribal-bg p-3">
          <code class="mono text-accent-blue-light">{{ field.name }}</code>
          <p class="help mt-0.5">{{ field.desc }}</p>
        </div>
      </div>

      <h3 class="mb-2 text-sm font-medium text-white">Example provider</h3>
      <pre class="overflow-x-auto rounded-md border border-tribal-border bg-tribal-bg p-3 text-xs leading-relaxed text-zinc-300"><code>{{ providerExample }}</code></pre>
    </section>
  </div>
</template>
