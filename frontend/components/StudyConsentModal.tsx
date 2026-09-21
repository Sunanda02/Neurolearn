"use client"

/**
 * StudyConsentModal — study-participation consent gate
 *
 * FIX (A-2 follow-up): the backend now refuses to create a research
 * record (ResearchParticipant / StudySession, and anything downstream)
 * until study-participation consent is on file server-side
 * (routers/research.py, data/database.py). That backend fix shipped
 * before this frontend modal existed, so every video-page load hit a
 * hard 403 with no way for the student to actually grant consent — the
 * app was completely broken. This modal is that missing consent step.
 *
 * This is a separate decision from webcam consent (ConsentModal.tsx) —
 * the mentor guidelines are explicit that camera choice and study
 * consent are separate. Declining here does not touch webcam consent at
 * all; a student who declines the camera can still take part in the
 * study, and vice versa.
 *
 * Participation is voluntary and adult students are eligible per the
 * study's population/eligibility criteria; this modal doesn't re-verify
 * adult status, only records the participation decision itself.
 */

import { useState } from "react"
import { createPortal } from "react-dom"
import { motion, AnimatePresence } from "framer-motion"
import { FlaskConical, ShieldCheck, AlertTriangle } from "lucide-react"

interface StudyConsentModalProps {
  onDecision: (granted: boolean) => void
  /** Called when the student declines — the page decides where to send them. */
  onDecline: () => void
}

export default function StudyConsentModal({ onDecision, onDecline }: StudyConsentModalProps) {
  const [submitting, setSubmitting] = useState(false)
  const [saveError, setSaveError] = useState<string | null>(null)

  const submit = async (granted: boolean) => {
    setSubmitting(true)
    setSaveError(null)
    try {
      const { setStudyConsent } = await import("@/lib/api")
      await setStudyConsent(granted)
      setSubmitting(false)
      if (granted) {
        onDecision(true)
      } else {
        onDecline()
      }
    } catch {
      setSubmitting(false)
      // FAIL CLOSED: a failed save must not let the page proceed as if
      // consent were granted. Keep the modal open so the student can
      // retry (mirrors ConsentModal.tsx's fail-closed behavior).
      setSaveError(
        "We couldn't save your choice. Please check your connection and try again."
      )
    }
  }

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
            <div className="rounded-full bg-emerald-500/20 p-2">
              <FlaskConical className="h-5 w-5 text-emerald-400" />
            </div>
            <div>
              <h2 className="text-lg font-semibold">Take part in this research study?</h2>
              <p className="mt-1 text-sm text-white/60">
                This lesson and its assessment are part of a research study on
                adaptive learning.
              </p>
            </div>
          </div>

          <ul className="mt-4 space-y-2 text-sm text-white/70">
            <li className="flex gap-2">
              <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-emerald-400" />
              Participation is voluntary and separate from your grades — declining
              does not affect them.
            </li>
            <li className="flex gap-2">
              <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-emerald-400" />
              This is a separate choice from webcam/behavioral-cue monitoring, which
              is asked about on its own.
            </li>
            <li className="flex gap-2">
              <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-emerald-400" />
              You can change this choice later from your profile's privacy settings.
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
              className="flex-1 rounded-lg bg-emerald-500 px-4 py-2.5 text-sm font-medium text-white transition hover:bg-emerald-400 disabled:opacity-50"
            >
              {submitting ? "Saving..." : saveError ? "Try again" : "Agree to participate"}
            </button>
            <button
              disabled={submitting}
              onClick={() => submit(false)}
              className="flex-1 rounded-lg border border-white/15 px-4 py-2.5 text-sm font-medium text-white/80 transition hover:bg-white/5 disabled:opacity-50"
            >
              Decline
            </button>
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>,
    document.body
  )
}