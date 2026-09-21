"use client"

// ============================================================
// lib/auth.ts — real authentication for NeuroLearn
//
// FIX (auth request): the entire frontend previously hardcoded
// student_id=student_001 everywhere and never sent any credentials —
// any browser could read or write any student's data. This file is the
// single source of truth for "who is logged in" and is consumed by:
//   - apiFetch() in lib/api.ts, which attaches the JWT to every request
//   - <AuthProvider> below, which wraps the whole app in app/layout.tsx
//   - <RouteGuard> (components/RouteGuard.tsx), which redirects to
//     /login when there's no valid session
// ============================================================

import { createContext, useContext, useEffect, useState, type ReactNode } from "react"
import { revokeActiveConsentIfAny, clearStoredWebcamSessionId } from "@/lib/consent"

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api"
const TOKEN_KEY = "neurolearn_token"
const REFRESH_TOKEN_KEY = "neurolearn_refresh_token"
const USER_ID_KEY = "neurolearn_user_id"

// Small companion to the token: several existing api.ts functions take a
// `studentId` path parameter (e.g. /api/crs/{student_id}) that predates
// auth and defaulted to the literal string "student_001". The backend
// now rejects any student_id that isn't the caller's own (403), so those
// defaults need to resolve to the real logged-in user's id. Rather than
// threading the id through every call site via React context, we cache
// it here — set on login/signup/fetchMe, read by getCachedUserId().
export function getCachedUserId(): string | null {
  if (typeof window === "undefined") return null
  return window.localStorage.getItem(USER_ID_KEY)
}

function cacheUserId(id: string) {
  window.localStorage.setItem(USER_ID_KEY, id)
}

export interface AuthUser {
  id: string
  name: string
  email: string
  avatar: string
  level: number
  xp: number
  xpToNextLevel: number
  streak: number
  bestStreak: number
  totalCoursesCompleted: number
  totalWatchTime: number
  joinedDate: string
  rank: number
  badges: unknown[]
}

// ── Token storage ──
// A real Next.js app (not a Claude artifact) — localStorage is fine here.
export function getToken(): string | null {
  if (typeof window === "undefined") return null
  return window.localStorage.getItem(TOKEN_KEY)
}

function getRefreshToken(): string | null {
  if (typeof window === "undefined") return null
  return window.localStorage.getItem(REFRESH_TOKEN_KEY)
}

function setTokens(accessToken: string, refreshToken: string) {
  window.localStorage.setItem(TOKEN_KEY, accessToken)
  window.localStorage.setItem(REFRESH_TOKEN_KEY, refreshToken)
}

function clearToken() {
  window.localStorage.removeItem(TOKEN_KEY)
  window.localStorage.removeItem(REFRESH_TOKEN_KEY)
  window.localStorage.removeItem(USER_ID_KEY)
}

// FIX (remaining-things request): access tokens are now short-lived (30
// min, was 10h) so they need to actually be refreshed rather than just
// used until they happen to expire. This is called by apiFetch (lib/api.ts)
// exactly once on a 401 before giving up — if the refresh itself fails
// (refresh token also expired/revoked), the caller's AuthError propagates
// normally and RouteGuard sends the user to /login.
let refreshInFlight: Promise<boolean> | null = null

export async function tryRefreshAccessToken(): Promise<boolean> {
  if (refreshInFlight) return refreshInFlight
  refreshInFlight = (async () => {
    const refreshToken = getRefreshToken()
    if (!refreshToken) return false
    try {
      const res = await fetch(`${API_BASE}/auth/refresh`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: refreshToken }),
      })
      if (!res.ok) {
        clearToken()
        return false
      }
      const data = await res.json()
      setTokens(data.access_token, data.refresh_token) // rotated — store both
      return true
    } catch {
      return false
    }
  })()
  const result = await refreshInFlight
  refreshInFlight = null
  return result
}

export async function requestPasswordReset(email: string): Promise<{ message: string; devResetToken?: string }> {
  const data = await request("/auth/request-password-reset", { email })
  return { message: data.message, devResetToken: data.dev_reset_token }
}

export async function resetPassword(token: string, newPassword: string): Promise<void> {
  await request("/auth/reset-password", { token, new_password: newPassword })
}

