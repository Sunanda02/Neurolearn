"use client"

import { useEffect, useState } from "react"
import { motion } from "framer-motion"
import { Trophy, Medal, Crown, Flame, Star, ChevronUp } from "lucide-react"
import { fetchLeaderboard, type LeaderboardEntry } from "@/lib/api"

const rankBadge = (rank: number) => {
  if (rank === 1) return { icon: Crown, color: "text-amber-400", bg: "bg-amber-500/15" }
  if (rank === 2) return { icon: Medal, color: "text-gray-300", bg: "bg-gray-400/15" }
  if (rank === 3) return { icon: Medal, color: "text-amber-600", bg: "bg-amber-700/15" }
  return { icon: Star, color: "text-[var(--text-muted)]", bg: "bg-[var(--bg-elevated)]" }
}

export default function LeaderboardPage() {
  const [entries, setEntries] = useState<LeaderboardEntry[]>([])
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    fetchLeaderboard()
      .then((data) => { setEntries(data); setIsLoading(false) })
      .catch(() => setIsLoading(false))
  }, [])

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-[60vh]">
        <motion.div animate={{ rotate: 360 }} transition={{ duration: 1.5, repeat: Infinity, ease: "linear" }} className="w-10 h-10 border-3 border-violet-500 border-t-transparent rounded-full" />
      </div>
    )
  }

  return (
    <div className="p-6 max-w-3xl mx-auto">
      <motion.div initial={{ opacity: 0, y: -15 }} animate={{ opacity: 1, y: 0 }} className="text-center mb-8">
        <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-amber-500/10 border border-amber-500/20 mb-4">
          <Trophy size={18} className="text-amber-400" />
          <span className="text-sm font-bold text-amber-300">Global Leaderboard</span>
        </div>
        <h1 className="text-2xl font-bold text-[var(--text-primary)]">Top Learners</h1>
      </motion.div>

      {/* Top 3 podium */}
      <div className="grid grid-cols-3 gap-3 mb-8">
        {entries.slice(0, 3).map((entry, i) => {
          const order = [1, 0, 2][i] // 2nd, 1st, 3rd layout
          const e = entries[order]
          if (!e) return null
          const badge = rankBadge(e.rank)
          const isFirst = e.rank === 1

          return (
            <motion.div
              key={e.studentId}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.1 }}
              className={`rounded-2xl p-4 text-center border transition-all ${
                isFirst
                  ? "bg-gradient-to-b from-amber-500/10 to-amber-500/5 border-amber-500/20 shadow-lg shadow-amber-500/5"
                  : "bg-[var(--bg-card)] border-[var(--border-subtle)]"
              } ${isFirst ? "md:-mt-4" : ""}`}
            >
              <div className={`w-12 h-12 rounded-full mx-auto mb-2 flex items-center justify-center ${badge.bg}`}>
                <badge.icon size={20} className={badge.color} />
              </div>
              <div className="w-10 h-10 rounded-full bg-gradient-to-br from-violet-500 to-purple-600 mx-auto mb-2 flex items-center justify-center text-white text-xs font-bold">
                {e.name.split(" ").map((n) => n[0]).join("")}
              </div>
              <p className="text-sm font-bold text-[var(--text-primary)] truncate">{e.name}</p>
              <p className="text-lg font-bold text-violet-400 mt-1">{e.xp.toLocaleString()} XP</p>
              <p className="text-[10px] text-[var(--text-muted)]">Level {e.level}</p>
            </motion.div>
          )
        })}
      </div>

      {/* Full list */}
      <div className="rounded-2xl bg-[var(--bg-card)] border border-[var(--border-subtle)] overflow-hidden">
        <div className="px-5 py-3 border-b border-[var(--border-subtle)] grid grid-cols-12 text-[10px] font-semibold text-[var(--text-muted)] uppercase tracking-wider">
          <span className="col-span-1">#</span>
          <span className="col-span-5">Student</span>
          <span className="col-span-2 text-right">XP</span>
          <span className="col-span-2 text-right">Level</span>
          <span className="col-span-2 text-right">Streak</span>
        </div>

        {entries.map((entry, i) => {
          const isCurrentStudent = entry.studentId === "student_001"
          return (
            <motion.div
              key={entry.studentId}
              initial={{ opacity: 0, x: -10 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: i * 0.03 }}
              className={`px-5 py-3 grid grid-cols-12 items-center border-b border-[var(--border-subtle)] last:border-b-0 transition-colors
                ${isCurrentStudent ? "bg-violet-500/8 border-l-2 border-l-violet-500" : "hover:bg-[var(--bg-elevated)]"}
              `}
            >
              <span className={`col-span-1 text-sm font-bold ${entry.rank <= 3 ? "text-amber-400" : "text-[var(--text-muted)]"}`}>
                {entry.rank}
              </span>
              <div className="col-span-5 flex items-center gap-2">
                <div className={`w-7 h-7 rounded-lg flex items-center justify-center text-[10px] font-bold text-white ${
                  isCurrentStudent ? "bg-gradient-to-br from-violet-500 to-purple-600" : "bg-[var(--bg-elevated)] text-[var(--text-muted)]"
                }`}>
                  {entry.name.split(" ").map((n) => n[0]).join("")}
                </div>
                <span className={`text-xs font-medium ${isCurrentStudent ? "text-violet-300" : "text-[var(--text-primary)]"}`}>
                  {entry.name} {isCurrentStudent && <span className="text-[9px] text-violet-400">(You)</span>}
                </span>
              </div>
              <span className="col-span-2 text-right text-xs font-bold text-[var(--text-primary)]">{entry.xp.toLocaleString()}</span>
              <span className="col-span-2 text-right text-xs text-[var(--text-secondary)]">{entry.level}</span>
              <div className="col-span-2 flex items-center justify-end gap-1">
                <Flame size={10} className="text-orange-400" />
                <span className="text-xs text-[var(--text-secondary)]">{entry.streak}</span>
              </div>
            </motion.div>
          )
        })}
      </div>
    </div>
  )
}
