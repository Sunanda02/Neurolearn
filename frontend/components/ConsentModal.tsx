"use client"

/**
 * ConsentModal — webcam behavioral_cue-monitoring consent gate
 *
 * FIX (CR6, peer review packet): NeuroLearn previously started the camera
 * and streamed frames to /api/attention/snapshot with no consent prompt,
 * no retention disclosure, and no opt-out. This modal is shown once per
 * student (or whenever consent hasn't been recorded yet) before
 * CameraFeed is allowed to call getUserMedia, and its answer is persisted
 * via POST /api/attention/consent so the backend can enforce the same
 * rule server-side (see routers/attention.py).
 *
 * Declining does NOT penalize the student: CRS's Behavioral Cue (B) component
 * defaults to a neutral 0.5 when no behavioral-cue data is supplied
 * (backend/ml/crs.py), so opting out only removes a potential *upward*
 * signal, never forces a lower readiness score or an easier/harder tier.
 *
 * FIX (A-3, Claude audit): granting consent previously called
 * onDecision(true) unconditionally in a `finally` block — a network
 * failure was swallowed by an empty `catch`, and even a non-2xx response
 * (403/500/etc.) was never checked at all, since `fetch()` doesn't throw
 * on those. The camera would end up enabled locally with nothing actually
 * persisted server-side. Consent must fail closed: `onDecision(true)` is
 * now only called after a confirmed 2xx response. Declining is different
 * — "camera stays off" is the safe default either way, so a decline is
 * always applied locally even if persisting it fails (CameraFeed will
 * simply re-ask next time, which is also safe).
 */

import { useEffect, useState } from "react"
import { createPortal } from "react-dom"
import { motion, AnimatePresence } from "framer-motion"
import { Camera, ShieldCheck, X, AlertTriangle } from "lucide-react"
import { getToken } from "@/lib/auth"
import { postConsentDecision } from "@/lib/consent"

const RETENTION_DAYS = 30

interface ConsentModalProps {
  studentId: string
  sessionId: string
  studySessionId?: string | null
  onDecision: (granted: boolean) => void
}

export default function ConsentModal({ studentId, sessionId, studySessionId, onDecision }: ConsentModalProps) {
  const [submitting, setSubmitting] = useState(false)
  const [mounted, setMounted] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)

  useEffect(() => {
    setMounted(true)
  }, [])

  const submit = async (granted: boolean) => {
    setSubmitting(true)
    setSaveError(null)

    const persisted = await postConsentDecision({
      studentId,
      sessionId,
      studySessionId,
      granted,
      retentionDays: RETENTION_DAYS,
      token: getToken(),
    }).catch(() => false)

    setSubmitting(false)

    if (!granted) {
      // Declining is always safe to apply locally: the camera stays off
      // either way, whether or not the decline itself was persisted.
      onDecision(false)
      return
    }

    if (persisted) {
      onDecision(true)
    } else {
      // FAIL CLOSED (A-3): a failed grant must NOT enable the camera.
      // Keep the modal open so the student can retry; onDecision(true)
      // is deliberately never called here.
      setSaveError(
        "We couldn't save your choice. Your camera has not been enabled — check your connection and try again."
      )
    }
  }

  if (!mounted) return null

  return createPortal(
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4"
      >
        <motion.div
          initial={{ scale: 0.95, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          className="w-full max-w-md rounded-2xl border border-white/10 bg-neutral-900 p-6 text-white shadow-xl"
        >
          <div className="flex items-start gap-3">
            <div className="rounded-full bg-indigo-500/20 p-2">
              <Camera className="h-5 w-5 text-indigo-400" />
            </div>
            <div>
              <h2 className="text-lg font-semibold">Use your camera for behavioral-cue monitoring?</h2>
              <p className="mt-1 text-sm text-white/60">
                This lesson can estimate your on-screen behavioral cue from your webcam.
              </p>
            </div>
          </div>

          <ul className="mt-4 space-y-2 text-sm text-white/70">
            <li className="flex gap-2">
              <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-emerald-400" />
              Raw video frames are analyzed in memory and are never saved — only a
              numeric behavioral-cue score is stored.
            </li>
            <li className="flex gap-2">
              <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-emerald-400" />
              Stored scores are kept for {RETENTION_DAYS} days, then automatically deleted.
            </li>
            <li className="flex gap-2">
              <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-emerald-400" />
              You can decline or revoke this at any time from your profile's privacy
              settings — declining does not lower your score or lock you into easier
              content; it only removes one input to a five-part readiness estimate.
            </li>
          </ul>

          {saveError && (
            <div className="mt-4 flex items-start gap-2 rounded-lg border border-red-500/20 bg-red-500/10 p-3 text-xs text-red-300">
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
              <span>{saveError}</span>
            </div>
          )}

          <div className="mt-6 flex flex-col gap-2 sm:flex-row-reverse">
            <button
              disabled={submitting}
              onClick={() => submit(true)}
              className="flex-1 rounded-lg bg-indigo-500 px-4 py-2.5 text-sm font-medium text-white transition hover:bg-indigo-400 disabled:opacity-50"
            >
              {submitting ? "Saving..." : saveError ? "Try again" : "Allow camera"}
            </button>
            <button
              disabled={submitting}
              onClick={() => submit(false)}
              className="flex-1 rounded-lg border border-white/15 px-4 py-2.5 text-sm font-medium text-white/80 transition hover:bg-white/5 disabled:opacity-50"
            >
              Continue without camera
            </button>
          </div>
          <button
            aria-label="Dismiss"
            onClick={() => submit(false)}
            className="absolute right-4 top-4 text-white/40 hover:text-white/70"
          >
            <X className="h-4 w-4" />
          </button>
        </motion.div>
      </motion.div>
    </AnimatePresence>
    ,
    document.body
  )
}