export class AuthError extends Error {
  constructor(message = "Not authenticated") {
    super(message)
    this.name = "AuthError"
  }
}

function normalizeUser(raw: any): AuthUser {
  const user = {
    id: raw.id,
    name: raw.name,
    email: raw.email,
    avatar: raw.avatar,
    level: raw.level,
    xp: raw.xp,
    xpToNextLevel: raw.xp_to_next_level ?? raw.xpToNextLevel,
    streak: raw.streak,
    bestStreak: raw.best_streak ?? raw.bestStreak,
    totalCoursesCompleted: raw.total_courses_completed ?? raw.totalCoursesCompleted,
    totalWatchTime: raw.total_watch_time ?? raw.totalWatchTime,
    joinedDate: raw.joined_date ?? raw.joinedDate,
    rank: raw.rank,
    badges: raw.badges ?? [],
  }
  if (typeof window !== "undefined") cacheUserId(user.id)
  return user
}

async function request(path: string, body: unknown) {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) {
    throw new Error(data.detail || `Request failed (${res.status})`)
  }
  return data
}

export async function signup(email: string, password: string, name: string): Promise<AuthUser> {
  const data = await request("/auth/signup", { email, password, name })
  setTokens(data.access_token, data.refresh_token)
  return normalizeUser(data.user)
}

export async function login(email: string, password: string): Promise<AuthUser> {
  const data = await request("/auth/login", { email, password })
  setTokens(data.access_token, data.refresh_token)
  return normalizeUser(data.user)
}

export async function fetchMe(): Promise<AuthUser> {
  const token = getToken()
  if (!token) throw new AuthError()
  let res = await fetch(`${API_BASE}/auth/me`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  // FIX (remaining-things request): access tokens now expire in 30
  // minutes rather than 10 hours — a 401 here used to just mean "log the
  // user out"; now it first tries a silent refresh, since the far more
  // common case is simply that the access token expired mid-session.
  if (res.status === 401) {
    const refreshed = await tryRefreshAccessToken()
    if (refreshed) {
      res = await fetch(`${API_BASE}/auth/me`, {
        headers: { Authorization: `Bearer ${getToken()}` },
      })
    }
  }
  if (res.status === 401) {
    clearToken()
    throw new AuthError()
  }
  if (!res.ok) throw new Error(`Failed to load profile (${res.status})`)
  return normalizeUser(await res.json())
}

export async function logout() {
  // FIX (auto-revoke at logout): if a CameraFeed with granted consent is
  // currently mounted, revoke it first — best-effort, capped at ~1.5s so
  // a slow/unreachable backend never hangs logout (see lib/consent.ts).
  await revokeActiveConsentIfAny()
  // The webcam session id is intentionally persisted across navigation
  // (see getOrCreateWebcamSessionId) so consent isn't re-asked just from
  // visiting /profile or /dashboard. Logout is one of the three defined
  // triggers that SHOULD end that session, so clear it here.
  clearStoredWebcamSessionId()

  // FIX (remaining-things request): logout previously only cleared the
  // browser's copy of the token — the token itself stayed valid
  // server-side until natural expiry. This actually revokes the refresh
  // token first (best-effort; the token is cleared locally regardless of
  // whether the revoke call succeeds, e.g. if the backend is unreachable).
  const refreshToken = getRefreshToken()
  if (refreshToken) {
    fetch(`${API_BASE}/auth/logout`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
    }).catch(() => {})
  }
  clearToken()
  if (typeof window !== "undefined") window.location.href = "/login"
}

// ── React context ──

interface AuthContextValue {
  user: AuthUser | null
  loading: boolean
  refreshUser: () => Promise<void>
  logout: () => void
}

const AuthContext = createContext<AuthContextValue>({
  user: null,
  loading: true,
  refreshUser: async () => {},
  logout,
})

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null)
  const [loading, setLoading] = useState(true)

  const refreshUser = async () => {
    try {
      const me = await fetchMe()
      setUser(me)
    } catch {
      setUser(null)
    }
  }

  useEffect(() => {
    (async () => {
      if (getToken()) {
        await refreshUser()
      }
      setLoading(false)
    })()
  }, [])

  return (
    <AuthContext.Provider value={{ user, loading, refreshUser, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  return useContext(AuthContext)
}