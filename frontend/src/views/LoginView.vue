<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { login, register } from '../api/auth'
import { getLoginBanner } from '../api/banner'
import { useAuthStore } from '../stores/auth'
import BannerBar from '../components/layout/BannerBar.vue'
import type { Banner } from '../types'

const router = useRouter()
const authStore = useAuthStore()

const activeTab = ref<'signin' | 'register'>('signin')
const error = ref('')
const loading = ref(false)
const loginBanner = ref<Banner | null>(null)

onMounted(async () => {
  try {
    loginBanner.value = await getLoginBanner()
  } catch {
    loginBanner.value = null
  }
})

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
  <div class="flex min-h-screen flex-col">
    <!-- Public announcement banner -->
    <BannerBar :banner="loginBanner" />

    <main class="flex flex-1 items-center justify-center px-4 py-8">
      <div class="w-full max-w-sm">
        <div class="mb-5 text-center">
          <img src="/tribal_logo.png" alt="" class="mx-auto mb-2 h-12 w-12 object-contain" />
          <h1 class="page-title">Tribal</h1>
          <p class="meta mt-0.5">Credential lifecycle management</p>
        </div>

        <div class="card card-pad">
          <div class="mb-4 grid grid-cols-2 gap-1 rounded-md bg-tribal-bg p-1" role="tablist" aria-label="Account">
            <button
              type="button"
              role="tab"
              :aria-selected="activeTab === 'signin'"
              :class="['nav-link justify-center', activeTab === 'signin' ? 'nav-active' : '']"
              @click="activeTab = 'signin'; error = ''"
            >
              Sign in
            </button>
            <button
              type="button"
              role="tab"
              :aria-selected="activeTab === 'register'"
              :class="['nav-link justify-center', activeTab === 'register' ? 'nav-active' : '']"
              @click="activeTab = 'register'; error = ''"
            >
              Create account
            </button>
          </div>

          <form v-if="activeTab === 'signin'" class="space-y-4" @submit.prevent="handleSignin">
            <div>
              <label for="signin-email" class="label">Email</label>
              <input id="signin-email" v-model="signinForm.email" type="email" required autocomplete="username" placeholder="you@example.com" class="input" :aria-invalid="error ? 'true' : undefined" />
            </div>
            <div>
              <label for="signin-password" class="label">Password</label>
              <input id="signin-password" v-model="signinForm.password" type="password" required autocomplete="current-password" class="input" :aria-invalid="error ? 'true' : undefined" />
            </div>
            <div v-if="error" class="alert-error" role="alert">{{ error }}</div>
            <button type="submit" :disabled="loading" class="btn-primary btn-block">
              {{ loading ? 'Signing in…' : 'Sign in' }}
            </button>
          </form>

          <form v-else class="space-y-4" @submit.prevent="handleRegister">
            <div>
              <label for="register-name" class="label">Display name <span class="font-normal text-zinc-400">(optional)</span></label>
              <input id="register-name" v-model="registerForm.display_name" type="text" autocomplete="name" placeholder="Your name" class="input" />
            </div>
            <div>
              <label for="register-email" class="label">Email</label>
              <input id="register-email" v-model="registerForm.email" type="email" required autocomplete="username" placeholder="you@example.com" class="input" />
            </div>
            <div>
              <label for="register-password" class="label">Password</label>
              <input id="register-password" v-model="registerForm.password" type="password" required autocomplete="new-password" aria-describedby="register-password-help" class="input" :aria-invalid="error ? 'true' : undefined" />
              <p id="register-password-help" class="help">At least 8 characters, with 1 digit and 1 special character.</p>
            </div>
            <div v-if="error" class="alert-error" role="alert">{{ error }}</div>
            <button type="submit" :disabled="loading" class="btn-primary btn-block">
              {{ loading ? 'Creating account…' : 'Create account' }}
            </button>
          </form>
        </div>
      </div>
    </main>
  </div>
</template>
