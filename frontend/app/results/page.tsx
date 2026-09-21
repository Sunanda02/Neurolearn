"use client"

import { useSearchParams } from "next/navigation"
import { useState, useCallback, Suspense } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { Download, Mail, Check, X, Loader2, FileText } from "lucide-react"
import ResultCard from "@/components/ResultCard"
import type { AssessmentResult } from "@/lib/api"

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api"

export default function ResultsPage() {
  return (
    <Suspense fallback={
      <div className="flex items-center justify-center h-[70vh]">
        <div className="w-10 h-10 border-3 border-violet-500 border-t-transparent rounded-full animate-spin" />
      </div>
    }>
      <ResultsContent />
    </Suspense>
  )
}

function ResultsContent() {
  const searchParams = useSearchParams()
  const dataParam = searchParams.get("data")
  const attentionParam = searchParams.get("behavioral_cue")
  const courseParam = searchParams.get("course")
  const videoParam = searchParams.get("video")

  const [pdfLoading, setPdfLoading] = useState(false)
  const [emailLoading, setEmailLoading] = useState(false)
  const [emailSent, setEmailSent] = useState(false)
  const [emailError, setEmailError] = useState("")
  const [showEmailModal, setShowEmailModal] = useState(false)
  const [emailAddress, setEmailAddress] = useState("")

  let result: AssessmentResult | null = null
  try {
    if (dataParam) result = JSON.parse(dataParam)
  } catch {}

  let attentionData: any = null
  try {
    if (attentionParam) attentionData = JSON.parse(attentionParam)
  } catch {}

  if (!result) {
    result = {
      sessionId: "demo",
      score: 75,
      totalPoints: 100,
      earnedPoints: 75,
      percentage: 75,
      xpEarned: 112,
      timeSpent: 180,
      correctAnswers: 3,
      totalQuestions: 5,
      difficulty: "medium",
      message: "Well done! You have a solid understanding of the material.",
      nextDifficulty: "hard",
      suggestedTopics: ["Advanced: Performance Optimization", "Practice: Hook Patterns"],
      adaptiveResponse: {
        performanceTrend: "improving",
        recommendedAction: "Great progress! Keep building — you'll unlock harder content soon.",
        nextAssessmentDifficulty: "hard",
        strengthAreas: ["Core Concepts", "Syntax"],
        weakAreas: ["Applied Knowledge"],
      },
    }
  }

  const buildReportPayload = useCallback(() => {
    const attn = attentionData || {
      avgScore: result!.percentage * 0.85,
      scoreHistory: Array.from({ length: 20 }, () => 50 + Math.random() * 40),
      totalSnapshots: 20,
      attentivePercent: 68,
      inattentivePercent: 22,
      unfocusedPercent: 10,
      avgEyeContact: 0.82,
      avgBlinkRate: 16.5,
      headPoseDistribution: { forward: 28, slightly_away: 8, away: 4 },
    }
    return {
      student: { name: "Alex Johnson", email: emailAddress || "student@example.com", id: "student_001", level: 12, xp: 4250 },
      course: { title: courseParam || "Introduction to React", id: courseParam || "course_001" },
      video: { title: videoParam || "Video Session", id: videoParam || "video_001", duration: result!.timeSpent * 3 },
      assessment: result!,
      behavioral_cue: attn,
      transcription: { totalSegments: 15, avgConfidence: 0.932 },
    }
  }, [result, attentionData, courseParam, videoParam, emailAddress])

  const handleDownloadPdf = useCallback(async () => {
    setPdfLoading(true)
    try {
      const payload = buildReportPayload()
      try {
        const res = await fetch(`${API_BASE}/report/generate`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        })
        if (res.ok) {
          const blob = await res.blob()
          const url = URL.createObjectURL(blob)
          const a = document.createElement("a")
          a.href = url
          a.download = `NeuroLearn_Report_${Date.now()}.pdf`
          document.body.appendChild(a)
          a.click()
          document.body.removeChild(a)
          URL.revokeObjectURL(url)
          return
        }
      } catch { /* backend down */ }
      // Fallback: text report
      const text = generateTextReport(payload)
      const blob = new Blob([text], { type: "text/plain" })
      const url = URL.createObjectURL(blob)
      const a = document.createElement("a")
      a.href = url
      a.download = `NeuroLearn_Report_${Date.now()}.txt`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
    } finally {
      setPdfLoading(false)
    }
  }, [buildReportPayload])

  const handleSendEmail = useCallback(async () => {
    if (!emailAddress.includes("@")) { setEmailError("Please enter a valid email address"); return }
    setEmailLoading(true)
    setEmailError("")
    try {
      const payload = buildReportPayload()
      const res = await fetch(`${API_BASE}/report/email`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ toEmail: emailAddress, reportData: payload }),
      })
      if (res.ok) {
        setEmailSent(true)
        setTimeout(() => setShowEmailModal(false), 2000)
      } else {
        const data = await res.json().catch(() => ({}))
        setEmailError(data.detail || "Failed to send. Is SMTP configured on backend?")
      }
    } catch {
      setEmailError("Server unreachable. Start backend with SMTP_USER and SMTP_PASSWORD in .env")
    } finally {
      setEmailLoading(false)
    }
  }, [emailAddress, buildReportPayload])

  return (
    <div className="p-6 max-w-4xl mx-auto">
      <motion.div initial={{ opacity: 0, y: -15 }} animate={{ opacity: 1, y: 0 }} className="text-center mb-8">
        <h1 className="text-2xl font-bold text-[var(--text-primary)] mb-1">Assessment Results</h1>
        <p className="text-xs text-[var(--text-muted)]">Review your performance and adaptive recommendations</p>
      </motion.div>

      <ResultCard result={result} />

      {/* Report Card Actions */}
      <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.5 }}
        className="mt-8 rounded-2xl border border-[var(--border-subtle)] bg-[var(--bg-card)] p-6">
        <div className="flex items-center gap-3 mb-4">
          <div className="w-10 h-10 rounded-xl bg-violet-500/15 flex items-center justify-center">
            <FileText size={20} className="text-violet-400" />
          </div>
          <div>
            <h3 className="text-base font-bold text-[var(--text-primary)]">Report Card</h3>
            <p className="text-xs text-[var(--text-muted)]">Download or email a detailed PDF with scores, behavioral-cue charts, and recommendations</p>
          </div>
        </div>
        <div className="flex flex-wrap gap-3">
          <motion.button whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }} onClick={handleDownloadPdf} disabled={pdfLoading}
            className="flex items-center gap-2 px-5 py-2.5 text-sm font-semibold rounded-xl bg-gradient-to-r from-emerald-500 to-green-600 text-white hover:shadow-lg hover:shadow-emerald-500/20 transition-all disabled:opacity-50">
            {pdfLoading ? <Loader2 size={16} className="animate-spin" /> : <Download size={16} />}
            {pdfLoading ? "Generating..." : "Download PDF Report"}
          </motion.button>
          <motion.button whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }}
            onClick={() => { setShowEmailModal(true); setEmailSent(false); setEmailError("") }}
            className="flex items-center gap-2 px-5 py-2.5 text-sm font-semibold rounded-xl bg-[var(--bg-elevated)] text-[var(--text-secondary)] border border-[var(--border-subtle)] hover:border-violet-500/30 hover:text-violet-400 transition-all">
            <Mail size={16} /> Email Report Card
          </motion.button>
        </div>
      </motion.div>

      {/* Email Modal */}
      <AnimatePresence>
        {showEmailModal && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
            onClick={(e) => e.target === e.currentTarget && setShowEmailModal(false)}>
            <motion.div initial={{ scale: 0.9, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} exit={{ scale: 0.9, opacity: 0 }}
              className="w-full max-w-md rounded-2xl bg-[var(--bg-card)] border border-[var(--border-subtle)] p-6 shadow-2xl">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-bold text-[var(--text-primary)]">Email Report Card</h3>
                <button onClick={() => setShowEmailModal(false)} className="text-[var(--text-muted)] hover:text-[var(--text-primary)]"><X size={18} /></button>
              </div>
              {emailSent ? (
                <div className="flex flex-col items-center gap-3 py-6">
                  <div className="w-14 h-14 rounded-full bg-emerald-500/15 flex items-center justify-center"><Check size={28} className="text-emerald-400" /></div>
                  <p className="text-sm font-semibold text-emerald-400">Report sent successfully!</p>
                  <p className="text-xs text-[var(--text-muted)]">Check {emailAddress} inbox</p>
                </div>
              ) : (
                <>
                  <p className="text-xs text-[var(--text-muted)] mb-4">
                    Enter the email address to receive the full PDF report card with assessment scores, behavioral-cue metrics, graphical analysis, and adaptive recommendations.
                  </p>
                  <input type="email" value={emailAddress} onChange={(e) => setEmailAddress(e.target.value)}
                    placeholder="student@example.com"
                    className="w-full px-4 py-2.5 text-sm rounded-xl bg-[var(--bg-elevated)] border border-[var(--border-subtle)] text-[var(--text-primary)] placeholder:text-[var(--text-muted)] focus:outline-none focus:border-violet-500/50 focus:ring-1 focus:ring-violet-500/20 mb-3"
                    onKeyDown={(e) => e.key === "Enter" && handleSendEmail()} />
                  {emailError && <p className="text-xs text-red-400 mb-3">{emailError}</p>}
                  <motion.button whileHover={{ scale: 1.01 }} whileTap={{ scale: 0.99 }} onClick={handleSendEmail} disabled={emailLoading || !emailAddress}
                    className="w-full flex items-center justify-center gap-2 px-4 py-2.5 text-sm font-semibold rounded-xl bg-gradient-to-r from-violet-500 to-purple-600 text-white hover:shadow-lg hover:shadow-violet-500/20 transition-all disabled:opacity-50">
                    {emailLoading ? <Loader2 size={16} className="animate-spin" /> : <Mail size={16} />}
                    {emailLoading ? "Sending..." : "Send Report"}
                  </motion.button>
                  <p className="text-[10px] text-[var(--text-muted)] mt-3 text-center">
                    Requires backend running with SMTP configured (SMTP_USER, SMTP_PASSWORD in .env)
                  </p>
                </>
              )}
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

function generateTextReport(data: any): string {
  const a = data.assessment, attn = data.behavioral_cue, ar = a.adaptiveResponse || {}
  return `
NEUROLEARN REPORT CARD
===================================
Student:      ${data.student.name}
Course:       ${data.course.title}
Date:         ${new Date().toISOString().split("T")[0]}

ASSESSMENT
  Score:        ${a.percentage}%
  Correct:      ${a.correctAnswers} / ${a.totalQuestions}
  Points:       ${a.earnedPoints} / ${a.totalPoints}
  XP Earned:    +${a.xpEarned}
  Difficulty:   ${a.difficulty}

BEHAVIORAL CUE
  Average:      ${attn.avgScore?.toFixed?.(1) || attn.avgScore}%
  Snapshots:    ${attn.totalSnapshots}
  Eye Contact:  ${((attn.avgEyeContact || 0) * 100).toFixed(0)}%
  High signal band:    ${attn.attentivePercent}%
  Medium signal band:  ${attn.inattentivePercent}%
  Low signal band:     ${attn.unfocusedPercent}%

ADAPTIVE ANALYSIS
  Trend:        ${ar.performanceTrend}
  Next:         ${ar.nextAssessmentDifficulty}
  Strengths:    ${(ar.strengthAreas || []).join(", ")}
  Weak Areas:   ${(ar.weakAreas || []).join(", ")}
  Action:       ${ar.recommendedAction}

Generated by NeuroLearn Platform
`.trim()
}