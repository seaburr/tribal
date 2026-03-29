export async function apiFetch<T = unknown>(
  url: string,
  options?: RequestInit,
): Promise<T> {
  const method = options?.method?.toUpperCase() ?? 'GET'
  const headers: Record<string, string> = {}

  if (options?.headers) {
    Object.assign(headers, options.headers)
  }

  if (['POST', 'PUT', 'PATCH'].includes(method) && options?.body) {
    headers['Content-Type'] = 'application/json'
  }

  const response = await fetch(url, {
    ...options,
    credentials: 'include',
    headers,
  })

  if (response.status === 401) {
    window.location.href = '/login'
    throw new Error('Unauthorized')
  }

  if (!response.ok) {
    let message = `HTTP ${response.status}`
    try {
      const body = await response.json()
      if (body?.detail) {
        message = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail)
      }
    } catch {
      // ignore parse errors
    }
    throw new Error(message)
  }

  // Handle empty responses (204 No Content, etc.)
  const contentType = response.headers.get('content-type') ?? ''
  if (response.status === 204 || !contentType.includes('application/json')) {
    return undefined as T
  }

  return response.json() as Promise<T>
}
