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
    color: 'bg-amber-500/20 text-amber-400',
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
</script>

<template>
  <div class="max-w-3xl space-y-8">
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
        <li class="flex gap-2"><span class="text-amber-400">•</span> Configure Slack notification schedules and reminder intervals</li>
        <li class="flex gap-2"><span class="text-amber-400">•</span> View the full audit log — every create, update, delete, and login event</li>
        <li class="flex gap-2"><span class="text-amber-400">•</span> Manage users and assign roles (Admin, Member, Read-only)</li>
        <li class="flex gap-2"><span class="text-amber-400">•</span> Soft-delete recovery — restore or permanently purge deleted resources</li>
        <li class="flex gap-2"><span class="text-amber-400">•</span> Download CSV reports: upcoming expiries, recent changes, and reviews due</li>
        <li class="flex gap-2"><span class="text-amber-400">•</span> Revoke API keys from any user in the system</li>
        <li class="flex gap-2"><span class="text-amber-400">•</span> Configure periodic review cadence for resources</li>
      </ul>
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
          href="https://registry.terraform.io/providers/seaburr/tribal"
          target="_blank"
          rel="noopener noreferrer"
          class="text-amber-400 hover:text-amber-300 underline"
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
  </div>
</template>
