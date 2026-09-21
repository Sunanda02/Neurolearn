"use client"

import { useState, useEffect } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { Eye, AlertCircle, Brain, Activity } from "lucide-react"
import type { AttentionSnapshotResponse } from "./CameraFeed"

interface AttentionPanelProps {
  latestSnapshot: AttentionSnapshotResponse | null
  sessionAverage: number
  scoreHistory: number[]
}

// FIX (B-6/J-1): these used to label the learner directly with a
// psychological-state judgment ("Focused" / "Distracted" / "Unfocused",
// each paired with an emotive emoji). The mentor guidelines prohibit
// telling a learner the system has determined they are focused,
// distracted, or otherwise in a psychological state. This now shows only
// a neutral operational band for the camera-derived behavioural signal.
const stateConfig = {
  attentive: { label: "High signal band", ringColor: "#10b981" },
  inattentive: { label: "Medium signal band", ringColor: "#f59e0b" },
  unfocused: { label: "Low signal band", ringColor: "#ef4444" },
}

export default function AttentionPanel({
  latestSnapshot,
  sessionAverage,
  scoreHistory,
}: AttentionPanelProps) {
  const [animatedScore, setAnimatedScore] = useState(0)

  const state = latestSnapshot?.state || "attentive"
  const score = latestSnapshot?.score ?? 0
  const config = stateConfig[state]
  // Use camelCase — matches normSnap() output from CameraFeed
  const modelData = latestSnapshot?.modelResponse

  useEffect(() => {
    const target = score
    const step = target > animatedScore ? 2 : -2
    const timer = setInterval(() => {
      setAnimatedScore((prev) => {
        const next = prev + step
        if ((step > 0 && next >= target) || (step < 0 && next <= target)) {
          clearInterval(timer)
          return target
        }
        return next
      })
    }, 20)
    return () => clearInterval(timer)
  }, [score])

  const radius = 52
  const circumference = 2 * Math.PI * radius
  const strokeDashoffset = circumference - (animatedScore / 100) * circumference

  const sparklinePath = (() => {
    if (scoreHistory.length < 2) return ""
    const w = 100
    const h = 24
    const step = w / (scoreHistory.length - 1)
    return scoreHistory
      .map((s, i) => `${i === 0 ? "M" : "L"} ${i * step} ${h - (s / 100) * h}`)
      .join(" ")
  })()

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.4, delay: 0.1 }}
      className="rounded-2xl overflow-hidden bg-[var(--bg-card)] border border-[var(--border-subtle)]"
    >
      {/* Header */}
      <div className="px-4 py-2.5 border-b border-[var(--border-subtle)] flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Eye size={14} className="text-[var(--text-muted)]" />
          <span className="text-xs font-semibold text-[var(--text-primary)]">Behavioral Cue Monitor</span>
        </div>
        <span className="text-[10px] px-2 py-0.5 rounded-full bg-[var(--bg-elevated)] text-[var(--text-muted)] font-mono">
          Avg: {Math.round(sessionAverage)}%
        </span>
      </div>

      <div className="p-5 flex flex-col items-center">
        {/* Circular gauge */}
        <div className="relative w-32 h-32 mb-4">
          <svg className="w-full h-full -rotate-90" viewBox="0 0 120 120">
            <circle cx="60" cy="60" r={radius} fill="none" stroke="var(--border-subtle)" strokeWidth="8" />
            <motion.circle
              cx="60" cy="60" r={radius} fill="none"
              stroke={config.ringColor} strokeWidth="8" strokeLinecap="round"
              strokeDasharray={circumference}
              initial={{ strokeDashoffset: circumference }}
              animate={{ strokeDashoffset }}
              transition={{ duration: 0.8, ease: "easeOut" }}
            />
          </svg>
          <div className="absolute inset-0 flex flex-col items-center justify-center">
            <span className="text-3xl font-bold text-[var(--text-primary)]">{animatedScore}</span>
            <p className="text-[10px] text-[var(--text-muted)] -mt-0.5">/ 100</p>
          </div>
          {state === "attentive" && (
            <motion.div
              animate={{ scale: [1, 1.15, 1], opacity: [0.3, 0.1, 0.3] }}
              transition={{ duration: 2, repeat: Infinity }}
              className="absolute inset-0 rounded-full"
              style={{ boxShadow: `0 0 30px ${config.ringColor}40` }}
            />
          )}
        </div>

        {/* State badge */}
        <motion.div
          key={state}
          initial={{ y: 10, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          className="flex items-center gap-2 px-4 py-1.5 rounded-full mb-2"
          style={{
            background: `linear-gradient(135deg, ${config.ringColor}15, ${config.ringColor}08)`,
            border: `1px solid ${config.ringColor}30`,
          }}
        >
          <span className="text-xs font-bold" style={{ color: config.ringColor }}>{config.label}</span>
        </motion.div>

        {/* Message */}
        <AnimatePresence mode="wait">
          <motion.p
            key={latestSnapshot?.message || "waiting"}
            initial={{ opacity: 0, y: 5 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -5 }}
            className="text-xs text-[var(--text-muted)] text-center px-2 mb-4 min-h-[2rem]"
          >
            {latestSnapshot?.message || "Waiting for camera data..."}
          </motion.p>
        </AnimatePresence>

        {/* Sparkline */}
        {scoreHistory.length > 1 && (
          <div className="w-full mb-4">
            <p className="text-[10px] text-[var(--text-muted)] mb-1">Session Trend</p>
            <svg viewBox="0 0 100 24" className="w-full h-6" preserveAspectRatio="none">
              <path d={sparklinePath} fill="none" stroke={config.ringColor} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" vectorEffect="non-scaling-stroke" />
            </svg>
          </div>
        )}

        {/* Model metrics — camelCase field names */}
        {modelData && (
          <div className="w-full grid grid-cols-2 gap-2">
            <div className="p-2 rounded-lg bg-[var(--bg-elevated)] border border-[var(--border-subtle)]">
              <div className="flex items-center gap-1 mb-1">
                <Eye size={10} className="text-violet-400" />
                <span className="text-[9px] text-[var(--text-muted)]">Eye Contact</span>
              </div>
              <p className="text-xs font-bold text-[var(--text-primary)]">
                {(modelData.eyeContact * 100).toFixed(0)}%
              </p>
            </div>
            <div className="p-2 rounded-lg bg-[var(--bg-elevated)] border border-[var(--border-subtle)]">
              <div className="flex items-center gap-1 mb-1">
                <Brain size={10} className="text-cyan-400" />
                <span className="text-[9px] text-[var(--text-muted)]">Head Pose</span>
              </div>
              <p className="text-xs font-bold text-[var(--text-primary)] capitalize">
                {(modelData.headPose || "").replace("_", " ")}
              </p>
            </div>
            <div className="p-2 rounded-lg bg-[var(--bg-elevated)] border border-[var(--border-subtle)]">
              <div className="flex items-center gap-1 mb-1">
                <Activity size={10} className="text-emerald-400" />
                <span className="text-[9px] text-[var(--text-muted)]">Blink Rate</span>
              </div>
              <p className="text-xs font-bold text-[var(--text-primary)]">
                {modelData.blinkRate}/min
              </p>
            </div>
            <div className="p-2 rounded-lg bg-[var(--bg-elevated)] border border-[var(--border-subtle)]">
              <div className="flex items-center gap-1 mb-1">
                <AlertCircle size={10} className="text-amber-400" />
                <span className="text-[9px] text-[var(--text-muted)]">Confidence</span>
              </div>
              <p className="text-xs font-bold text-[var(--text-primary)]">
                {((latestSnapshot?.confidence || 0) * 100).toFixed(0)}%
              </p>
            </div>
          </div>
        )}
      </div>
    </motion.div>
  )
}