"use client"

import { useEffect, useState } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { Clock, ChevronRight, CheckCircle } from "lucide-react"
import type { AssessmentQuestion } from "@/lib/api"

interface AssessmentCardProps {
  question: AssessmentQuestion
  questionNumber: number
  totalQuestions: number
  timeRemaining?: number
  initialAnswer?: string | number | null
  isFinalQuestion?: boolean
  isBusy?: boolean
  canGoPrevious?: boolean
  canGoNext?: boolean
  onSubmit: (questionId: string, answer: string | number) => void
  onPrevious?: () => void
  onNext?: () => void
}

export default function AssessmentCard({
  question,
  questionNumber,
  totalQuestions,
  timeRemaining,
  initialAnswer = null,
  isFinalQuestion = false,
  isBusy = false,
  canGoPrevious = false,
  canGoNext = false,
  onSubmit,
  onPrevious,
  onNext,
}: AssessmentCardProps) {
  const [selected, setSelected] = useState<number | null>(
    typeof initialAnswer === "number" ? initialAnswer : null
  )
  const progressPct = (questionNumber / totalQuestions) * 100
  const hasSavedAnswer = initialAnswer !== null && initialAnswer !== undefined

  useEffect(() => {
    setSelected(typeof initialAnswer === "number" ? initialAnswer : null)
  }, [initialAnswer, question.id])

  const handleSubmit = () => {
    if (hasSavedAnswer && canGoNext) {
      onNext?.()
      return
    }
    if (selected !== null) {
      onSubmit(question.id, selected)
    }
  }

  const formatTime = (s: number) => {
    const m = Math.floor(s / 60)
    const sec = s % 60
    return `${m}:${sec.toString().padStart(2, "0")}`
  }

  const diffColors = {
    easy: { text: "text-emerald-400", bg: "bg-emerald-500/10", border: "border-emerald-500/20" },
    medium: { text: "text-amber-400", bg: "bg-amber-500/10", border: "border-amber-500/20" },
    hard: { text: "text-red-400", bg: "bg-red-500/10", border: "border-red-500/20" },
  }
  const dc = diffColors[question.difficulty] || diffColors.medium

  return (
    <motion.div
      key={question.id}
      initial={{ opacity: 0, x: 40 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, x: -40 }}
      transition={{ duration: 0.4, ease: [0.4, 0, 0.2, 1] }}
      className="rounded-2xl bg-[var(--bg-card)] border border-[var(--border-subtle)] p-6 md:p-8 max-w-2xl mx-auto"
    >
      {/* Top bar: progress + timer + difficulty */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <span className="text-xs font-medium text-[var(--text-muted)]">
            Q{questionNumber}/{totalQuestions}
          </span>
          <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${dc.text} ${dc.bg} border ${dc.border} uppercase`}>
            {question.difficulty}
          </span>
          <span className="text-[10px] font-mono text-violet-400 bg-violet-500/10 px-2 py-0.5 rounded-full">
            +{question.points} pts
          </span>
        </div>
        {timeRemaining !== undefined && (
          <div className={`flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-mono ${timeRemaining < 60 ? "bg-red-500/10 text-red-400 border border-red-500/20" : "bg-[var(--bg-elevated)] text-[var(--text-muted)]"}`}>
            <Clock size={12} />
            {formatTime(timeRemaining)}
          </div>
        )}
      </div>

      {/* Progress bar */}
      <div className="w-full h-1 rounded-full bg-[var(--bg-primary)] mb-8 overflow-hidden">
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${progressPct}%` }}
          transition={{ duration: 0.6, ease: "easeOut" }}
          className="h-full rounded-full"
          style={{ background: "linear-gradient(90deg, #8b5cf6, #a855f7, #ec4899)" }}
        />
      </div>

      {/* Question text */}
      <motion.h2
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.1 }}
        className="text-xl md:text-2xl font-bold text-[var(--text-primary)] mb-8 leading-snug"
      >
        {question.question}
      </motion.h2>

      {/* Options */}
      <div className="space-y-3 mb-8">
        {question.options?.map((option, idx) => (
          <motion.button
            key={idx}
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.15 + idx * 0.07 }}
            onClick={() => setSelected(idx)}
            className={`w-full p-4 text-left rounded-xl border-2 transition-all duration-200 group flex items-center gap-3
              ${selected === idx
                ? "border-violet-500 bg-violet-500/8 shadow-lg shadow-violet-500/10"
                : "border-[var(--border-subtle)] bg-[var(--bg-elevated)]/50 hover:border-[var(--border-default)] hover:bg-[var(--bg-elevated)]"
              }
            `}
          >
            {/* Radio circle */}
            <div className={`w-5 h-5 rounded-full border-2 flex items-center justify-center shrink-0 transition-all
              ${selected === idx ? "border-violet-500 bg-violet-500" : "border-[var(--border-strong)] group-hover:border-[var(--text-muted)]"}
            `}>
              {selected === idx && (
                <motion.div
                  initial={{ scale: 0 }}
                  animate={{ scale: 1 }}
                  className="w-2 h-2 bg-white rounded-full"
                />
              )}
            </div>

            {/* Option letter + text */}
            <div className="flex items-center gap-3 flex-1 min-w-0">
              <span className={`text-xs font-bold w-6 h-6 rounded-md flex items-center justify-center shrink-0
                ${selected === idx ? "bg-violet-500/20 text-violet-300" : "bg-[var(--bg-primary)] text-[var(--text-muted)]"}
              `}>
                {String.fromCharCode(65 + idx)}
              </span>
              <span className={`text-sm transition-colors
                ${selected === idx ? "text-violet-200 font-medium" : "text-[var(--text-secondary)]"}
              `}>
                {option}
              </span>
            </div>
          </motion.button>
        ))}
      </div>

      {/* Submit button */}
      <div className="flex items-center gap-3">
        <motion.button
          whileHover={canGoPrevious ? { scale: 1.01 } : {}}
          whileTap={canGoPrevious ? { scale: 0.99 } : {}}
          onClick={onPrevious}
          disabled={!canGoPrevious || isBusy}
          className="px-4 py-3.5 rounded-xl font-bold text-sm bg-[var(--bg-elevated)] text-[var(--text-secondary)] border border-[var(--border-subtle)] disabled:opacity-40 disabled:cursor-not-allowed"
        >
          Previous
        </motion.button>
      <motion.button
          whileHover={(selected !== null || canGoNext) && !isBusy ? { scale: 1.01 } : {}}
          whileTap={(selected !== null || canGoNext) && !isBusy ? { scale: 0.99 } : {}}
        onClick={handleSubmit}
          disabled={(selected === null && !canGoNext) || isBusy}
          className={`flex-1 py-3.5 rounded-xl font-bold text-sm transition-all duration-300 flex items-center justify-center gap-2
          ${(selected !== null || canGoNext) && !isBusy
            ? "bg-gradient-to-r from-violet-500 to-purple-600 text-white hover:shadow-xl hover:shadow-violet-500/20 cursor-pointer"
            : "bg-[var(--bg-elevated)] text-[var(--text-muted)] cursor-not-allowed border border-[var(--border-subtle)]"
          }
        `}
      >
          {isBusy ? (
            "Loading..."
          ) : isFinalQuestion ? (
          <>
            <CheckCircle size={16} />
            Submit Assessment
          </>
        ) : (
          <>
            Next Question
            <ChevronRight size={16} />
          </>
        )}
      </motion.button>
      </div>
    </motion.div>
  )
}
