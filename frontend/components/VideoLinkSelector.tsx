"use client"

import { motion } from "framer-motion"
import { Play, CheckCircle2, Clock, ChevronRight } from "lucide-react"
import type { VideoLink } from "@/lib/api"

interface VideoLinkSelectorProps {
  videos: VideoLink[]
  activeVideoId: string | null
  onSelect: (video: VideoLink) => void
  courseTitle: string
}

export default function VideoLinkSelector({
  videos,
  activeVideoId,
  onSelect,
  courseTitle,
}: VideoLinkSelectorProps) {
  const safeVideos = videos || []

  const formatDuration = (seconds: number) => {
    const m = Math.floor(seconds / 60)
    const s = seconds % 60
    return `${m}:${s.toString().padStart(2, "0")}`
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.15 }}
      className="rounded-2xl bg-[var(--bg-card)] border border-[var(--border-subtle)] overflow-hidden"
    >
      {/* Header */}
      <div className="px-5 py-3 border-b border-[var(--border-subtle)]">
        <h3 className="text-sm font-bold text-[var(--text-primary)] mb-0.5">
          {courseTitle}
        </h3>
        <p className="text-[10px] text-[var(--text-muted)]">
          {safeVideos.filter((v) => v.completed).length}/{safeVideos.length} completed
        </p>
      </div>

      {/* Video list */}
      <div className="max-h-[400px] overflow-y-auto">
        {safeVideos.map((video, idx) => {
          const isActive = video.id === activeVideoId
          const isCompleted = video.completed

          return (
            <motion.button
              key={video.id}
              whileHover={{ x: 3 }}
              whileTap={{ scale: 0.99 }}
              onClick={() => onSelect(video)}
              className={`w-full flex items-center gap-3 px-4 py-3 border-b border-[var(--border-subtle)] text-left transition-all duration-200 group
                ${isActive
                  ? "bg-violet-500/8 border-l-2 border-l-violet-500"
                  : "hover:bg-[var(--bg-elevated)] border-l-2 border-l-transparent"
                }
              `}
            >
              {/* Order number / status */}
              <div
                className={`w-7 h-7 rounded-lg flex items-center justify-center shrink-0 text-xs font-bold
                  ${isCompleted
                    ? "bg-emerald-500/15 text-emerald-400"
                    : isActive
                      ? "bg-violet-500/15 text-violet-400"
                      : "bg-[var(--bg-elevated)] text-[var(--text-muted)]"
                  }
                `}
              >
                {isCompleted ? (
                  <CheckCircle2 size={14} />
                ) : isActive ? (
                  <Play size={12} fill="currentColor" />
                ) : (
                  idx + 1
                )}
              </div>

              {/* Title + meta */}
              <div className="flex-1 min-w-0">
                {video.stageLabel && (
                  <span className="inline-block mb-0.5 text-[8px] font-semibold uppercase tracking-wide px-1.5 py-0.5 rounded-full bg-violet-500/15 text-violet-400">
                    {video.stageLabel}
                  </span>
                )}
                <p
                  className={`text-xs font-medium truncate ${
                    isActive
                      ? "text-violet-300"
                      : isCompleted
                        ? "text-[var(--text-secondary)]"
                        : "text-[var(--text-primary)]"
                  }`}
                >
                  {video.title}
                </p>
                <div className="flex items-center gap-2 mt-0.5">
                  <div className="flex items-center gap-1">
                    <Clock size={9} className="text-[var(--text-muted)]" />
                    <span className="text-[9px] text-[var(--text-muted)]">
                      {formatDuration(video.duration)}
                    </span>
                  </div>
                  {video.watchedPercent > 0 && video.watchedPercent < 100 && (
                    <div className="flex items-center gap-1">
                      <div className="w-12 h-0.5 rounded-full bg-[var(--bg-primary)] overflow-hidden">
                        <div
                          className="h-full rounded-full bg-violet-500"
                          style={{ width: `${video.watchedPercent}%` }}
                        />
                      </div>
                      <span className="text-[8px] text-[var(--text-muted)]">
                        {video.watchedPercent}%
                      </span>
                    </div>
                  )}
                </div>
              </div>

              {/* Arrow */}
              <ChevronRight
                size={14}
                className={`shrink-0 transition-colors ${
                  isActive ? "text-violet-400" : "text-[var(--text-muted)] group-hover:text-[var(--text-secondary)]"
                }`}
              />
            </motion.button>
          )
        })}
      </div>
    </motion.div>
  )
}
