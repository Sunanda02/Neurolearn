"use client"

import { useState, useEffect } from "react"
import { useRouter } from "next/navigation"
import { motion, AnimatePresence } from "framer-motion"
import { Bell, Search, Zap, Flame, ChevronDown } from "lucide-react"
import { fetchNotifications, type Notification } from "@/lib/api"
import { logout } from "@/lib/auth"

interface NavbarProps {
  studentName: string
  level: number
  xp: number
  xpToNextLevel: number
  streak: number
}

export default function Navbar({ studentName, level, xp, xpToNextLevel, streak }: NavbarProps) {
  const router = useRouter()
  const [notifications, setNotifications] = useState<Notification[]>([])
  const [showNotifs, setShowNotifs] = useState(false)
  const [showProfile, setShowProfile] = useState(false)
  const unreadCount = notifications.filter((n) => !n.read).length
  const xpPercent = Math.round((xp / xpToNextLevel) * 100)

  useEffect(() => {
    fetchNotifications().then(setNotifications).catch(() => {})
  }, [])

  return (
    <motion.nav
      initial={{ opacity: 0, y: -10 }}
      animate={{ opacity: 1, y: 0 }}
      className="sticky top-0 z-40 h-16 border-b border-[var(--border-subtle)] glass-strong flex items-center justify-between px-6"
    >
      {/* Left: Search */}
      <div className="flex items-center gap-3 flex-1 max-w-md">
        <div className="relative flex-1">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--text-muted)]" />
          <input
            type="text"
            placeholder="Search courses, topics..."
            className="w-full pl-10 pr-4 py-2 text-sm rounded-xl bg-[var(--bg-elevated)] border border-[var(--border-subtle)] text-[var(--text-primary)] placeholder:text-[var(--text-muted)] focus:outline-none focus:border-violet-500/50 focus:ring-1 focus:ring-violet-500/20 transition-all"
          />
        </div>
      </div>

      {/* Center: Quick stats */}
      <div className="hidden lg:flex items-center gap-4">
        {/* Level badge */}
        <motion.div
          whileHover={{ scale: 1.05 }}
          className="flex items-center gap-2 px-4 py-1.5 rounded-full bg-gradient-to-r from-violet-500/20 to-purple-500/20 border border-violet-500/30"
        >
          <Zap size={14} className="text-violet-400" />
          <span className="text-xs font-bold text-violet-300">Lv. {level}</span>
          <div className="w-16 h-1.5 rounded-full bg-[var(--bg-primary)] overflow-hidden">
            <motion.div
              initial={{ width: 0 }}
              animate={{ width: `${xpPercent}%` }}
              className="h-full rounded-full progress-animated"
            />
          </div>
          <span className="text-[10px] font-mono text-[var(--text-muted)]">{xpPercent}%</span>
        </motion.div>

        {/* Streak */}
        <motion.div
          whileHover={{ scale: 1.05 }}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-orange-500/10 border border-orange-500/20"
        >
          <Flame size={14} className="text-orange-400" />
          <span className="text-xs font-bold text-orange-300">{streak}</span>
        </motion.div>
      </div>

      {/* Right: Notifications + Profile */}
      <div className="flex items-center gap-3">
        {/* Notifications */}
        <div className="relative">
          <motion.button
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
            onClick={() => { setShowNotifs(!showNotifs); setShowProfile(false) }}
            className="relative w-9 h-9 rounded-xl bg-[var(--bg-elevated)] border border-[var(--border-subtle)] flex items-center justify-center text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:border-[var(--border-default)] transition-all"
          >
            <Bell size={16} />
            {unreadCount > 0 && (
              <motion.div
                initial={{ scale: 0 }}
                animate={{ scale: 1 }}
                className="absolute -top-1 -right-1 w-4 h-4 rounded-full bg-red-500 flex items-center justify-center"
              >
                <span className="text-[10px] font-bold text-white">{unreadCount}</span>
              </motion.div>
            )}
          </motion.button>

          <AnimatePresence>
            {showNotifs && (
              <motion.div
                initial={{ opacity: 0, y: 10, scale: 0.95 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, y: 10, scale: 0.95 }}
                className="absolute right-0 top-12 w-80 rounded-xl bg-[var(--bg-card)] border border-[var(--border-default)] shadow-2xl shadow-black/40 overflow-hidden"
              >
                <div className="px-4 py-3 border-b border-[var(--border-subtle)]">
                  <h3 className="text-sm font-semibold text-[var(--text-primary)]">Notifications</h3>
                </div>
                <div className="max-h-80 overflow-y-auto">
                  {notifications.map((notif) => (
                    <div
                      key={notif.id}
                      className={`px-4 py-3 border-b border-[var(--border-subtle)] hover:bg-[var(--bg-elevated)] transition-colors cursor-pointer ${!notif.read ? "bg-violet-500/5" : ""}`}
                    >
                      <div className="flex items-start gap-3">
                        <span className="text-lg">{notif.icon}</span>
                        <div className="flex-1 min-w-0">
                          <p className="text-xs font-semibold text-[var(--text-primary)]">{notif.title}</p>
                          <p className="text-xs text-[var(--text-muted)] mt-0.5">{notif.message}</p>
                          <p className="text-[10px] text-[var(--text-muted)] mt-1">{notif.timestamp}</p>
                        </div>
                        {!notif.read && <div className="w-2 h-2 rounded-full bg-violet-500 mt-1 shrink-0" />}
                      </div>
                    </div>
                  ))}
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* Profile */}
        <div className="relative">
          <motion.button
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
            onClick={() => { setShowProfile(!showProfile); setShowNotifs(false) }}
            className="flex items-center gap-2 px-2 py-1.5 rounded-xl hover:bg-[var(--bg-elevated)] transition-all"
          >
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-blue-500 to-violet-600 flex items-center justify-center text-white text-xs font-bold shadow-md">
              {studentName.split(" ").map((n) => n[0]).join("")}
            </div>
            <div className="hidden md:block text-left">
              <p className="text-xs font-semibold text-[var(--text-primary)]">{studentName}</p>
              <p className="text-[10px] text-[var(--text-muted)]">{xp} XP</p>
            </div>
            <ChevronDown size={14} className="text-[var(--text-muted)]" />
          </motion.button>

          <AnimatePresence>
            {showProfile && (
              <motion.div
                initial={{ opacity: 0, y: 10, scale: 0.95 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, y: 10, scale: 0.95 }}
                className="absolute right-0 top-12 w-48 rounded-xl bg-[var(--bg-card)] border border-[var(--border-default)] shadow-2xl shadow-black/40 p-1"
              >
                {[
                  { label: "Profile", onClick: () => router.push("/profile") },
                  { label: "Settings", onClick: () => router.push("/profile") },
                  { label: "Help", onClick: () => {} },
                  {
                    label: "Sign Out",
                    // FIX (auth request): this button previously did
                    // nothing at all — no onClick handler existed. It now
                    // actually clears the session and redirects to /login.
                    onClick: () => logout(),
                  },
                ].map((item) => (
                  <button
                    key={item.label}
                    onClick={item.onClick}
                    className="w-full text-left px-3 py-2 text-sm rounded-lg text-[var(--text-secondary)] hover:bg-[var(--bg-elevated)] hover:text-[var(--text-primary)] transition-colors"
                  >
                    {item.label}
                  </button>
                ))}
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
    </motion.nav>
  )
}
