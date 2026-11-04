import { nextTick, onBeforeUnmount, shallowRef, watch, type Ref } from 'vue'

// Wires a native <dialog> to an `open` flag: showModal() gives focus containment, an inert background and Escape.
// On open focus moves to `initialFocus` (selector inside the dialog, default: first [data-autofocus], else first
// focusable); on close focus returns to whatever had it before. Backdrop click and Escape both call `onCancel`.
// Open dialogs, innermost last. Nested dialogs (a confirm on top of a modal) share the page scroll lock, and anything
// that must stay interactive above a modal (toasts) has to live inside the top one: the rest of the page is inert.
export const modalStack = shallowRef<HTMLDialogElement[]>([])

export function useModal(
  dialog: Ref<HTMLDialogElement | null>,
  isOpen: () => boolean,
  onCancel: () => void,
  initialFocus = '[data-autofocus]',
) {
  let previous: HTMLElement | null = null
  let shown = false

  function show() {
    const d = dialog.value
    if (!d || d.open) return
    previous = document.activeElement as HTMLElement | null
    d.showModal()
    shown = true
    modalStack.value = [...modalStack.value, d]
    document.documentElement.classList.add('overflow-hidden')
    nextTick(() => {
      // Separate lookups: one combined selector returns document order, which would pick a header close button.
      const target =
        d.querySelector<HTMLElement>(initialFocus) ??
        d.querySelector<HTMLElement>('input:not([disabled]), select:not([disabled]), textarea:not([disabled])') ??
        d.querySelector<HTMLElement>('button:not([disabled])')
      target?.focus()
    })
  }

  function hide() {
    const d = dialog.value
    if (d?.open) d.close()
    if (!shown) return
    shown = false
    modalStack.value = modalStack.value.filter((m) => m !== d)
    if (modalStack.value.length === 0) document.documentElement.classList.remove('overflow-hidden')
    previous?.focus?.()
    previous = null
  }

  watch(
    [isOpen, dialog],
    () => {
      if (isOpen()) show()
      else hide()
    },
    { flush: 'post', immediate: true },
  )
  onBeforeUnmount(hide)

  return {
    // bind on <dialog>: @cancel="m.onNativeCancel" @click="m.onBackdrop"
    onNativeCancel(e: Event) {
      e.preventDefault() // parent decides: it flips `open`, the watcher closes
      onCancel()
    },
    onBackdrop(e: MouseEvent) {
      if (e.target === dialog.value) onCancel()
    },
  }
}
