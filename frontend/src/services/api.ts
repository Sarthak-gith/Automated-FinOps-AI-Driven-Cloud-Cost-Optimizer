const API_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000/api'
let token: string | null = localStorage.getItem('finops_token')
export function setToken(value: string | null) {
  token = value
  if (value) localStorage.setItem('finops_token', value)
  else localStorage.removeItem('finops_token')
}
export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers)
  headers.set('Content-Type', 'application/json')
  if (token) headers.set('Authorization', 'Bearer ' + token)
  const response = await fetch(API_URL + path, { ...options, headers })
  if (response.status === 401) setToken(null)
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}))
    throw new Error(payload.detail || 'Request failed (' + response.status + ')')
  }
  return response.json() as Promise<T>
}
export const post = <T,>(path: string, body?: unknown) => api<T>(path, { method:'POST', body:JSON.stringify(body ?? {}) })
export const put = <T,>(path: string, body: unknown) => api<T>(path, { method:'PUT', body:JSON.stringify(body) })
