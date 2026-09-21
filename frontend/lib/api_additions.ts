// ============================================================
// API ADDITIONS — Content Discovery (Auto Course Generator)
// File: lib/api_additions.ts
//
// Paste these types and functions into lib/api.ts
// They follow the existing apiFetch / normalizeKeys patterns.
// ============================================================

// ── Types (add to lib/api.ts) ────────────────────────────────

export interface DiscoveredVideo {
  id: string
  title: string
  url: string
  duration: number
  thumbnail: string
  channel: string
  assessmentAvailable: boolean
  transcriptionAvailable: boolean
}

export interface AutoCourse {
  courseId: string
  courseTitle: string
  topic: string
  description: string
  icon: string
  category: string
  difficulty: string
  tags: string[]
  videos: DiscoveredVideo[]
  totalFound: number
  generatedAt: number
  elapsedSeconds: number
  status: "success" | "partial" | "failed"
}

export interface DiscoverRequest {
  topic: string
  maxVideos?: number          // 1–10, default 5
  autoTranscribe?: boolean    // default false
}

export interface FullPipelineRequest {
  topic: string
  maxVideos?: number          // 1–5, default 3
  studentId?: string
  attentionScore?: number
}

export interface FullPipelineResponse {
  courseId: string
  courseTitle: string
  status: string
  message: string
  videosQueued: number
  assessmentSessions: object[]
}

// ── API Functions (add to lib/api.ts) ────────────────────────

/**
 * Discover educational videos for a topic via web scraping.
 * POST /api/content/discover
 */
export async function discoverCourseContent(
  request: DiscoverRequest
): Promise<AutoCourse> {
  return apiFetch<AutoCourse>("/content/discover", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      topic: request.topic,
      max_videos: request.maxVideos ?? 5,
      auto_transcribe: request.autoTranscribe ?? false,
    }),
  })
}

/**
 * Run full pipeline: discover + transcribe + generate assessments (background).
 * POST /api/content/pipeline/full
 */
export async function runFullCoursePipeline(
  request: FullPipelineRequest
): Promise<FullPipelineResponse> {
  return apiFetch<FullPipelineResponse>("/content/pipeline/full", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      topic: request.topic,
      max_videos: request.maxVideos ?? 3,
      student_id: request.studentId ?? "student_001",
      attention_score: request.attentionScore ?? 75,
    }),
  })
}

/**
 * List all auto-generated courses in the database.
 * GET /api/content/courses/auto
 */
export async function getAutoCourses(): Promise<{
  total: number
  courses: AutoCourse[]
}> {
  return apiFetch<{ total: number; courses: AutoCourse[] }>(
    "/content/courses/auto"
  )
}

/**
 * Get a specific auto-generated course by ID.
 * GET /api/content/courses/auto/{courseId}
 */
export async function getAutoCourse(courseId: string): Promise<AutoCourse> {
  return apiFetch<AutoCourse>(`/content/courses/auto/${courseId}`)
}
