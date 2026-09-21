"use client"

import { motion } from "framer-motion"
import { Sparkles } from "lucide-react"
import AutoCourseGenerator from "@/components/AutoCourseGenerator"

/**
 * /discover — Auto Course Generator
 *
 * Previously this file was just `export { default } from "../page"` which
 * re-exported app/page.tsx. Now that app/page.tsx is a redirect to
 * /dashboard, this page carries the actual AutoCourseGenerator content
 * directly so the /discover route continues to work correctly.
 */
export default function DiscoverPage() {
  return (
    <div className="p-6 max-w-[860px] mx-auto space-y-8">

      {/* Page header */}
      <motion.div
        initial={{ opacity: 0, y: -16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
      >
        <div className="flex items-center gap-3 mb-2">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-violet-500/30 to-purple-600/30 border border-violet-500/20 flex items-center justify-center">
            <Sparkles size={20} className="text-violet-400" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-[var(--text-primary)]">
              Auto Course Generator
            </h1>
            <p className="text-sm text-[var(--text-muted)]">
              Type any topic — NeuroLearn finds videos and builds adaptive assessments automatically
            </p>
          </div>
        </div>
      </motion.div>

      {/* How it works */}
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1, duration: 0.4 }}
        className="grid grid-cols-3 gap-3"
      >
        {[
          { step: "1", title: "Enter a topic", desc: "e.g. Operating Systems, React Hooks, Machine Learning", icon: "🔍" },
          { step: "2", title: "We find videos",  desc: "Scrapes YouTube for top educational content — no paid API", icon: "🎬" },
          { step: "3", title: "Assessments ready", desc: "FLAN-T5 generates adaptive quiz questions from transcripts", icon: "🧠" },
        ].map((item, i) => (
          <motion.div
            key={item.step}
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.15 + i * 0.07 }}
            className="rounded-xl p-4 bg-[var(--bg-card)] border border-[var(--border-subtle)] space-y-2"
          >
            <div className="flex items-center gap-2">
              <span className="text-xl">{item.icon}</span>
              <span className="text-xs font-bold text-violet-400 bg-violet-500/10 px-2 py-0.5 rounded-full">
                Step {item.step}
              </span>
            </div>
            <p className="text-sm font-semibold text-[var(--text-primary)]">{item.title}</p>
            <p className="text-xs text-[var(--text-muted)] leading-relaxed">{item.desc}</p>
          </motion.div>
        ))}
      </motion.div>

      {/* Generator */}
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.25, duration: 0.4 }}
        className="rounded-2xl bg-[var(--bg-card)] border border-[var(--border-subtle)] p-6"
      >
        <AutoCourseGenerator />
      </motion.div>

    </div>
  )
}