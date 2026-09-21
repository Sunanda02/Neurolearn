"use client"

import { motion } from "framer-motion"
import { Brain, Eye, ShieldCheck, TrendingUp, FileText, Info } from "lucide-react"
import type { CrsBlock } from "@/lib/api"

interface CRSPanelProps {
  crs: CrsBlock
}

const COMPONENT_META: {
  key: keyof CrsBlock["components"]
  label: string
  icon: typeof Brain
  color: string
}[] = [
  { key: "performance", label: "Performance", icon: TrendingUp, color: "#10b981" },
  { key: "behavioralCue", label: "Behavioral Cue", icon: Eye, color: "#3b82f6" },
  { key: "integrity", label: "Integrity", icon: ShieldCheck, color: "#f59e0b" },
  { key: "trend", label: "Trend", icon: TrendingUp, color: "#8b5cf6" },
  { key: "complexity", label: "Complexity", icon: FileText, color: "#ec4899" },
]

export default function CRSPanel({ crs }: CRSPanelProps) {
  const radius = 42
  const circumference = 2 * Math.PI * radius
  const offset = circumference - crs.score * circumference

  const bandColor = crs.score > 0.75 ? "#ef4444" : crs.score >= 0.45 ? "#f59e0b" : "#10b981"
  const bandLabel = crs.score > 0.75 ? "Hard band" : crs.score >= 0.45 ? "Medium band" : "Easy band"

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.55 }}
      className="p-4 rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-elevated)]"
    >
      <div className="flex items-center gap-2 mb-4">
        <Brain size={16} className="text-violet-400" />
        <h3 className="text-sm font-bold text-[var(--text-primary)]">Cognitive Readiness Score</h3>
        <span
          className="ml-auto text-[10px] font-semibold px-2 py-0.5 rounded-full"
          style={{ color: bandColor, backgroundColor: `${bandColor}1a` }}
        >
          {bandLabel}
        </span>
      </div>

      <div className="flex items-center gap-5 mb-4">
        {/* Gauge */}
        <div className="relative w-24 h-24 shrink-0">
          <svg className="w-full h-full -rotate-90" viewBox="0 0 96 96">
            <circle cx="48" cy="48" r={radius} fill="none" stroke="var(--border-subtle)" strokeWidth="7" />
            <motion.circle
              cx="48" cy="48" r={radius} fill="none"
              stroke={bandColor} strokeWidth="7" strokeLinecap="round"
              strokeDasharray={circumference}
              initial={{ strokeDashoffset: circumference }}
              animate={{ strokeDashoffset: offset }}
              transition={{ duration: 1.2, ease: "easeOut", delay: 0.3 }}
            />
          </svg>
          <div className="absolute inset-0 flex flex-col items-center justify-center">
            <span className="text-xl font-bold text-[var(--text-primary)]">{crs.scorePct.toFixed(0)}</span>
            <span className="text-[9px] text-[var(--text-muted)]">CRS</span>
          </div>
        </div>

        {/* Component bars */}
        <div className="flex-1 space-y-1.5">
          {COMPONENT_META.map((c, i) => {
            const value = crs.components[c.key]
            const Icon = c.icon
            return (
              <div key={c.key} className="flex items-center gap-2">
                <Icon size={11} style={{ color: c.color }} className="shrink-0" />
                <span className="text-[10px] text-[var(--text-muted)] w-16 shrink-0">{c.label}</span>
                <div className="flex-1 h-1.5 rounded-full bg-[var(--bg-primary)] overflow-hidden">
                  <motion.div
                    className="h-full rounded-full"
                    style={{ backgroundColor: c.color }}
                    initial={{ width: 0 }}
                    animate={{ width: `${value * 100}%` }}
                    transition={{ duration: 0.8, delay: 0.4 + i * 0.07 }}
                  />
                </div>
                <span className="text-[10px] font-semibold text-[var(--text-secondary)] w-8 text-right shrink-0">
                  {(value * 100).toFixed(0)}%
                </span>
              </div>
            )
          })}
        </div>
      </div>

      {/* Explanation */}
      <div className="flex items-start gap-2 p-2 rounded-lg bg-[var(--bg-primary)] border border-[var(--border-subtle)]">
        <Info size={11} className="text-[var(--text-muted)] shrink-0 mt-0.5" />
        <p className="text-[10px] text-[var(--text-muted)] leading-relaxed">{crs.explanation}</p>
      </div>
    </motion.div>
  )
}
