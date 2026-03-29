<script setup lang="ts">
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { login, register } from '../api/auth'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const authStore = useAuthStore()

const activeTab = ref<'signin' | 'register'>('signin')
const error = ref('')
const loading = ref(false)

const signinForm = reactive({
  email: '',
  password: '',
})

const registerForm = reactive({
  email: '',
  password: '',
  display_name: '',
})

function validatePassword(password: string): string | null {
  if (password.length < 8) return 'Password must be at least 8 characters.'
  if (!/\d/.test(password)) return 'Password must contain at least one digit.'
  if (!/[^a-zA-Z0-9]/.test(password)) return 'Password must contain at least one special character.'
  return null
}

async function handleSignin() {
  error.value = ''
  loading.value = true
  try {
    await login(signinForm.email, signinForm.password)
    await authStore.load()
    await router.push('/')
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : 'Login failed'
  } finally {
    loading.value = false
  }
}

async function handleRegister() {
  error.value = ''
  const pwError = validatePassword(registerForm.password)
  if (pwError) {
    error.value = pwError
    return
  }
  loading.value = true
  try {
    await register(registerForm.email, registerForm.password, registerForm.display_name || undefined)
    await authStore.load()
    await router.push('/')
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : 'Registration failed'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="min-h-screen bg-tribal-bg flex items-center justify-center px-4">
    <div class="w-full max-w-md">
      <!-- Logo + Title -->
      <div class="text-center mb-8">
        <img
          src="/tribal_logo.png"
          alt="Tribal"
          class="w-16 h-16 object-contain mx-auto mb-3"
        />
        <h1 class="text-2xl font-bold text-blue-400">Tribal</h1>
        <p class="text-zinc-500 text-sm mt-1">Credential Lifecycle Management</p>
      </div>

      <!-- Card -->
      <div class="bg-tribal-panel rounded-xl border border-tribal-border p-8">
        <!-- Tabs -->
        <div class="flex border-b border-tribal-border mb-6">
          <button
            :class="[
              'pb-3 px-1 mr-6 text-sm font-medium transition-colors',
              activeTab === 'signin'
                ? 'text-blue-400 border-b-2 border-blue-400'
                : 'text-zinc-400 hover:text-zinc-200',
            ]"
            @click="activeTab = 'signin'; error = ''"
          >
            Sign In
          </button>
          <button
            :class="[
              'pb-3 px-1 text-sm font-medium transition-colors',
              activeTab === 'register'
                ? 'text-blue-400 border-b-2 border-blue-400'
                : 'text-zinc-400 hover:text-zinc-200',
            ]"
            @click="activeTab = 'register'; error = ''"
          >
            Create Account
          </button>
        </div>

        <!-- Sign In -->
        <form v-if="activeTab === 'signin'" class="space-y-4" @submit.prevent="handleSignin">
          <div>
            <label class="block text-sm font-medium text-zinc-300 mb-1">Email</label>
            <input
              v-model="signinForm.email"
              type="email"
              required
              placeholder="you@example.com"
              class="w-full bg-tribal-card border border-tribal-border rounded-lg px-4 py-2.5 text-white placeholder-zinc-500 focus:outline-none focus:border-blue-500 transition-colors"
            />
          </div>
          <div>
            <label class="block text-sm font-medium text-zinc-300 mb-1">Password</label>
            <input
              v-model="signinForm.password"
              type="password"
              required
              placeholder="••••••••"
              class="w-full bg-tribal-card border border-tribal-border rounded-lg px-4 py-2.5 text-white placeholder-zinc-500 focus:outline-none focus:border-blue-500 transition-colors"
            />
          </div>
          <div v-if="error" class="text-red-400 text-sm bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">
            {{ error }}
          </div>
          <button
            type="submit"
            :disabled="loading"
            class="w-full bg-blue-600 hover:bg-blue-500 text-white font-semibold rounded-lg px-4 py-2.5 transition-colors disabled:opacity-50"
          >
            {{ loading ? 'Signing in...' : 'Sign In' }}
          </button>
        </form>

        <!-- Register -->
        <form v-else class="space-y-4" @submit.prevent="handleRegister">
          <div>
            <label class="block text-sm font-medium text-zinc-300 mb-1">Display Name <span class="text-zinc-500">(optional)</span></label>
            <input
              v-model="registerForm.display_name"
              type="text"
              placeholder="Your Name"
              class="w-full bg-tribal-card border border-tribal-border rounded-lg px-4 py-2.5 text-white placeholder-zinc-500 focus:outline-none focus:border-blue-500 transition-colors"
            />
          </div>
          <div>
            <label class="block text-sm font-medium text-zinc-300 mb-1">Email</label>
            <input
              v-model="registerForm.email"
              type="email"
              required
              placeholder="you@example.com"
              class="w-full bg-tribal-card border border-tribal-border rounded-lg px-4 py-2.5 text-white placeholder-zinc-500 focus:outline-none focus:border-blue-500 transition-colors"
            />
          </div>
          <div>
            <label class="block text-sm font-medium text-zinc-300 mb-1">Password</label>
            <input
              v-model="registerForm.password"
              type="password"
              required
              placeholder="Min 8 chars, 1 digit, 1 special"
              class="w-full bg-tribal-card border border-tribal-border rounded-lg px-4 py-2.5 text-white placeholder-zinc-500 focus:outline-none focus:border-blue-500 transition-colors"
            />
          </div>
          <div v-if="error" class="text-red-400 text-sm bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">
            {{ error }}
          </div>
          <button
            type="submit"
            :disabled="loading"
            class="w-full bg-blue-600 hover:bg-blue-500 text-white font-semibold rounded-lg px-4 py-2.5 transition-colors disabled:opacity-50"
          >
            {{ loading ? 'Creating account...' : 'Create Account' }}
          </button>
        </form>
      </div>
    </div>
  </div>
</template>
