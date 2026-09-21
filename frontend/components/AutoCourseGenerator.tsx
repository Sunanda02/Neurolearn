"use client"

import { useState } from "react"
import { motion, AnimatePresence } from "framer-motion"
import {
  Search,
  Loader2,
  BookOpen,
  PlayCircle,
  CheckCircle2,
  AlertCircle,
  Zap,
  Clock,
  ExternalLink,
  Sparkles,
} from "lucide-react"
import {
  discoverCourseContent,
  runFullCoursePipeline,
  saveAutoCourseToDashboard,
  type AutoCourse,
  type DiscoveredVideo,
} from "@/lib/api"

// ── Types ────────────────────────────────────────────────────

type DiscoverResponse = AutoCourse
const SAVED_AUTO_COURSES_KEY = "neurolearn_saved_auto_courses"

// ── Helpers ──────────────────────────────────────────────────

function formatDuration(seconds: number): string {
  if (!seconds) return "Unknown"
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  const s = seconds % 60
  if (h > 0) return `${h}h ${m}m`
  if (m > 0) return `${m}m ${s}s`
  return `${s}s`
}

function toDashboardCourse(course: AutoCourse) {
  const videos = (course.videos || []).map((video, idx) => ({
    id: video.id,
    title: video.title,
    url: video.url,
    duration: video.duration || 0,
    thumbnail: video.thumbnail || "",
    order: idx + 1,
    completed: false,
    watchedPercent: 0,
  }))

  const totalSeconds = videos.reduce((sum, v) => sum + (v.duration || 0), 0)

  return {
    id: course.courseId,
    title: course.courseTitle,
    description: course.description,
    icon: course.icon || "🎓",
    category: course.category || "Auto-Generated",
    difficulty: (course.difficulty || "Intermediate") as "Beginner" | "Intermediate" | "Advanced",
    totalVideos: videos.length,
    completedVideos: 0,
    progress: 0,
    estimatedHours: Math.max(0.1, Number((totalSeconds / 3600).toFixed(1))),
    tags: course.tags || ["auto-generated"],
    videoLinks: videos,
  }
}

function saveAutoCourseLocally(course: AutoCourse) {
  if (typeof window === "undefined") return

  const localCourse = toDashboardCourse(course)
  const raw = window.localStorage.getItem(SAVED_AUTO_COURSES_KEY)
  const existing = raw ? JSON.parse(raw) : []
  const filtered = Array.isArray(existing)
    ? existing.filter((c: { id?: string }) => c?.id !== localCourse.id)
    : []

  window.localStorage.setItem(
    SAVED_AUTO_COURSES_KEY,
    JSON.stringify([localCourse, ...filtered])
  )
}

// ── Sub-components ────────────────────────────────────────────

function VideoCard({ video, index }: { video: DiscoveredVideo; index: number }) {
  return (
    <motion.div
      initial={{ opacity: 0, x: -20 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: index * 0.07, duration: 0.4, ease: [0.4, 0, 0.2, 1] }}
      className="flex gap-4 p-4 rounded-xl bg-[var(--bg-card)] border border-[var(--border-subtle)]
                 hover:border-violet-500/30 transition-all duration-200 group"
    >
      {/* Thumbnail */}
      <div className="flex-shrink-0 w-28 h-[4.2rem] rounded-lg overflow-hidden bg-white/5 relative">
        {video.thumbnail ? (
          <img
            src={video.thumbnail}
            alt={video.title}
            className="w-full h-full object-cover"
            onError={(e) => {
              ;(e.target as HTMLImageElement).style.display = "none"
            }}
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center">
            <PlayCircle className="w-8 h-8 text-violet-400/40" />
          </div>
        )}
        <div className="absolute inset-0 bg-black/0 group-hover:bg-black/20 transition-all duration-200
                        flex items-center justify-center">
          <PlayCircle className="w-7 h-7 text-white opacity-0 group-hover:opacity-100 transition-opacity duration-200" />
        </div>
      </div>

      {/* Info */}
      <div className="flex-1 min-w-0">
        {/* FIX (course generator request): surfaces which curriculum
            stage this video was chosen for, so it's visible in the UI
            that a course spans levels instead of repeating one. */}
        {video.stageLabel && (
          <span className="inline-block mb-1 text-[10px] font-semibold uppercase tracking-wide px-2 py-0.5 rounded-full bg-violet-500/15 text-violet-400">
            {video.stageLabel}
          </span>
        )}
        <p className="text-sm font-medium text-[var(--text-primary)] line-clamp-2 leading-snug">
          {video.title}
        </p>
        {video.channel && (
          <p className="text-xs text-[var(--text-muted)] mt-1">{video.channel}</p>
        )}
        <div className="flex items-center gap-3 mt-2 flex-wrap">
          <span className="flex items-center gap-1 text-xs text-[var(--text-muted)]">
            <Clock className="w-3 h-3" />
            {formatDuration(video.duration)}
          </span>
          {video.assessmentAvailable && (
            <span className="flex items-center gap-1 text-xs text-emerald-400 bg-emerald-500/10
                             px-2 py-0.5 rounded-full">
              <CheckCircle2 className="w-3 h-3" />
              Assessment ready
            </span>
          )}
        </div>
      </div>

      {/* Actions */}
      <div className="flex-shrink-0 flex flex-col gap-2 justify-center">
        <a
          href={video.url}
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center gap-1 text-xs text-violet-400 hover:text-violet-300
                     bg-violet-500/10 hover:bg-violet-500/20 px-3 py-1.5 rounded-lg
                     transition-all duration-150"
        >
          Watch <ExternalLink className="w-3 h-3" />
        </a>
      </div>
    </motion.div>
  )
}

