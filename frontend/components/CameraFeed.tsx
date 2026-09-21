"use client"

/**
 * CameraFeed — Webcam capture + behavioral_cue scoring pipeline
 *
 * PIPELINE (runs every 500ms while video plays):
 *   1. getUserMedia → <video srcObject={stream}>
 *   2. video.onloadeddata → cameraReady = true
 *   3. canvas.drawImage(video) → canvas.toDataURL("image/jpeg")
 *   4. POST base64 frame → /api/attention/snapshot
 *   5. Parse response → call onAttentionUpdate(snapshot)
 *
 * Every step is logged to console for debugging.
 *
 * FIX (B-1, research fail-closed): this used to fall back to a
 * Math.random()-based fake score (generateLocalDummy) whenever the
 * backend was unreachable or the 2s request timed out, and would
 * display/report that fabricated number as if it were a real
 * measurement. Research mode must fail closed: if a frame cannot be
 * scored by the real backend within the request window, that cycle
 * simply reports nothing — no fabricated score is displayed, and
 * nothing is written as a research measurement. onAttentionUpdate is
 * only ever called with a genuine backend response.
 *
 * FIX (B-7, bind capture to the instructional segment): the frame-capture
 * and send loops now pause — without tearing down the camera stream
 * itself — whenever the video is known to be paused or has ended (see
 * `videoPlayStateKnown` on CameraFeedProps). Previously they ran the
 * whole time the camera was active regardless of play state, for every
 * video type, so frames could keep being captured and sent during a
 * break or after the instructional segment ended.
 *
 * FIX (start/stop/revoke): "Stop Camera" and "Revoke Consent" used to be
 * the same button/action, so pausing the camera silently erased the
 * consent decision too — the student would be re-prompted with the
 * consent modal the next time they pressed the button. These are now
 * three distinct actions (see lib/consent.ts for the shared rationale):
 *   - Start Camera:   resumes capture. Consent is asked at most once per
 *                      session; a prior decision on file is reused.
 *   - Stop Camera:    pauses capture only, consent record untouched, and
 *                      video-play auto-resume is suppressed until the
 *                      student presses Start again.
 *   - Revoke Consent: explicit opt-out; stops capture AND clears consent
 *                      server-side. Also fires automatically at
 *                      study-session completion and at logout.
 */

import { useRef, useState, useEffect, useCallback } from "react"
import { motion } from "framer-motion"
import { Camera, CameraOff, AlertTriangle, Wifi, WifiOff, ShieldOff } from "lucide-react"
import ConsentModal from "./ConsentModal"
import { getToken } from "@/lib/auth"
import { postConsentDecision, registerActiveConsentRevoke } from "@/lib/consent"

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api"
const CAPTURE_INTERVAL_MS = 500 // capture frame every 500ms
const SEND_INTERVAL_MS = 2000   // send to backend every 2s (not every frame)

export interface AttentionSnapshotResponse {
  timestamp: string
  score: number
  state: "attentive" | "inattentive" | "unfocused"
  confidence: number
  message: string
  modelResponse: {
    eyeContact: number
    headPose: string
    faceDetected: boolean
    blinkRate: number
  }
}

interface CameraFeedProps {
  isVideoPlaying: boolean
  /**
   * FIX (B-7): whether `isVideoPlaying` reflects a real, trustworthy
   * pause/play/ended signal for the current video. True for native mp4
   * playback and YouTube embeds (both fire real state-change events).
   * False for a generic opaque third-party iframe, where the parent page
   * has no way to observe play state at all — in that case we fall back
   * to the previous "capture whenever the camera is active" behavior,
   * since there's no reliable segment boundary to bind to. Defaults to
   * true (the safer default: pause capture unless a caller explicitly
   * says it can't know).
   */
  videoPlayStateKnown?: boolean
  videoId: string
  studentId: string
  sessionId: string
  studySessionId?: string | null
  onConsentChange?: (granted: boolean) => void
  onAttentionUpdate?: (snapshot: AttentionSnapshotResponse) => void
  /**
   * Set true by the parent once the study session has finished (e.g. right
   * before navigating to the assessment). Camera consent is auto-revoked
   * when this flips to true — see lib/consent.ts. Leave undefined/false
   * for pages that don't have a "session complete" concept.
   */
  sessionComplete?: boolean
}

