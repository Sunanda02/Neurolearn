"use client"

import { useEffect, useState } from "react"
import { motion } from "framer-motion"
import { useRouter } from "next/navigation"
import {
  Trophy,
  ArrowRight,
  RotateCcw,
  TrendingUp,
  TrendingDown,
  Minus,
  Target,
  Zap,
  BookOpen,
  ShieldCheck,
  AlertTriangle,
} from "lucide-react"
import type { AssessmentResult } from "@/lib/api"
import CRSPanel from "./CRSPanel"

interface ResultCardProps {
  result: AssessmentResult
}

export default function ResultCard({ result }: ResultCardProps) {
  const router = useRouter()
  const [animatedScore, setAnimatedScore] = useState(0)
  const [showConfetti, setShowConfetti] = useState(false)

  const score = result.percentage

  // Animate score counter
  useEffect(() => {
    let frame: number
    const duration = 1500
    const start = performance.now()
    const animate = (now: number) => {
      const elapsed = now - start
      const pct = Math.min(elapsed / duration, 1)
      const eased = 1 - Math.pow(1 - pct, 3) // ease-out cubic
      setAnimatedScore(Math.round(score * eased))
      if (pct < 1) frame = requestAnimationFrame(animate)
    }
    frame = requestAnimationFrame(animate)
    if (score >= 80) {
      setTimeout(() => setShowConfetti(true), 800)
      setTimeout(() => setShowConfetti(false), 4000)
    }
    return () => cancelAnimationFrame(frame)
  }, [score])

  // SVG ring
  const radius = 60
  const circumference = 2 * Math.PI * radius
  const offset = circumference - (animatedScore / 100) * circumference

  const scoreColor =
    score >= 80 ? "#10b981" : score >= 60 ? "#f59e0b" : "#ef4444"
  const scoreLabel =
    score >= 90 ? "Outstanding!" : score >= 80 ? "Excellent!" : score >= 60 ? "Good Job!" : score >= 40 ? "Keep Practicing" : "Try Again"
  const scoreEmoji =
    score >= 90 ? "🏆" : score >= 80 ? "🎉" : score >= 60 ? "👍" : score >= 40 ? "📚" : "💪"

  const trendIcon = {
    improving: TrendingUp,
    stable: Minus,
    declining: TrendingDown,
  }
  const TrendIcon = trendIcon[result.adaptiveResponse?.performanceTrend || "stable"]
  const trendColor = {
    improving: "text-emerald-400",
    stable: "text-amber-400",
    declining: "text-red-400",
  }

  return (
    <>
      {/* Confetti */}
      {showConfetti && (
        <div className="fixed inset-0 pointer-events-none z-50">
          {Array.from({ length: 60 }).map((_, i) => (
            <motion.div
              key={i}
              initial={{
                opacity: 1,
                x: typeof window !== "undefined" ? Math.random() * window.innerWidth : 500,
                y: -20,
                rotate: 0,
                scale: Math.random() * 0.5 + 0.5,
              }}
              animate={{
                opacity: 0,
                y: typeof window !== "undefined" ? window.innerHeight + 50 : 900,
                x: `+=${(Math.random() - 0.5) * 200}`,
                rotate: Math.random() * 720,
              }}
              transition={{ duration: Math.random() * 2 + 2, ease: "easeIn" }}
              className="fixed w-2 h-2 rounded-full"
              style={{
                background: ["#8b5cf6", "#a855f7", "#ec4899", "#10b981", "#f59e0b", "#3b82f6"][i % 6],
              }}
            />
          ))}
        </div>
      )}

      <motion.div
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.5 }}
        className="rounded-2xl overflow-hidden bg-[var(--bg-card)] border border-[var(--border-subtle)] max-w-2xl mx-auto shadow-2xl shadow-black/20"
      >
        {/* Header gradient */}
        <div
          className="p-8 text-center"
          style={{ background: `linear-gradient(135deg, ${scoreColor}15, ${scoreColor}05)` }}
        >
          <motion.p
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.3 }}
            className="text-4xl mb-2"
          >
            {scoreEmoji}
          </motion.p>
          <motion.h2
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.4 }}
            className="text-2xl font-bold text-[var(--text-primary)]"
          >
            {scoreLabel}
          </motion.h2>
          <p className="text-sm text-[var(--text-muted)] mt-1">Assessment Complete</p>
        </div>

        <div className="p-8 space-y-8">
          {/* Circular score */}
          <div className="flex justify-center">
            <div className="relative w-36 h-36">
              <svg className="w-full h-full -rotate-90" viewBox="0 0 140 140">
                <circle cx="70" cy="70" r={radius} fill="none" stroke="var(--border-subtle)" strokeWidth="10" />
                <motion.circle
                  cx="70" cy="70" r={radius} fill="none"
                  stroke={scoreColor} strokeWidth="10" strokeLinecap="round"
                  strokeDasharray={circumference}
                  initial={{ strokeDashoffset: circumference }}
                  animate={{ strokeDashoffset: offset }}
                  transition={{ duration: 1.5, ease: "easeOut", delay: 0.3 }}
                />
              </svg>
              <div className="absolute inset-0 flex flex-col items-center justify-center">
                <motion.span
                  initial={{ opacity: 0, scale: 0.5 }}
                  animate={{ opacity: 1, scale: 1 }}
                  transition={{ delay: 0.8 }}
                  className="text-4xl font-bold text-[var(--text-primary)]"
                >
                  {animatedScore}%
                </motion.span>
                <span className="text-[10px] text-[var(--text-muted)]">Score</span>
              </div>
            </div>
          </div>

          {/* FIX (real XP request): result.totalXp/newLevel/leveledUp are
              the actual persisted values from the backend (see
              routers/assessment.py's _apply_xp) — previously nothing on
              this page reflected whether XP had really been banked, only
              the per-assessment delta below. A level-up is now visibly
              celebrated instead of being silently invisible. */}
          {result.leveledUp && (
            <motion.div
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ delay: 0.3 }}
              className="mb-4 flex items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-amber-500/15 to-orange-500/15 border border-amber-500/30 px-4 py-3"
            >
              <span className="text-lg">🎉</span>
              <p className="text-sm font-semibold text-amber-300">
                Level up! You're now level {result.newLevel}
              </p>
            </motion.div>
          )}

          {/* Stats grid */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.5 }}
            className="grid grid-cols-3 gap-3"
          >
            <div className="p-3 rounded-xl bg-[var(--bg-elevated)] border border-[var(--border-subtle)] text-center">
              <p className="text-2xl font-bold text-violet-400">+{result.xpEarned}</p>
              <p className="text-[10px] text-[var(--text-muted)] mt-0.5">
                XP Earned{typeof result.totalXp === "number" ? ` · ${result.totalXp} total` : ""}
              </p>
            </div>
            <div className="p-3 rounded-xl bg-[var(--bg-elevated)] border border-[var(--border-subtle)] text-center">
              <p className="text-2xl font-bold text-cyan-400">{result.correctAnswers}/{result.totalQuestions}</p>
              <p className="text-[10px] text-[var(--text-muted)] mt-0.5">Correct</p>
            </div>
            <div className="p-3 rounded-xl bg-[var(--bg-elevated)] border border-[var(--border-subtle)] text-center">
              <p className="text-2xl font-bold text-amber-400">{Math.floor(result.timeSpent / 60)}m {result.timeSpent % 60}s</p>
              <p className="text-[10px] text-[var(--text-muted)] mt-0.5">Time</p>
            </div>

          </motion.div>

          {/* Adaptive feedback */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.6 }}
            className="p-4 rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-elevated)]"
          >
            <div className="flex items-center gap-2 mb-3">
              <Target size={16} className="text-violet-400" />
              <h3 className="text-sm font-bold text-[var(--text-primary)]">Adaptive Analysis</h3>
            </div>

            <p className="text-xs text-[var(--text-secondary)] mb-4">{result.message}</p>

            {/* Trend + Next difficulty */}
            <div className="grid grid-cols-2 gap-3 mb-4">
              <div className="flex items-center gap-2 p-2 rounded-lg bg-[var(--bg-primary)]">
                <TrendIcon size={14} className={trendColor[result.adaptiveResponse?.performanceTrend || "stable"]} />
                <div>
                  <p className="text-[10px] text-[var(--text-muted)]">Trend</p>
                  <p className="text-xs font-semibold text-[var(--text-primary)] capitalize">
                    {result.adaptiveResponse?.performanceTrend || "stable"}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-2 p-2 rounded-lg bg-[var(--bg-primary)]">
                <Zap size={14} className="text-violet-400" />
                <div>
                  <p className="text-[10px] text-[var(--text-muted)]">Next Level</p>
                  <p className="text-xs font-semibold text-[var(--text-primary)] capitalize">
                    {result.nextDifficulty}
                  </p>
                </div>
              </div>
            </div>

            {/* Strengths / Weaknesses */}
            {(result.adaptiveResponse?.strengthAreas?.length > 0 || result.adaptiveResponse?.weakAreas?.length > 0) && (
              <div className="grid grid-cols-2 gap-3">
                {result.adaptiveResponse?.strengthAreas?.length > 0 && (
                  <div className="p-2 rounded-lg bg-emerald-500/5 border border-emerald-500/10">
                    <div className="flex items-center gap-1 mb-1">
                      <ShieldCheck size={10} className="text-emerald-400" />
                      <span className="text-[9px] font-semibold text-emerald-400">Strengths</span>
                    </div>
                    {result.adaptiveResponse.strengthAreas.map((s) => (
                      <p key={s} className="text-[10px] text-emerald-300/80">{s}</p>
                    ))}
                  </div>
                )}
                {result.adaptiveResponse?.weakAreas?.length > 0 && (
                  <div className="p-2 rounded-lg bg-amber-500/5 border border-amber-500/10">
                    <div className="flex items-center gap-1 mb-1">
                      <AlertTriangle size={10} className="text-amber-400" />
                      <span className="text-[9px] font-semibold text-amber-400">Improve</span>
                    </div>
                    {result.adaptiveResponse.weakAreas.map((w) => (
                      <p key={w} className="text-[10px] text-amber-300/80">{w}</p>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* Recommended action */}
            {result.adaptiveResponse?.recommendedAction && (
              <p className="text-[11px] text-[var(--text-muted)] italic mt-3 p-2 rounded-lg bg-[var(--bg-primary)] border border-[var(--border-subtle)]">
                💡 {result.adaptiveResponse.recommendedAction}
              </p>
            )}
          </motion.div>

          {/* Cognitive Readiness Score — NeuroLearn-MCL (Phase 13) */}
          {result.adaptiveResponse?.crs && (
            <CRSPanel crs={result.adaptiveResponse.crs} />
          )}

          {/* Suggested topics */}
          {result.suggestedTopics?.length > 0 && (
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.7 }}>
              <p className="text-xs text-[var(--text-muted)] mb-2">Suggested Next:</p>
              <div className="flex flex-wrap gap-2">
                {result.suggestedTopics.map((t) => (
                  <span key={t} className="text-[10px] px-3 py-1 rounded-full bg-violet-500/10 text-violet-300 border border-violet-500/15">
                    {t}
                  </span>
                ))}
              </div>
            </motion.div>
          )}

          {/* Action buttons */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.8 }}
            className="flex gap-3 pt-2"
          >
            <motion.button
              whileHover={{ scale: 1.01 }}
              whileTap={{ scale: 0.99 }}
              onClick={() => router.push("/dashboard")}
              className="flex-1 py-3 rounded-xl font-semibold text-sm bg-gradient-to-r from-violet-500 to-purple-600 text-white hover:shadow-lg hover:shadow-violet-500/20 transition-all flex items-center justify-center gap-2"
            >
              Continue Learning <ArrowRight size={16} />
            </motion.button>
            <motion.button
              whileHover={{ scale: 1.01 }}
              whileTap={{ scale: 0.99 }}
              onClick={() => router.back()}
              className="px-5 py-3 rounded-xl font-semibold text-sm bg-[var(--bg-elevated)] text-[var(--text-secondary)] border border-[var(--border-subtle)] hover:border-[var(--border-default)] transition-all flex items-center gap-2"
            >
              <RotateCcw size={14} /> Retry
            </motion.button>
          </motion.div>
        </div>
      </motion.div>
    </>
  )
}
