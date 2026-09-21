"use client"

import { useState } from "react"
import Link from "next/link"
import { requestPasswordReset } from "@/lib/auth"

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("")
  const [submitting, setSubmitting] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  const [devToken, setDevToken] = useState<string | null>(null)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setSubmitting(true)
    setMessage(null)
    setDevToken(null)
    try {
      const result = await requestPasswordReset(email)
      setMessage(result.message)
      // FIX (remaining-things request): in local dev with no SMTP
      // configured, the backend returns the raw token directly rather
      // than silently going nowhere — surfaced here with a clear label
      // so it's obviously a dev-only affordance, not a security choice
      // that would ever ship with real email configured.
      if (result.devResetToken) setDevToken(result.devResetToken)
    } catch (err) {
      setMessage(err instanceof Error ? err.message : "Something went wrong")
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-[var(--bg-primary)] px-4">
      <div className="w-full max-w-sm">
        <div className="text-center mb-8">
          <h1 className="text-2xl font-semibold text-[var(--text-primary)]">Reset your password</h1>
          <p className="mt-1 text-sm text-[var(--text-muted)]">
            We'll send a reset link to your email
          </p>
        </div>

        {!message ? (
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-xs font-medium text-[var(--text-muted)] mb-1.5">Email</label>
              <input
                type="email"
                required
                autoComplete="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full rounded-lg border border-[var(--border-default)] bg-[var(--bg-card)] px-3 py-2.5 text-sm text-[var(--text-primary)] outline-none focus:border-[var(--border-strong)]"
                placeholder="you@example.com"
              />
            </div>
            <button
              type="submit"
              disabled={submitting}
              className="w-full rounded-lg bg-indigo-500 px-4 py-2.5 text-sm font-medium text-white transition hover:bg-indigo-400 disabled:opacity-50"
            >
              {submitting ? "Sending..." : "Send reset link"}
            </button>
          </form>
        ) : (
          <div className="space-y-4">
            <p className="text-sm text-[var(--text-secondary)] bg-[var(--bg-card)] border border-[var(--border-default)] rounded-lg px-3 py-2.5">
              {message}
            </p>
            {devToken && (
              <div className="text-sm bg-amber-500/10 border border-amber-500/25 rounded-lg px-3 py-2.5">
                <p className="text-amber-300 font-medium mb-1">Dev mode (no email configured)</p>
                <Link
                  href={`/reset-password?token=${devToken}`}
                  className="text-amber-200 underline break-all"
                >
                  Continue to reset password →
                </Link>
              </div>
            )}
          </div>
        )}

        <p className="mt-6 text-center text-sm text-[var(--text-muted)]">
          <Link href="/login" className="text-indigo-400 hover:text-indigo-300">
            Back to log in
          </Link>
        </p>
      </div>
    </div>
  )
}
