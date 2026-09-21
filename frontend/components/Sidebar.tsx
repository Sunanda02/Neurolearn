"use client"

import { useState } from "react"
import Link from "next/link"
import { usePathname } from "next/navigation"
import { motion, AnimatePresence } from "framer-motion"
import {
  LayoutDashboard,
  PlayCircle,
  ClipboardCheck,
  Trophy,
  BarChart3,
  User,
  Settings,
  HelpCircle,
  ChevronLeft,
  ChevronRight,
  Flame,
  Star,
  Sparkles,      // ← NEW
} from "lucide-react"

interface SidebarProps {
  xp?: number
  xpToNextLevel?: number
  level?: number
  streak?: number
}

const menuItems = [
  { label: "Dashboard",     icon: LayoutDashboard, href: "/dashboard" },
  { label: "Video Learning",icon: PlayCircle,       href: "/video"     },
  { label: "Assessment",    icon: ClipboardCheck,   href: "/assessment"},
  { label: "Results",       icon: BarChart3,        href: "/results"   },
  { label: "Leaderboard",   icon: Trophy,           href: "/leaderboard"},
  { label: "Profile",       icon: User,             href: "/profile"   },
  { label: "Auto Course",   icon: Sparkles,         href: "/discover", badge: "NEW" }, // ← NEW
]

