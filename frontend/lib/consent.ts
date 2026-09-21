"use client"

/**
 * lib/consent.ts — shared webcam-consent persistence + cross-module revoke
 * registry.
 *
 * FIX (start/stop/revoke semantics): Start Camera, Stop Camera, and Revoke
 * Consent are three distinct actions now (previously "Revoke Camera" did
 * both stop-and-revoke in one click, and there was no way to pause the
 * camera without also erasing the consent decision):
 *
 *   - Start Camera  — resumes capture. Consent is asked at most once per
 *     session: the decision is persisted server-side against session_id
 *     (see ConsentModal.tsx / CameraFeed.tsx), so pressing Start again
 *     later in the same session never re-opens the modal.
 *   - Stop Camera   — pauses capture only. The consent record is left
 *     untouched, so Start resumes without re-prompting.
 *   - Revoke Consent — explicit opt-out, always available as a secondary
 *     action while consent is on file. Stops capture AND clears the
 *     consent record server-side (granted=false), matching the existing
 *     "declining/revoking never lowers your score" behavior.
 *
 * Consent must also be revoked automatically, without a manual click, at
 * two points that happen outside CameraFeed's own component tree:
 *   1. study-session completion (the learner moves on to the assessment)
 *   2. logout
 * The mounted CameraFeed is the only thing that knows the current
 * studentId/sessionId/studySessionId, so it registers a revoke callback
 * here whenever consent is granted and clears it on unmount/decline.
 * logout() (lib/auth.tsx) looks the callback up instead of reaching into
 * React state it has no access to.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api"
const WEBCAM_SESSION_STORAGE_KEY = "neurolearn_webcam_session_id"

function generateWebcamSessionId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return `webcam_${crypto.randomUUID()}`
  }
  return `webcam_${Date.now()}_${Math.random().toString(16).slice(2)}`
}

/**
 * FIX (consent re-asked on navigation): the id used to live in React
 * state seeded fresh on every mount of the video page, so navigating to
 * /profile or /dashboard and back (a full unmount/remount, not just a
 * video switch within the page — the earlier "A-1" fix only covered the
 * latter) minted a brand-new session_id with no consent record on file.
 * The student saw the consent modal again even though they'd already
 * granted it minutes earlier.
 *
 * Consent must only be re-asked after one of three triggers: manual
 * revoke, study-session completion, or logout — never merely from
 * navigating between pages. Persisting the id in sessionStorage (survives
 * navigation and reloads, cleared when the tab/browser closes) fixes
 * that; logout() (lib/auth.tsx) also clears it explicitly via
 * clearStoredWebcamSessionId() below so a fresh login always starts a
 * clean session boundary.
 */
export function getOrCreateWebcamSessionId(): string {
  if (typeof window === "undefined") return generateWebcamSessionId()
  try {
    const existing = window.sessionStorage.getItem(WEBCAM_SESSION_STORAGE_KEY)
    if (existing) return existing
    const created = generateWebcamSessionId()
    window.sessionStorage.setItem(WEBCAM_SESSION_STORAGE_KEY, created)
    return created
  } catch {
    // sessionStorage unavailable (e.g. strict privacy mode) — fall back
    // to a page-mount-scoped id; consent will simply be re-asked on
    // navigation in that browser configuration.
    return generateWebcamSessionId()
  }
}

export function clearStoredWebcamSessionId() {
  if (typeof window === "undefined") return
  try {
    window.sessionStorage.removeItem(WEBCAM_SESSION_STORAGE_KEY)
  } catch {
    // ignore — nothing to clean up if storage isn't available
  }
}

export interface ConsentDecisionParams {
  studentId: string
  sessionId: string
  studySessionId?: string | null
  granted: boolean
  retentionDays?: number
  token?: string | null
}

/** POST /api/attention/consent. Returns whether the backend confirmed it. */
export async function postConsentDecision({
  studentId,
  sessionId,
  studySessionId,
  granted,
  retentionDays = 30,
  token,
}: ConsentDecisionParams): Promise<boolean> {
  const res = await fetch(`${API_BASE}/attention/consent`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({
      student_id: studentId,
      session_id: sessionId,
      study_session_id: studySessionId || undefined,
      granted,
      retention_days: retentionDays,
      raw_frames_stored: false,
      version: "1.0",
    }),
  })
  return res.ok
}

// ── Active-session revoke registry ──
// Only one CameraFeed is meaningfully "live" at a time (one video page per
// browser tab), so a single-slot registry is enough. It is intentionally
// module state, not persisted anywhere — it exists purely so logout(),
// which runs outside React, can trigger a real server-side revoke instead
// of only clearing the local auth token.
let activeRevoke: (() => Promise<void>) | null = null

export function registerActiveConsentRevoke(fn: (() => Promise<void>) | null) {
  activeRevoke = fn
}

/**
 * Best-effort revoke of whatever camera-consent session is currently
 * mounted, if any. Never throws and never blocks the caller longer than
 * `timeoutMs` — logout must complete even if the backend is unreachable.
 */
export async function revokeActiveConsentIfAny(timeoutMs = 1500): Promise<void> {
  const fn = activeRevoke
  if (!fn) return
  try {
    await Promise.race([
      fn(),
      new Promise<void>((resolve) => setTimeout(resolve, timeoutMs)),
    ])
  } catch {
    // Swallow — logout must never be blocked by a consent-revoke failure.
  }
}