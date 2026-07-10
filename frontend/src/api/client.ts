const BASE = (import.meta as any).env.VITE_API_BASE || ''

export const USERNAME_KEY = 'jumprope_username'
export const ADMIN_TOKEN_KEY = 'jumprope_admin_token'

export function getUsername(): string {
  return localStorage.getItem(USERNAME_KEY) || ''
}

export function setUsername(name: string): void {
  localStorage.setItem(USERNAME_KEY, name.trim().slice(0, 50))
}

interface Opts {
  method?: string
  body?: any
  admin?: boolean
  query?: Record<string, any>
}

function buildQuery(query?: Record<string, any>): string {
  if (!query) return ''
  const parts: string[] = []
  for (const [k, v] of Object.entries(query)) {
    if (v === undefined || v === null || v === '') continue
    parts.push(`${encodeURIComponent(k)}=${encodeURIComponent(String(v))}`)
  }
  return parts.length ? '?' + parts.join('&') : ''
}

async function request(path: string, opts: Opts = {}): Promise<any> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  const u = getUsername()
  if (u) headers['X-Username'] = encodeURIComponent(u)
  if (opts.admin) {
    const token = localStorage.getItem(ADMIN_TOKEN_KEY)
    if (token) headers['Authorization'] = 'Bearer ' + token
  }
  const res = await fetch(BASE + path + buildQuery(opts.query), {
    method: opts.method || 'GET',
    headers,
    body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined,
  })
  if (!res.ok) {
    let msg = '请求失败'
    try {
      const j = await res.json()
      msg = typeof j.detail === 'string' ? j.detail : Array.isArray(j.detail) ? j.detail[0]?.msg || msg : msg
    } catch {
      /* ignore */
    }
    const err = new Error(msg) as any
    err.status = res.status
    throw err
  }
  if (res.status === 204) return null
  return res.json()
}

export const api = {
  get: (p: string, query?: Record<string, any>, admin = false) => request(p, { method: 'GET', query, admin }),
  post: (p: string, body?: any, admin = false) => request(p, { method: 'POST', body, admin }),
  put: (p: string, body?: any, admin = false) => request(p, { method: 'PUT', body, admin }),
  del: (p: string, admin = false) => request(p, { method: 'DELETE', admin }),
}

export async function uploadForm(path: string, form: FormData, admin = false): Promise<any> {
  const headers: Record<string, string> = {}
  const u = getUsername()
  if (u) headers['X-Username'] = encodeURIComponent(u)
  if (admin) {
    const token = localStorage.getItem(ADMIN_TOKEN_KEY)
    if (token) headers['Authorization'] = 'Bearer ' + token
  }
  const res = await fetch(BASE + path, { method: 'POST', headers, body: form })
  if (!res.ok) {
    let msg = '上传失败'
    try {
      const j = await res.json()
      msg = typeof j.detail === 'string' ? j.detail : msg
    } catch {
      /* ignore */
    }
    throw new Error(msg)
  }
  return res.json()
}

export type JumpVideo = {
  id: number
  username: string
  title: string
  description: string
  video_url: string
  cover_url: string
  media_status: string
  score_status: string
  media_error?: string
  score_error?: string
  duration_sec: number | null
  jump_count: number | null
  speed_per_min: number | null
  fancy_count: number | null
  fancy_duration_sec: number | null
  ai_score: number | null
  ai_score_detail: any
  is_public: boolean
  is_approved: boolean
  published_at: string | null
  upload_date: string
  created_at: string | null
}