/** Normalize snake_case backend JSON → camelCase frontend type */
function normSnap(data: any): AttentionSnapshotResponse {
  const mr = data.model_response || data.modelResponse || {}
  return {
    timestamp: data.timestamp || new Date().toISOString(),
    score: data.score ?? 0,
    state: data.state || "attentive",
    confidence: data.confidence ?? 0.5,
    message: data.message || "",
    modelResponse: {
      eyeContact: mr.eye_contact ?? mr.eyeContact ?? 0,
      headPose: mr.head_pose ?? mr.headPose ?? "forward",
      faceDetected: mr.face_detected ?? mr.faceDetected ?? false,
      blinkRate: mr.blink_rate ?? mr.blinkRate ?? 0,
    },
  }
}

export default function CameraFeed({
  isVideoPlaying,
  videoPlayStateKnown = true,
  videoId,
  studentId,
  sessionId,
  studySessionId,
  onConsentChange,
  onAttentionUpdate,
  sessionComplete,
}: CameraFeedProps) {
  // ── Refs (never stale) ──
  const videoElRef = useRef<HTMLVideoElement>(null)
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const sendLoopRef = useRef<number | null>(null)
  const cameraReadyRef = useRef(false)
  const isSendingRef = useRef(false)
  const latestFrameRef = useRef<string | null>(null)
  // FIX (AbortError race): startCamera() is now called from several sites
  // — the auto-start effect, handleConsentDecision, handleStartCamera,
  // and the error Retry button — and isActive only flips to true AFTER
  // getUserMedia()/play() resolve. Two call sites firing in the same tick
  // (e.g. consent just got granted: handleConsentDecision calls
  // startCamera() directly while the auto-start effect also fires) used
  // to both pass the `!isActive` guard and each reassign
  // `videoEl.srcObject`, aborting the other's pending play() with
  // "AbortError: The play() request was interrupted by a new load
  // request." This ref makes startCamera() a no-op while a start is
  // already in flight or a stream already exists.
  const startingRef = useRef(false)

  // Keep callback/ids in refs so interval never goes stale
  const callbackRef = useRef(onAttentionUpdate)
  callbackRef.current = onAttentionUpdate
  const videoIdRef = useRef(videoId)
  videoIdRef.current = videoId
  const studentIdRef = useRef(studentId)
  studentIdRef.current = studentId
  const sessionIdRef = useRef(sessionId)
  sessionIdRef.current = sessionId
  const studySessionIdRef = useRef(studySessionId)
  studySessionIdRef.current = studySessionId

  // ── UI State ──
  const [isActive, setIsActive] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [isConnected, setIsConnected] = useState(false)
  const [framesSent, setFramesSent] = useState(0)
  const [lastScore, setLastScore] = useState<number | null>(null)
  const [showConsentPrompt, setShowConsentPrompt] = useState(false)

  // FIX (CR6, peer review packet): consent must be resolved before the
  // camera is ever requested. `consentGranted === null` means "not yet
  // asked" (show the modal); `false` means the student opted out
  // (CameraFeed stays permanently off for this session, no retries).
  const [consentGranted, setConsentGranted] = useState<boolean | null>(null)
  const [consentChecked, setConsentChecked] = useState(false)
  const consentGrantedRef = useRef<boolean | null>(null)
  consentGrantedRef.current = consentGranted

  // Stop Camera sets this so the "auto-start when video plays" effect
  // below doesn't immediately restart capture — the camera stays off
  // until the student explicitly presses Start Camera again. Consent
  // itself is untouched by Stop (see file header).
  const [manuallyStopped, setManuallyStopped] = useState(false)
  const manuallyStoppedRef = useRef(false)
  manuallyStoppedRef.current = manuallyStopped

  // On mount, check whether this student already has a consent decision
  // on file (e.g. from a previous session) so we don't re-prompt every time.
  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        const res = await fetch(
          `${API_BASE}/attention/consent?session_id=${encodeURIComponent(sessionId)}`,
          { headers: { ...(getToken() ? { Authorization: `Bearer ${getToken()}` } : {}) } }
        )
        if (!cancelled && res.ok) {
          const data = await res.json()
          setConsentGranted(data.granted === true ? true : data.granted === false && data.granted_at ? false : null)
        }
      } catch {
        // Backend unreachable — fall through to prompting; declining is safe.
      } finally {
        if (!cancelled) setConsentChecked(true)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [studentId, sessionId])

  // ══════════════════════════════════════════════════════════
  // STEP 1: Start webcam — getUserMedia → video.srcObject
  // ══════════════════════════════════════════════════════════
  const startCamera = useCallback(async () => {
    if (consentGrantedRef.current !== true) {
      setShowConsentPrompt(true)
      return
    }
    if (startingRef.current || streamRef.current) {
      // Already starting or already have a live stream — a second
      // concurrent call here is exactly what produced the play()
      // AbortError (see startingRef comment above).
      return
    }
    startingRef.current = true
    setIsLoading(true)
    setError(null)
    cameraReadyRef.current = false

    try {
      if (!navigator.mediaDevices?.getUserMedia) {
        setError(
          "Camera access is unavailable in this browser context. Use Chrome/Edge on localhost or HTTPS, and do not open the app from a file URL."
        )
        return
      }
      console.log("[CameraFeed] Requesting webcam access...")
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { width: { ideal: 640 }, height: { ideal: 480 }, facingMode: "user" },
        audio: false,
      })
      console.log("[CameraFeed] Got webcam stream:", stream.getVideoTracks()[0]?.label)

      streamRef.current = stream
      const videoEl = videoElRef.current
      if (videoEl) {
        videoEl.srcObject = stream

        // CRITICAL: Wait for video to actually have frame data
        videoEl.onloadeddata = () => {
          console.log("[CameraFeed] Video element loaded data — camera READY")
          cameraReadyRef.current = true
        }

        await videoEl.play()
        setIsActive(true)
        console.log("[CameraFeed] Camera active, video playing")
      }
    } catch (err: unknown) {
      const e = err as Error
      // A real concurrent-call collision surfaces here as AbortError —
      // startingRef should prevent that now, but if it ever slips through
      // (e.g. the *other* caller's play() got interrupted), don't show it
      // to the student as a camera failure.
      if (e.name === "AbortError") {
        console.warn("[CameraFeed] play() aborted by a concurrent start — ignoring")
        return
      }
      console.error("[CameraFeed] Camera error:", e)
      if (e.name === "NotAllowedError") setError("Camera permission denied.")
      else if (e.name === "NotFoundError") setError("No camera found.")
      else setError("Camera error: " + e.message)
    } finally {
      startingRef.current = false
      setIsLoading(false)
    }
  }, [])

  // ══════════════════════════════════════════════════════════
  // STEP 2: Capture frame — video → canvas → base64
  // Runs on a fast loop (500ms) to keep latestFrameRef fresh.
  //
  // FIX (B-7): only runs while the video is actually playing, whenever we
  // have a trustworthy signal for that (videoPlayStateKnown). This is the
  // "designated instructional segment" boundary — paused (a break) or
  // ended (after the instructional segment) means no frames are captured,
  // without tearing down the camera stream itself (that's what the
  // separate Stop Camera / Revoke Consent actions are for).
  // ══════════════════════════════════════════════════════════
  useEffect(() => {
    if (!isActive) return
    if (videoPlayStateKnown && !isVideoPlaying) return

    const captureLoop = setInterval(() => {
      const videoEl = videoElRef.current
      const canvas = canvasRef.current
      if (!videoEl || !canvas || !cameraReadyRef.current) return

      // Extra safety: check video dimensions are valid
      if (videoEl.videoWidth === 0 || videoEl.videoHeight === 0) return

      const ctx = canvas.getContext("2d")
      if (!ctx) return

      canvas.width = 320
      canvas.height = 240
      ctx.drawImage(videoEl, 0, 0, 320, 240)
      const base64 = canvas.toDataURL("image/jpeg", 0.6)
      latestFrameRef.current = base64
    }, CAPTURE_INTERVAL_MS)

    console.log("[CameraFeed] Frame capture loop started (every", CAPTURE_INTERVAL_MS, "ms)")

    return () => {
      clearInterval(captureLoop)
      console.log("[CameraFeed] Frame capture loop stopped")
    }
  }, [isActive, isVideoPlaying, videoPlayStateKnown])

  // ══════════════════════════════════════════════════════════
  const stopCamera = useCallback(() => {
    console.log("[CameraFeed] Stopping camera")
    streamRef.current?.getTracks().forEach((t) => t.stop())
    streamRef.current = null
    cameraReadyRef.current = false
    latestFrameRef.current = null
    if (videoElRef.current) videoElRef.current.srcObject = null
    if (sendLoopRef.current) clearInterval(sendLoopRef.current)
    sendLoopRef.current = null
    setIsActive(false)
    setIsConnected(false)
  }, [])
  // STEP 3: Send frame to backend — POST every 2s
  // Runs whenever camera is active AND the video is actually playing,
  // wherever that signal is trustworthy (videoPlayStateKnown — see prop
  // doc above). FIX (B-7): this used to run unconditionally whenever the
  // camera was active, regardless of play state, for every video type —
  // including mp4 and YouTube, both of which DO give a real pause/ended
  // signal via VideoPlayer's onPlayStateChange. That meant frames kept
  // being captured and sent to the backend during pauses/after the video
  // ended, i.e. outside the designated instructional segment. Only a
  // generic opaque third-party iframe (no play-state signal available at
  // all) still runs unconditionally, since there's no boundary to bind to.
  // ══════════════════════════════════════════════════════════
  useEffect(() => {
    if (!isActive || (videoPlayStateKnown && !isVideoPlaying)) {
      if (sendLoopRef.current) {
        clearInterval(sendLoopRef.current)
        sendLoopRef.current = null
      }
      return
    }

    const sendToBackend = async () => {
      // Don't stack requests — skip if previous still in-flight
      if (isSendingRef.current) return
      isSendingRef.current = true

      const frame = latestFrameRef.current
      let delivered = false

      // ── Try real backend with 2s timeout ──
      // CR6: only send a frame if consent was actually granted — this loop
      // only runs while isActive is true, and isActive can now only become
      // true after handleConsentDecision(true) or a prior granted session,
      // but we still check the ref directly as defense-in-depth against a
      // stale closure.
      if (frame && consentGrantedRef.current === true) {
        try {
          const ctrl = new AbortController()
          const timer = setTimeout(() => ctrl.abort(), 2000)

          const res = await fetch(`${API_BASE}/attention/snapshot`, {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              ...(getToken() ? { Authorization: `Bearer ${getToken()}` } : {}),
            },
            signal: ctrl.signal,
            body: JSON.stringify({
              frame_base64: frame,
              video_id: videoIdRef.current,
              student_id: studentIdRef.current,
              session_id: sessionIdRef.current,
              study_session_id: studySessionIdRef.current || undefined,
              consent_confirmed: true,
            }),
          })
          clearTimeout(timer)

          if (res.ok) {
            const data = await res.json()
            const snap = normSnap(data)
            console.log("[CameraFeed] Backend response: score =", snap.score, "state =", snap.state)
            setIsConnected(true)
            setFramesSent((p) => p + 1)
            setLastScore(snap.score)
            callbackRef.current?.(snap)
            delivered = true
          } else if (res.status === 403) {
            setConsentGranted(false)
            consentGrantedRef.current = false
            setShowConsentPrompt(false)
            onConsentChange?.(false)
            stopCamera()
            delivered = true
          }
        } catch (e) {
          // Fetch failed or timed out — fail closed. No fabricated score
          // is generated or displayed; this cycle's measurement is simply
          // missing (B-1). onAttentionUpdate is not called.
          console.log("[CameraFeed] Backend unreachable — measurement missing this cycle (fail-closed)")
        }
      }

      // ── Fail closed: if the real backend did not deliver a scored
      // response, do NOT synthesize one. Just reflect disconnected state. ──
      if (!delivered && consentGrantedRef.current === true) {
        setIsConnected(false)
      }

      isSendingRef.current = false
    }

    // Fire immediately, then every SEND_INTERVAL_MS
    sendToBackend()
    sendLoopRef.current = window.setInterval(sendToBackend, SEND_INTERVAL_MS) as unknown as number

    console.log("[CameraFeed] Send loop started (every", SEND_INTERVAL_MS, "ms)")

    return () => {
      if (sendLoopRef.current) {
        clearInterval(sendLoopRef.current)
        sendLoopRef.current = null
      }
      console.log("[CameraFeed] Send loop stopped")
    }
  }, [isActive, isVideoPlaying, videoPlayStateKnown, onConsentChange])


  // Explicit opt-out: stops capture AND clears the consent record
  // server-side. This is the ONLY path that touches consent — plain
  // "Stop Camera" (below) never calls this.
  const revokeConsent = useCallback(async () => {
    stopCamera()
    setConsentGranted(false)
    consentGrantedRef.current = false
    onConsentChange?.(false)
    await postConsentDecision({
      studentId: studentIdRef.current,
      sessionId: sessionIdRef.current,
      studySessionId: studySessionIdRef.current,
      granted: false,
      token: getToken(),
    }).catch(() => {
      // Local revocation still wins: camera and send loop are already
      // stopped, and consentGranted is already false in this tab.
    })
  }, [onConsentChange, stopCamera])

  // Pauses capture only — consent decision is left completely alone, and
  // the student is not re-prompted next time they press Start.
  const handleStopCamera = useCallback(() => {
    setManuallyStopped(true)
    manuallyStoppedRef.current = true
    stopCamera()
  }, [stopCamera])

  // Auto-start camera when video plays — ONLY if the student has already
  // granted consent (CR6) AND hasn't explicitly pressed Stop Camera this
  // session. If consent is undecided, the modal below handles it and
  // calls startCamera() itself via handleConsentDecision.
  useEffect(() => {
    if (isVideoPlaying && !isActive && !error && consentGranted === true && !manuallyStopped) {
      startCamera()
    }
  }, [isVideoPlaying, isActive, error, consentGranted, manuallyStopped, startCamera])

  const handleConsentDecision = useCallback(
    (granted: boolean) => {
      setConsentGranted(granted)
      consentGrantedRef.current = granted
      setShowConsentPrompt(false)
      onConsentChange?.(granted)
      if (granted && !isActive && !error) startCamera()
      if (!granted) stopCamera()
    },
    [isActive, error, onConsentChange, startCamera, stopCamera]
  )

  // Start Camera: the modal is shown here only when there's no decision
  // on file yet for this session_id (consentGranted !== true covers both
  // "undecided" and "previously declined" — either way we ask, or resume
  // asking, at most once per session). A prior grant just resumes.
  const handleStartCamera = useCallback(() => {
    setManuallyStopped(false)
    manuallyStoppedRef.current = false
    if (consentGrantedRef.current !== true) {
      setShowConsentPrompt(true)
      return
    }
    startCamera()
  }, [startCamera])

  // FIX (auto-revoke on session completion / logout): the currently
  // mounted CameraFeed is the only place that knows student/session ids,
  // so it registers itself as "the" revocable consent session whenever
  // consent is granted. video/page.tsx flips `sessionComplete` right
  // before navigating to the assessment; logout() (lib/auth.tsx) looks
  // this registration up directly since it runs outside React entirely.
  useEffect(() => {
    if (consentGranted === true) {
      registerActiveConsentRevoke(revokeConsent)
    } else {
      registerActiveConsentRevoke(null)
    }
    return () => registerActiveConsentRevoke(null)
  }, [consentGranted, revokeConsent])

  useEffect(() => {
    if (sessionComplete && consentGrantedRef.current === true) {
      void revokeConsent()
    }
  }, [sessionComplete, revokeConsent])

  // Cleanup on unmount — stop the stream, but do NOT revoke consent.
  // Unmounting happens on ordinary navigation/refresh too, and consent
  // must not be silently erased just because the component went away.
  useEffect(() => () => stopCamera(), [stopCamera])

  // ══════════════════════════════════════════════════════════
  // RENDER
  // ══════════════════════════════════════════════════════════
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.4 }}
      className="rounded-2xl overflow-hidden bg-[var(--bg-card)] border border-[var(--border-subtle)]"
    >
      {/* Header */}
      <div className="px-4 py-2.5 border-b border-[var(--border-subtle)] flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Camera size={14} className="text-[var(--text-muted)]" />
          <span className="text-xs font-semibold text-[var(--text-primary)]">Camera Feed</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1" title={isConnected ? "Connected to backend" : "Local fallback"}>
            {isConnected ? <Wifi size={10} className="text-emerald-400" /> : <WifiOff size={10} className="text-amber-400" />}
            <span className="text-[9px] text-[var(--text-muted)]">{isConnected ? "API" : "Local"}</span>
          </div>
          {isActive && (
            <motion.div animate={{ opacity: [1, 0.3, 1] }} transition={{ duration: 1.5, repeat: Infinity }} className="w-2 h-2 rounded-full bg-red-500" />
          )}
        </div>
      </div>

      {/* Consent gate (CR6) — shown once per undecided student, before any
          getUserMedia call ever happens */}
      {consentChecked && consentGranted !== true && (showConsentPrompt || (isVideoPlaying && consentGranted === null)) && (
        <ConsentModal
          studentId={studentId}
          sessionId={sessionId}
          studySessionId={studySessionId}
          onDecision={handleConsentDecision}
        />
      )}

      {/* Camera view */}
      <div className="relative aspect-video bg-[var(--bg-primary)] overflow-hidden">
        {consentGranted === false && (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 p-4 text-center">
            <div className="w-12 h-12 rounded-full bg-[var(--bg-elevated)] flex items-center justify-center">
              <CameraOff size={20} className="text-[var(--text-muted)]" />
            </div>
            <p className="text-xs text-[var(--text-muted)]">
              Camera monitoring is off by your choice. Your readiness score uses a
              neutral behavioral-cue value instead — this does not lower your score.
            </p>
          </div>
        )}

        {consentGranted !== false && !isActive && !error && (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-2">
            <div className="w-12 h-12 rounded-full bg-[var(--bg-elevated)] flex items-center justify-center">
              <CameraOff size={20} className="text-[var(--text-muted)]" />
            </div>
            <p className="text-xs text-[var(--text-muted)]">
              {manuallyStopped
                ? "Camera stopped. Press Start Camera to resume."
                : isVideoPlaying ? "Starting camera..." : "Camera starts when video plays"}
            </p>
          </div>
        )}

        {error && (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 bg-red-500/5 p-4">
            <AlertTriangle size={24} className="text-red-400" />
            <p className="text-xs text-red-400 text-center">{error}</p>
            <button onClick={handleStartCamera} className="text-xs px-3 py-1 rounded-lg bg-red-500/10 text-red-400 border border-red-500/20 hover:bg-red-500/20 transition-colors mt-1">Retry</button>
          </div>
        )}

        {/* Webcam video element — always rendered, hidden when inactive */}
        <video
          ref={videoElRef}
          autoPlay
          playsInline
          muted
          className={`w-full h-full object-cover ${isActive ? "block" : "hidden"}`}
          style={{ transform: "scaleX(-1)" }}
        />

        {/* Hidden canvas for frame extraction */}
        <canvas ref={canvasRef} className="hidden" />

        {/* Overlay badge with live score */}
        {isActive && (
          <div className="absolute top-2 left-2 right-2 flex items-center justify-between">
            <div className="px-2 py-1 rounded-md bg-black/60 backdrop-blur-sm flex items-center gap-1.5">
              <motion.div animate={{ scale: [1, 1.3, 1] }} transition={{ duration: 2, repeat: Infinity }} className="w-1.5 h-1.5 rounded-full bg-red-500" />
              <span className="text-[9px] text-white/80 font-mono">AI Monitor · {framesSent} frames</span>
            </div>
            {lastScore !== null && (
              <div className={`px-2 py-1 rounded-md backdrop-blur-sm text-[10px] font-bold font-mono ${
                lastScore >= 70 ? "bg-emerald-500/30 text-emerald-300" :
                lastScore >= 30 ? "bg-amber-500/30 text-amber-300" :
                "bg-red-500/30 text-red-300"
              }`}>
                Score: {lastScore}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Controls */}
      <div className="p-3 flex flex-col gap-2">
        <div className="flex gap-2">
          {!isActive ? (
            <motion.button whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }} onClick={handleStartCamera} disabled={isLoading}
              className="flex-1 px-4 py-2 text-xs font-semibold rounded-xl bg-gradient-to-r from-violet-500 to-purple-600 text-white hover:shadow-lg hover:shadow-violet-500/20 transition-all disabled:opacity-50">
              {isLoading ? "Starting..." : consentGranted === true ? "Start Camera" : "Review Camera Consent"}
            </motion.button>
          ) : (
            <motion.button whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }} onClick={handleStopCamera}
              className="flex-1 px-4 py-2 text-xs font-semibold rounded-xl bg-white/10 text-white border border-white/15 hover:bg-white/15 transition-all">
              Stop Camera
            </motion.button>
          )}
        </div>

        {/* Revoke Consent — a separate, always-available secondary action
            whenever there's a consent decision to revoke. Distinct from
            Stop Camera: this also clears the consent record server-side,
            so the next Start Camera re-prompts. */}
        {consentGranted === true && (
          <button
            onClick={revokeConsent}
            className="flex items-center justify-center gap-1.5 py-1.5 text-[11px] font-medium text-[var(--text-muted)] hover:text-red-400 transition-colors"
          >
            <ShieldOff size={11} />
            Revoke camera consent
          </button>
        )}
      </div>
    </motion.div>
  )
}