export default function Sidebar({ xp = 0, xpToNextLevel = 1, level = 1, streak = 0 }: SidebarProps) {
  const [collapsed, setCollapsed] = useState(false)
  const pathname = usePathname()
  const xpPercent = Math.round((xp / xpToNextLevel) * 100)

  return (
    <>
      <motion.aside
        initial={false}
        animate={{ width: collapsed ? 72 : 260 }}
        transition={{ duration: 0.3, ease: [0.4, 0, 0.2, 1] }}
        className="fixed left-0 top-0 z-50 h-screen flex flex-col border-r border-[var(--border-subtle)] bg-[var(--bg-secondary)] overflow-hidden"
      >
        {/* Brand */}
        <div className="flex items-center gap-3 px-4 h-16 border-b border-[var(--border-subtle)] shrink-0">
          <motion.div
            whileHover={{ rotate: 5, scale: 1.05 }}
            className="w-10 h-10 rounded-xl bg-gradient-to-br from-blue-500 via-violet-500 to-purple-600 flex items-center justify-center shadow-lg shadow-violet-500/20 shrink-0"
          >
            <span className="text-sm font-black text-white">NL</span>
          </motion.div>
          <AnimatePresence>
            {!collapsed && (
              <motion.span
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -10 }}
                className="text-lg font-bold text-[var(--text-primary)] whitespace-nowrap"
              >
                NeuroLearn
              </motion.span>
            )}
          </AnimatePresence>
        </div>

        {/* Nav items */}
        <nav className="flex-1 py-4 px-2 space-y-1 overflow-y-auto">
          {menuItems.map((item) => {
            const isActive = pathname === item.href || pathname?.startsWith(item.href + "/")
            const Icon = item.icon
            const isDiscover = item.href === "/discover"

            return (
              <Link key={item.href} href={item.href}>
                <motion.div
                  whileHover={{ x: 2 }}
                  whileTap={{ scale: 0.98 }}
                  className={`
                    relative flex items-center gap-3 px-3 py-2.5 rounded-xl cursor-pointer transition-all duration-200 group
                    ${isActive
                      ? "bg-gradient-to-r from-violet-500/15 to-purple-500/10 text-[var(--text-primary)]"
                      : isDiscover
                        ? "text-violet-400 hover:text-violet-300 hover:bg-violet-500/10"
                        : "text-[var(--text-muted)] hover:text-[var(--text-secondary)] hover:bg-[var(--bg-elevated)]"
                    }
                  `}
                >
                  {/* Active indicator */}
                  {isActive && (
                    <motion.div
                      layoutId="sidebar-active"
                      className="absolute left-0 top-1/2 -translate-y-1/2 w-1 h-6 rounded-r-full bg-gradient-to-b from-blue-500 to-violet-500"
                      transition={{ type: "spring", stiffness: 350, damping: 30 }}
                    />
                  )}

                  <Icon
                    size={20}
                    className={`shrink-0 transition-colors ${
                      isActive
                        ? "text-violet-400"
                        : isDiscover
                          ? "text-violet-400"
                          : "group-hover:text-violet-400/70"
                    }`}
                  />

                  <AnimatePresence>
                    {!collapsed && (
                      <motion.span
                        initial={{ opacity: 0, x: -10 }}
                        animate={{ opacity: 1, x: 0 }}
                        exit={{ opacity: 0, x: -10 }}
                        className={`text-sm font-medium whitespace-nowrap flex-1 ${isActive ? "font-semibold" : ""}`}
                      >
                        {item.label}
                      </motion.span>
                    )}
                  </AnimatePresence>

                  {/* NEW badge */}
                  {!collapsed && item.badge && !isActive && (
                    <AnimatePresence>
                      <motion.span
                        initial={{ opacity: 0, scale: 0.8 }}
                        animate={{ opacity: 1, scale: 1 }}
                        className="text-[9px] font-bold px-1.5 py-0.5 rounded-full bg-violet-500/20 text-violet-400 border border-violet-500/30"
                      >
                        {item.badge}
                      </motion.span>
                    </AnimatePresence>
                  )}
                </motion.div>
              </Link>
            )
          })}
        </nav>

        {/* Gamification stats (when expanded) */}
        <AnimatePresence>
          {!collapsed && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              exit={{ opacity: 0, height: 0 }}
              className="px-3 pb-3 space-y-3 shrink-0"
            >
              {/* XP Bar */}
              <div className="p-3 rounded-xl bg-[var(--bg-elevated)] border border-[var(--border-subtle)]">
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-1.5">
                    <Star size={14} className="text-amber-400" />
                    <span className="text-xs font-semibold text-[var(--text-secondary)]">Level {level}</span>
                  </div>
                  <span className="text-xs font-mono text-violet-400">{xp}/{xpToNextLevel}</span>
                </div>
                <div className="w-full h-1.5 rounded-full bg-[var(--bg-primary)] overflow-hidden">
                  <motion.div
                    initial={{ width: 0 }}
                    animate={{ width: `${xpPercent}%` }}
                    transition={{ duration: 1, ease: "easeOut" }}
                    className="h-full rounded-full progress-animated"
                  />
                </div>
              </div>

              {/* Streak */}
              <div className="flex items-center gap-2 px-3 py-2 rounded-xl bg-[var(--bg-elevated)] border border-[var(--border-subtle)]">
                <Flame size={16} className="text-orange-400" />
                <span className="text-xs font-semibold text-[var(--text-secondary)]">{streak} day streak</span>
                {streak >= 7 && (
                  <motion.span
                    animate={{ scale: [1, 1.2, 1] }}
                    transition={{ duration: 1.5, repeat: Infinity }}
                    className="text-xs"
                  >
                    🔥
                  </motion.span>
                )}
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Bottom actions */}
        <div className="px-2 pb-3 space-y-1 border-t border-[var(--border-subtle)] pt-3 shrink-0">
          {[
            { icon: Settings, label: "Settings" },
            { icon: HelpCircle, label: "Help" },
          ].map((item) => (
            <motion.button
              key={item.label}
              whileHover={{ x: 2 }}
              className="w-full flex items-center gap-3 px-3 py-2.5 rounded-xl text-[var(--text-muted)] hover:text-[var(--text-secondary)] hover:bg-[var(--bg-elevated)] transition-all duration-200"
            >
              <item.icon size={18} className="shrink-0" />
              <AnimatePresence>
                {!collapsed && (
                  <motion.span
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                    className="text-sm font-medium"
                  >
                    {item.label}
                  </motion.span>
                )}
              </AnimatePresence>
            </motion.button>
          ))}
        </div>

        {/* Collapse toggle */}
        <motion.button
          whileHover={{ scale: 1.1 }}
          whileTap={{ scale: 0.95 }}
          onClick={() => setCollapsed(!collapsed)}
          className="absolute top-4 -right-3 w-6 h-6 rounded-full bg-[var(--bg-elevated)] border border-[var(--border-default)] flex items-center justify-center text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:border-violet-500/50 transition-colors z-50 shadow-md"
        >
          {collapsed ? <ChevronRight size={12} /> : <ChevronLeft size={12} />}
        </motion.button>
      </motion.aside>

      {/* Spacer for content */}
      <motion.div
        initial={false}
        animate={{ width: collapsed ? 72 : 260 }}
        transition={{ duration: 0.3, ease: [0.4, 0, 0.2, 1] }}
        className="shrink-0 hidden md:block"
      />
    </>
  )
}