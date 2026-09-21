"use client"

import Link from "next/link"
import { motion } from "framer-motion"
import { Clock, BookOpen, ArrowRight, CheckCircle2 } from "lucide-react"
import type { Course } from "@/lib/api"

interface TopicCardProps {
  course: Course
  index: number
}

const difficultyConfig = {
  Beginner: { color: "text-emerald-400", bg: "bg-emerald-500/10", border: "border-emerald-500/20", glow: "shadow-emerald-500/10" },
  Intermediate: { color: "text-amber-400", bg: "bg-amber-500/10", border: "border-amber-500/20", glow: "shadow-amber-500/10" },
  Advanced: { color: "text-red-400", bg: "bg-red-500/10", border: "border-red-500/20", glow: "shadow-red-500/10" },
}

export default function TopicCard({ course, index }: TopicCardProps) {
  const diff = difficultyConfig[course.difficulty]
  const isComplete = course.progress === 100

  return (
    <motion.div
      initial={{ opacity: 0, y: 30 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.08, duration: 0.5, ease: [0.4, 0, 0.2, 1] }}
    >
      <Link href={`/video?course=${course.id}`}>
        <motion.div
          whileHover={{ y: -6, scale: 1.01 }}
          whileTap={{ scale: 0.99 }}
          className={`
            relative h-full rounded-2xl p-5 cursor-pointer transition-all duration-300
            bg-[var(--bg-card)] border border-[var(--border-subtle)]
            hover:border-violet-500/30 hover:shadow-xl hover:shadow-violet-500/5
            group overflow-hidden
          `}
        >
          {/* Gradient overlay on hover */}
          <div className="absolute inset-0 rounded-2xl bg-gradient-to-br from-violet-500/0 to-purple-500/0 group-hover:from-violet-500/5 group-hover:to-purple-500/5 transition-all duration-500" />

          {/* Completion check */}
          {isComplete && (
            <motion.div
              initial={{ scale: 0 }}
              animate={{ scale: 1 }}
              className="absolute top-3 right-3 w-8 h-8 rounded-full bg-emerald-500/20 border border-emerald-500/40 flex items-center justify-center"
            >
              <CheckCircle2 size={16} className="text-emerald-400" />
            </motion.div>
          )}

          {/* Content */}
          <div className="relative z-10">
            {/* Icon + Difficulty */}
            <div className="flex items-start justify-between mb-4">
              <motion.div
                whileHover={{ rotate: 10, scale: 1.1 }}
                className="text-4xl"
              >
                {course.icon}
              </motion.div>
              <span className={`text-[10px] font-bold px-2.5 py-1 rounded-full ${diff.color} ${diff.bg} border ${diff.border}`}>
                {course.difficulty}
              </span>
            </div>

            {/* Title */}
            <h3 className="text-base font-bold text-[var(--text-primary)] mb-1.5 group-hover:text-transparent group-hover:bg-gradient-to-r group-hover:from-blue-400 group-hover:to-violet-400 group-hover:bg-clip-text transition-all duration-300 line-clamp-2">
              {course.title}
            </h3>

            {/* Description */}
            <p className="text-xs text-[var(--text-muted)] mb-4 line-clamp-2">{course.description}</p>

            {/* Meta */}
            <div className="flex items-center gap-3 mb-4 text-[var(--text-muted)]">
              <div className="flex items-center gap-1">
                <BookOpen size={12} />
                <span className="text-[11px]">{course.completedVideos}/{course.totalVideos} videos</span>
              </div>
              <div className="flex items-center gap-1">
                <Clock size={12} />
                <span className="text-[11px]">{course.estimatedHours}h</span>
              </div>
            </div>

            {/* Progress bar */}
            <div className="mb-3">
              <div className="flex justify-between items-center mb-1.5">
                <span className="text-[10px] font-medium text-[var(--text-muted)]">Progress</span>
                <span className="text-[10px] font-bold text-violet-400">{course.progress}%</span>
              </div>
              <div className="w-full h-1.5 rounded-full bg-[var(--bg-primary)] overflow-hidden">
                <motion.div
                  initial={{ width: 0 }}
                  animate={{ width: `${course.progress}%` }}
                  transition={{ delay: index * 0.08 + 0.3, duration: 0.8, ease: "easeOut" }}
                  className="h-full rounded-full progress-animated"
                />
              </div>
            </div>

            {/* Tags */}
            <div className="flex flex-wrap gap-1.5 mb-4">
              {course.tags.slice(0, 3).map((tag) => (
                <span key={tag} className="text-[10px] px-2 py-0.5 rounded-full bg-[var(--bg-elevated)] text-[var(--text-muted)] border border-[var(--border-subtle)]">
                  {tag}
                </span>
              ))}
            </div>

            {/* CTA */}
            <div className="flex items-center justify-between pt-3 border-t border-[var(--border-subtle)]">
              <span className="text-xs font-medium text-[var(--text-muted)]">
                {course.progress === 0 ? "Start Learning" : course.progress === 100 ? "Review" : "Continue"}
              </span>
              <motion.div
                initial={{ x: 0 }}
                whileHover={{ x: 4 }}
                className="w-7 h-7 rounded-lg bg-violet-500/10 flex items-center justify-center group-hover:bg-violet-500/20 transition-colors"
              >
                <ArrowRight size={14} className="text-violet-400" />
              </motion.div>
            </div>
          </div>
        </motion.div>
      </Link>
    </motion.div>
  )
}
