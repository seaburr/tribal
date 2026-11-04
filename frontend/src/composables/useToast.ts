import { ref } from 'vue'

interface Toast {
  id: number
  message: string
  type: 'success' | 'error'
}

const toasts = ref<Toast[]>([])
let nextId = 0

function dismiss(id: number) {
  toasts.value = toasts.value.filter((t) => t.id !== id)
}

export function useToast() {
  function show(message: string, type: 'success' | 'error' = 'success') {
    const id = nextId++
    toasts.value = [...toasts.value.slice(-3), { id, message, type }]
    // Errors stay up longer: they usually need reading, and can be dismissed by hand.
    setTimeout(() => dismiss(id), type === 'error' ? 9000 : 5000)
  }
  return { toasts, show, dismiss }
}
