"use client"

import { useEffect, useState } from "react"
import { motion } from "framer-motion"
import { User, Trophy, Flame, Clock, BookOpen, Star, Calendar, Award } from "lucide-react"
import { fetchStudentProfile, type StudentProfile, type Badge } from "@/lib/api"

const rarityConfig = {
  common:    { label: "Common",    color: "text-gray-400",    bg: "bg-gray-500/10",    border: "border-gray-500/20" },
  rare:      { label: "Rare",      color: "text-blue-400",    bg: "bg-blue-500/10",    border: "border-blue-500/20" },
  epic:      { label: "Epic",      color: "text-purple-400",  bg: "bg-purple-500/10",  border: "border-purple-500/20" },
  legendary: { label: "Legendary", color: "text-amber-400",   bg: "bg-amber-500/10",   border: "border-amber-500/20" },
}

export default function ProfilePage() {
  const [student, setStudent] = useState<StudentProfile | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    fetchStudentProfile()
      .then((s) => { setStudent(s); setIsLoading(false) })
      .catch(() => setIsLoading(false))
  }, [])

  if (isLoading || !student) {
    return (
      <div className="flex items-center justify-center h-[60vh]">
        <motion.div animate={{ rotate: 360 }} transition={{ duration: 1.5, repeat: Infinity, ease: "linear" }} className="w-10 h-10 border-3 border-violet-500 border-t-transparent rounded-full" />
      </div>
    )
  }

  const xpPct = Math.round((student.xp / student.xpToNextLevel) * 100)
  const earnedBadges = student.badges.filter((b) => b.earned)

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-6">
      {/* Profile header */}
      <motion.div
        initial={{ opacity: 0, y: -15 }}
        animate={{ opacity: 1, y: 0 }}
        className="rounded-2xl bg-[var(--bg-card)] border border-[var(--border-subtle)] p-6 flex flex-col md:flex-row items-center gap-6"
      >
        <div className="w-20 h-20 rounded-2xl bg-gradient-to-br from-blue-500 via-violet-500 to-purple-600 flex items-center justify-center text-3xl font-black text-white shadow-xl shadow-violet-500/20">
          {student.name.split(" ").map((n) => n[0]).join("")}
        </div>
        <div className="flex-1 text-center md:text-left">
          <h1 className="text-2xl font-bold text-[var(--text-primary)]">{student.name}</h1>
          <p className="text-xs text-[var(--text-muted)]">{student.email}</p>
          <div className="flex items-center gap-3 mt-3 justify-center md:justify-start flex-wrap">
            <span className="flex items-center gap-1 text-xs px-3 py-1 rounded-full bg-violet-500/10 text-violet-300 border border-violet-500/20">
              <Star size={12} /> Level {student.level}
            </span>
            <span className="flex items-center gap-1 text-xs px-3 py-1 rounded-full bg-amber-500/10 text-amber-300 border border-amber-500/20">
              <Flame size={12} /> {student.streak} day streak
            </span>
            <span className="flex items-center gap-1 text-xs px-3 py-1 rounded-full bg-cyan-500/10 text-cyan-300 border border-cyan-500/20">
              <Trophy size={12} /> Rank #{student.rank}
            </span>
          </div>
        </div>
        {/* XP Circle */}
        <div className="relative w-24 h-24 shrink-0">
          <svg className="w-full h-full -rotate-90" viewBox="0 0 100 100">
            <circle cx="50" cy="50" r="42" fill="none" stroke="var(--border-subtle)" strokeWidth="6" />
            <motion.circle
              cx="50" cy="50" r="42" fill="none" stroke="#8b5cf6" strokeWidth="6" strokeLinecap="round"
              strokeDasharray={2 * Math.PI * 42}
              initial={{ strokeDashoffset: 2 * Math.PI * 42 }}
              animate={{ strokeDashoffset: 2 * Math.PI * 42 * (1 - xpPct / 100) }}
              transition={{ duration: 1, ease: "easeOut" }}
            />
          </svg>
          <div className="absolute inset-0 flex flex-col items-center justify-center">
            <span className="text-lg font-bold text-[var(--text-primary)]">{xpPct}%</span>
            <span className="text-[8px] text-[var(--text-muted)]">{student.xp}/{student.xpToNextLevel}</span>
          </div>
        </div>
      </motion.div>

      {/* Stats grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          { icon: BookOpen, label: "Courses Done", value: student.totalCoursesCompleted, color: "text-emerald-400" },
          { icon: Clock, label: "Watch Time", value: `${Math.floor(student.totalWatchTime / 60)}h ${student.totalWatchTime % 60}m`, color: "text-blue-400" },
          { icon: Flame, label: "Best Streak", value: `${student.bestStreak} days`, color: "text-orange-400" },
          { icon: Calendar, label: "Joined", value: new Date(student.joinedDate).toLocaleDateString("en-US", { month: "short", year: "numeric" }), color: "text-violet-400" },
        ].map((stat, i) => (
          <motion.div
            key={stat.label}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.08 }}
            className="rounded-xl p-4 bg-[var(--bg-card)] border border-[var(--border-subtle)]"
          >
            <stat.icon size={18} className={stat.color} />
            <p className="text-xl font-bold text-[var(--text-primary)] mt-2">{stat.value}</p>
            <p className="text-[10px] text-[var(--text-muted)]">{stat.label}</p>
          </motion.div>
        ))}
      </div>

      {/* Achievements */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.3 }}
        className="rounded-2xl bg-[var(--bg-card)] border border-[var(--border-subtle)] p-6"
      >
        <div className="flex items-center justify-between mb-5">
          <div className="flex items-center gap-2">
            <Award size={18} className="text-amber-400" />
            <h2 className="text-base font-bold text-[var(--text-primary)]">Achievements</h2>
          </div>
          <span className="text-xs text-[var(--text-muted)]">{earnedBadges.length}/{student.badges.length} earned</span>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {student.badges.map((badge, i) => {
            const rc = rarityConfig[badge.rarity]
            return (
              <motion.div
                key={badge.id}
                initial={{ opacity: 0, scale: 0.8 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ delay: 0.3 + i * 0.05 }}
                whileHover={badge.earned ? { scale: 1.05, y: -2 } : {}}
                className={`relative p-4 rounded-xl text-center transition-all cursor-pointer border
                  ${badge.earned
                    ? `${rc.bg} ${rc.border}`
                    : "bg-[var(--bg-elevated)] border-[var(--border-subtle)] opacity-40 grayscale"
                  }
                `}
              >
                <span className="text-3xl mb-2 block">{badge.icon}</span>
                <p className="text-xs font-bold text-[var(--text-primary)]">{badge.name}</p>
                <p className="text-[9px] text-[var(--text-muted)] mt-0.5">{badge.description}</p>
                <span className={`text-[8px] font-bold mt-2 inline-block px-2 py-0.5 rounded-full ${rc.color} ${rc.bg} ${rc.border}`}>
                  {rc.label}
                </span>
                {badge.earned && (
                  <div className="absolute -top-1.5 -right-1.5 w-5 h-5 rounded-full bg-emerald-500 flex items-center justify-center shadow-sm">
                    <span className="text-[9px] text-white font-bold">✓</span>
                  </div>
                )}
              </motion.div>
            )
          })}
        </div>

        {/* Progress bar */}
        <div className="mt-5 pt-4 border-t border-[var(--border-subtle)]">
          <div className="w-full h-2 rounded-full bg-[var(--bg-primary)] overflow-hidden">
            <motion.div
              initial={{ width: 0 }}
              animate={{ width: `${(earnedBadges.length / student.badges.length) * 100}%` }}
              transition={{ duration: 1 }}
              className="h-full rounded-full"
              style={{ background: "linear-gradient(90deg, #8b5cf6, #a855f7, #ec4899)" }}
            />
          </div>
          <p className="text-[10px] text-[var(--text-muted)] mt-1 text-center">
            {Math.round((earnedBadges.length / student.badges.length) * 100)}% complete
          </p>
        </div>
      </motion.div>
    </div>
  )
}