// ── Main Component ────────────────────────────────────────────

export default function AutoCourseGenerator() {
  const [topic, setTopic] = useState("")
  const [maxVideos, setMaxVideos] = useState(5)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<DiscoverResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const [saveLoading, setSaveLoading] = useState(false)
  const [savedCourseId, setSavedCourseId] = useState<string | null>(null)
  const [runFull, setRunFull] = useState(false)

  const EXAMPLE_TOPICS = [
    "Operating Systems",
    "Machine Learning",
    "React Hooks",
    "Networking Basics",
    "Data Structures",
  ]

  async function handleDiscover() {
    if (!topic.trim()) return
    setLoading(true)
    setError(null)
    setNotice(null)
    setResult(null)
    setSavedCourseId(null)

    try {
      if (runFull) {
        const queued = await runFullCoursePipeline({
          topic: topic.trim(),
          maxVideos,
          studentId: "student_001",
          attentionScore: 75,
        })

        setNotice(queued.message || "Pipeline queued successfully.")
      } else {
        const discovered = await discoverCourseContent({
          topic: topic.trim(),
          maxVideos,
          autoTranscribe: false,
        })
        setResult(discovered)
      }
    } catch (ex: unknown) {
      setError(ex instanceof Error ? ex.message : "Unknown error occurred")
    } finally {
      setLoading(false)
    }
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Enter") handleDiscover()
  }

  async function handleSaveCourse() {
    if (!result?.courseId) return
    setSaveLoading(true)
    setError(null)

    try {
      // Always persist locally so dashboard can show it instantly.
      saveAutoCourseLocally(result)

      const res = await saveAutoCourseToDashboard(result.courseId)
      setSavedCourseId(result.courseId)
      setNotice(res.message || "Course saved to dashboard")
    } catch (ex: unknown) {
      const msg = ex instanceof Error ? ex.message : "Could not save course"
      if (/404/.test(msg)) {
        setSavedCourseId(result.courseId)
        setNotice("Saved locally. Restart/redeploy backend to enable server-side save endpoint.")
      } else {
        setError(msg)
      }
    } finally {
      setSaveLoading(false)
    }
  }

  return (
    <div className="w-full max-w-2xl mx-auto space-y-6">
      {/* Header */}
      <div className="text-center space-y-1">
        <div className="flex items-center justify-center gap-2 mb-2">
          <Sparkles className="w-5 h-5 text-violet-400" />
          <h2 className="text-lg font-semibold text-[var(--text-primary)]">
            Auto Course Generator
          </h2>
        </div>
        <p className="text-sm text-[var(--text-muted)]">
          Enter any topic — NeuroLearn finds educational videos and creates
          adaptive assessments automatically.
        </p>
      </div>

      {/* Input */}
      <div className="space-y-3">
        <div className="flex gap-2">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--text-muted)]" />
            <input
              type="text"
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="e.g. Operating Systems, React Hooks, Machine Learning…"
              className="w-full pl-10 pr-4 py-3 rounded-xl text-sm
                         bg-[var(--bg-card)] border border-[var(--border-subtle)]
                         text-[var(--text-primary)] placeholder:text-[var(--text-muted)]
                         focus:outline-none focus:border-violet-500/50 focus:ring-1 focus:ring-violet-500/20
                         transition-all duration-150"
            />
          </div>

          {/* Max videos selector */}
          <select
            value={maxVideos}
            onChange={(e) => setMaxVideos(Number(e.target.value))}
            className="px-3 py-3 rounded-xl text-sm bg-[var(--bg-card)] border border-[var(--border-subtle)]
                       text-[var(--text-primary)] focus:outline-none focus:border-violet-500/50
                       cursor-pointer"
          >
            {[3, 4, 5].map((n) => (
              <option key={n} value={n}>
                {n} videos
              </option>
            ))}
          </select>
        </div>

        {/* Full pipeline toggle */}
        <label className="flex items-center gap-2 cursor-pointer w-fit">
          <div
            onClick={() => setRunFull((v) => !v)}
            className={`w-9 h-5 rounded-full transition-colors duration-200 relative
                        ${runFull ? "bg-violet-500" : "bg-white/10"}`}
          >
            <div
              className={`absolute top-0.5 w-4 h-4 rounded-full bg-white shadow transition-transform duration-200
                          ${runFull ? "translate-x-4" : "translate-x-0.5"}`}
            />
          </div>
          <span className="text-xs text-[var(--text-muted)]">
            Full pipeline (transcribe + generate assessments in background)
          </span>
        </label>

        {/* Discover button */}
        <button
          onClick={handleDiscover}
          disabled={loading || !topic.trim()}
          className="w-full flex items-center justify-center gap-2 py-3 px-4
                     rounded-xl font-medium text-sm transition-all duration-200
                     bg-violet-600 hover:bg-violet-500 disabled:opacity-50
                     disabled:cursor-not-allowed text-white shadow-lg shadow-violet-500/20"
        >
          {loading ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin" />
              Discovering content…
            </>
          ) : (
            <>
              <Zap className="w-4 h-4" />
              Generate Course
            </>
          )}
        </button>
      </div>

      {/* Example topics */}
      {!result && !loading && (
        <div className="flex flex-wrap gap-2 justify-center">
          {EXAMPLE_TOPICS.map((t) => (
            <button
              key={t}
              onClick={() => setTopic(t)}
              className="text-xs px-3 py-1.5 rounded-full bg-white/5 hover:bg-violet-500/15
                         border border-[var(--border-subtle)] hover:border-violet-500/30
                         text-[var(--text-muted)] hover:text-violet-300 transition-all duration-150"
            >
              {t}
            </button>
          ))}
        </div>
      )}

      {/* Error */}
      <AnimatePresence>
        {error && (
          <motion.div
            initial={{ opacity: 0, y: -8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            className="flex items-start gap-3 p-4 rounded-xl bg-red-500/10 border border-red-500/20"
          >
            <AlertCircle className="w-4 h-4 text-red-400 flex-shrink-0 mt-0.5" />
            <div>
              <p className="text-sm font-medium text-red-400">Discovery failed</p>
              <p className="text-xs text-red-300/70 mt-0.5">{error}</p>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Success notice */}
      <AnimatePresence>
        {notice && (
          <motion.div
            initial={{ opacity: 0, y: -8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            className="flex items-start gap-3 p-4 rounded-xl bg-emerald-500/10 border border-emerald-500/20"
          >
            <CheckCircle2 className="w-4 h-4 text-emerald-400 flex-shrink-0 mt-0.5" />
            <div>
              <p className="text-sm font-medium text-emerald-400">Pipeline queued</p>
              <p className="text-xs text-emerald-300/80 mt-0.5">{notice}</p>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Results */}
      <AnimatePresence>
        {result && (
          <motion.div
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            className="space-y-4"
          >
            {/* Course header */}
            <div className="flex items-center justify-between p-4 rounded-xl
                            bg-violet-500/10 border border-violet-500/20">
              <div className="flex items-center gap-3">
                <div className="w-9 h-9 rounded-lg bg-violet-500/20 flex items-center justify-center">
                  <BookOpen className="w-5 h-5 text-violet-400" />
                </div>
                <div>
                  <p className="text-sm font-semibold text-[var(--text-primary)]">
                    {result.courseTitle}
                  </p>
                  <p className="text-xs text-[var(--text-muted)]">
                    {result.totalFound} videos found · {result.elapsedSeconds.toFixed(1)}s
                  </p>
                </div>
              </div>
              <span
                className={`text-xs px-2.5 py-1 rounded-full font-medium ${
                  result.status === "success"
                    ? "bg-emerald-500/15 text-emerald-400"
                    : "bg-amber-500/15 text-amber-400"
                }`}
              >
                {result.status}
              </span>
            </div>

            {/* Video list */}
            <div className="space-y-2">
              {result.videos.map((video, i) => (
                <VideoCard key={video.id} video={video} index={i} />
              ))}
            </div>

            {/* CTA */}
            <div className="pt-1 space-y-3">
              <p className="text-center text-xs text-[var(--text-muted)]">
                Course ID: <code className="text-violet-400">{result.courseId}</code>
                {" · "}Use this to track progress in NeuroLearn.
              </p>

              <div className="flex justify-center">
                <button
                  onClick={handleSaveCourse}
                  disabled={saveLoading || savedCourseId === result.courseId}
                  className="flex items-center justify-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold
                             bg-emerald-600 hover:bg-emerald-500 disabled:opacity-60 disabled:cursor-not-allowed
                             text-white transition-all duration-200"
                >
                  {saveLoading
                    ? "Saving..."
                    : savedCourseId === result.courseId
                      ? "Saved to Dashboard"
                      : "Save to Dashboard"}
                </button>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
