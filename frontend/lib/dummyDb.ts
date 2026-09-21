// ============================================================
// DUMMY DATABASE — All data in JSON format for FastAPI integration
// Replace each section with actual API calls to your FastAPI backend
// Each function simulates: GET /api/<endpoint> → JSON response
// ============================================================

// ---- TYPES (matching FastAPI Pydantic models) ----

export interface StudentProfile {
  id: string
  name: string
  email: string
  avatar: string
  level: number
  xp: number
  xpToNextLevel: number
  streak: number
  bestStreak: number
  totalCoursesCompleted: number
  totalWatchTime: number // minutes
  joinedDate: string
  rank: number
  badges: Badge[]
}

export interface Badge {
  id: string
  name: string
  description: string
  icon: string
  earned: boolean
  earnedDate?: string
  rarity: "common" | "rare" | "epic" | "legendary"
}

export interface Course {
  id: string
  title: string
  description: string
  icon: string
  category: string
  difficulty: "Beginner" | "Intermediate" | "Advanced"
  totalVideos: number
  completedVideos: number
  progress: number
  estimatedHours: number
  tags: string[]
  videoLinks: VideoLink[]
}

export interface VideoLink {
  id: string
  title: string
  url: string
  duration: number // seconds
  thumbnail: string
  order: number
  completed: boolean
  watchedPercent: number
  // FIX (course generator request): preserved from the auto-generator's
  // curriculum-stage assignment when a course is saved to the dashboard.
  stageLabel?: string
}

export interface AttentionSnapshot {
  timestamp: string
  score: number
  state: "attentive" | "inattentive" | "unfocused"
  confidence: number
  message: string
  // JSON payload from your OCR/ML model
  modelResponse: {
    eye_contact: number
    head_pose: string
    face_detected: boolean
    blink_rate: number
  }
}

export interface TranscriptSegment {
  id: string
  text: string
  timestamp: string
  startTime: number
  endTime: number
  confidence: number
  // JSON from your transcription model
  modelResponse: {
    language: string
    words: { word: string; start: number; end: number; confidence: number }[]
  }
}

export interface AssessmentQuestion {
  id: string
  type: "mcq" | "true-false" | "short-answer"
  question: string
  options?: string[]
  correctAnswer: string | number
  difficulty: "easy" | "medium" | "hard"
  points: number
  explanation: string
  topicId: string
  // JSON from LLM question generation
  llmMetadata: {
    model: string
    generatedFrom: string
    difficultyScore: number
    bloomsLevel: string
  }
}

export interface AssessmentSession {
  id: string
  courseId: string
  videoId: string
  questions: AssessmentQuestion[]
  difficulty: "easy" | "medium" | "hard"
  timeLimit: number // seconds
  attentionScoreDuringVideo: number
  // JSON from adaptive engine
  adaptiveMetadata: {
    previousScore: number | null
    adjustedDifficulty: string
    reason: string
  }
}

export interface AssessmentResult {
  sessionId: string
  score: number
  totalPoints: number
  earnedPoints: number
  percentage: number
  xpEarned: number
  timeSpent: number
  correctAnswers: number
  totalQuestions: number
  difficulty: string
  message: string
  nextDifficulty: "easy" | "medium" | "hard"
  suggestedTopics: string[]
  // JSON from adaptive engine
  adaptiveResponse: {
    performanceTrend: "improving" | "stable" | "declining"
    recommendedAction: string
    nextAssessmentDifficulty: string
    strengthAreas: string[]
    weakAreas: string[]
  }
}

export interface LeaderboardEntry {
  rank: number
  studentId: string
  name: string
  avatar: string
  xp: number
  level: number
  streak: number
  coursesCompleted: number
}

export interface DailyChallenge {
  id: string
  title: string
  description: string
  xpReward: number
  type: "watch" | "quiz" | "streak" | "review"
  completed: boolean
  progress: number
  target: number
}

export interface Notification {
  id: string
  type: "achievement" | "reminder" | "milestone" | "challenge"
  title: string
  message: string
  timestamp: string
  read: boolean
  icon: string
}

// ============================================================
// DUMMY DATA — Replace with FastAPI endpoints
// ============================================================

export const DUMMY_STUDENT: StudentProfile = {
  id: "student_001",
  name: "Alex Johnson",
  email: "alex@neurolearn.io",
  avatar: "/placeholder-user.jpg",
  level: 12,
  xp: 4250,
  xpToNextLevel: 5000,
  streak: 7,
  bestStreak: 14,
  totalCoursesCompleted: 4,
  totalWatchTime: 1260,
  joinedDate: "2024-09-15",
  rank: 23,
  badges: [
    { id: "b1", name: "First Steps", description: "Complete your first lesson", icon: "👣", earned: true, earnedDate: "2024-09-16", rarity: "common" },
    { id: "b2", name: "Week Warrior", description: "Maintain a 7-day streak", icon: "⚔️", earned: true, earnedDate: "2024-09-23", rarity: "rare" },
    { id: "b3", name: "Perfect Score", description: "Score 100% on an assessment", icon: "💯", earned: false, rarity: "epic" },
    { id: "b4", name: "Speed Learner", description: "Complete 5 lessons in one day", icon: "🚀", earned: false, rarity: "epic" },
    { id: "b5", name: "Century Club", description: "Earn 1000 XP", icon: "💎", earned: true, earnedDate: "2024-10-01", rarity: "legendary" },
    { id: "b6", name: "Night Owl", description: "Study past midnight", icon: "🦉", earned: true, earnedDate: "2024-10-05", rarity: "common" },
    { id: "b7", name: "Quiz Master", description: "Complete 50 quizzes", icon: "🧠", earned: false, rarity: "legendary" },
    { id: "b8", name: "Social Butterfly", description: "Join a study group", icon: "🦋", earned: false, rarity: "rare" },
  ],
}

export const DUMMY_COURSES: Course[] = [
  {
    id: "course_001",
    title: "Introduction to React",
    description: "Master the fundamentals of React including components, props, state, and hooks",
    icon: "⚛️",
    category: "Frontend",
    difficulty: "Beginner",
    totalVideos: 8,
    completedVideos: 5,
    progress: 65,
    estimatedHours: 6,
    tags: ["React", "JavaScript", "Frontend"],
    videoLinks: [
      { id: "v1", title: "What is React? — Introduction & Setup", url: "https://www.youtube.com/watch?v=SqcY0GlETPk", duration: 720, thumbnail: "", order: 1, completed: true, watchedPercent: 100 },
      { id: "v2", title: "JSX & Components Deep Dive", url: "https://www.youtube.com/watch?v=9YkUCRr3bVc", duration: 890, thumbnail: "", order: 2, completed: true, watchedPercent: 100 },
      { id: "v3", title: "Props & Data Flow", url: "https://www.youtube.com/watch?v=PHaECbrKgs0", duration: 650, thumbnail: "", order: 3, completed: true, watchedPercent: 100 },
      { id: "v4", title: "State & useState Hook", url: "https://www.youtube.com/watch?v=O6P86uwfdR0", duration: 780, thumbnail: "", order: 4, completed: true, watchedPercent: 100 },
      { id: "v5", title: "useEffect & Side Effects", url: "https://www.youtube.com/watch?v=0ZJgIjIuY7U", duration: 920, thumbnail: "", order: 5, completed: true, watchedPercent: 100 },
      { id: "v6", title: "Event Handling & Forms", url: "https://www.youtube.com/watch?v=dH6i3GurZW8", duration: 640, thumbnail: "", order: 6, completed: false, watchedPercent: 35 },
      { id: "v7", title: "Conditional Rendering", url: "https://www.youtube.com/watch?v=4oCVDkb_peY", duration: 540, thumbnail: "", order: 7, completed: false, watchedPercent: 0 },
      { id: "v8", title: "Lists & Keys", url: "https://www.youtube.com/watch?v=0sasRxl35_8", duration: 480, thumbnail: "", order: 8, completed: false, watchedPercent: 0 },
    ],
  },
  {
    id: "course_002",
    title: "Advanced State Management",
    description: "Redux, Context API, Zustand and modern state patterns for scalable apps",
    icon: "🔄",
    category: "Frontend",
    difficulty: "Intermediate",
    totalVideos: 6,
    completedVideos: 2,
    progress: 42,
    estimatedHours: 8,
    tags: ["Redux", "Context API", "Zustand"],
    videoLinks: [
      { id: "v9", title: "Why State Management Matters", url: "https://www.youtube.com/watch?v=CVpUuw9XSjY", duration: 600, thumbnail: "", order: 1, completed: true, watchedPercent: 100 },
      { id: "v10", title: "Context API Fundamentals", url: "https://www.youtube.com/watch?v=5LrDIWkK_Bc", duration: 750, thumbnail: "", order: 2, completed: true, watchedPercent: 100 },
      { id: "v11", title: "Redux Toolkit Setup", url: "https://www.youtube.com/watch?v=9zySeP5vH9c", duration: 880, thumbnail: "", order: 3, completed: false, watchedPercent: 20 },
      { id: "v12", title: "Redux Thunk & Async", url: "https://www.youtube.com/watch?v=93p3LxR9xfM", duration: 920, thumbnail: "", order: 4, completed: false, watchedPercent: 0 },
      { id: "v13", title: "Zustand — Lightweight Alternative", url: "https://www.youtube.com/watch?v=_ngCLZ5Iz-0", duration: 680, thumbnail: "", order: 5, completed: false, watchedPercent: 0 },
      { id: "v14", title: "State Architecture Patterns", url: "https://www.youtube.com/watch?v=HKU24nY8Hsc", duration: 700, thumbnail: "", order: 6, completed: false, watchedPercent: 0 },
    ],
  },
  {
    id: "course_003",
    title: "Performance Optimization",
    description: "React.memo, useMemo, code splitting, lazy loading, and profiling techniques",
    icon: "⚡",
    category: "Frontend",
    difficulty: "Advanced",
    totalVideos: 5,
    completedVideos: 1,
    progress: 28,
    estimatedHours: 5,
    tags: ["Performance", "Optimization", "React"],
    videoLinks: [
      { id: "v15", title: "React Performance Basics", url: "https://www.youtube.com/watch?v=b1IQI4aJHLM", duration: 800, thumbnail: "", order: 1, completed: true, watchedPercent: 100 },
      { id: "v16", title: "React.memo & useMemo", url: "https://www.youtube.com/watch?v=THL1OPn72vo", duration: 700, thumbnail: "", order: 2, completed: false, watchedPercent: 40 },
      { id: "v17", title: "Code Splitting & Lazy Loading", url: "https://www.youtube.com/watch?v=JU6sl_yyZqs", duration: 650, thumbnail: "", order: 3, completed: false, watchedPercent: 0 },
      { id: "v18", title: "Profiler & DevTools", url: "https://www.youtube.com/watch?v=LfEkP0bpFLc", duration: 600, thumbnail: "", order: 4, completed: false, watchedPercent: 0 },
      { id: "v19", title: "Real-world Optimization Case Study", url: "https://www.youtube.com/watch?v=i8xbddI2Mg8", duration: 900, thumbnail: "", order: 5, completed: false, watchedPercent: 0 },
    ],
  },
  {
    id: "course_004",
    title: "TypeScript Fundamentals",
    description: "Strong typing, interfaces, generics, and TypeScript best practices",
    icon: "📘",
    category: "Languages",
    difficulty: "Beginner",
    totalVideos: 7,
    completedVideos: 6,
    progress: 85,
    estimatedHours: 5,
    tags: ["TypeScript", "JavaScript", "Types"],
    videoLinks: [
      { id: "v20", title: "Why TypeScript?", url: "https://www.youtube.com/watch?v=zQnBQ4tB3ZA", duration: 500, thumbnail: "", order: 1, completed: true, watchedPercent: 100 },
      { id: "v21", title: "Basic Types & Inference", url: "https://www.youtube.com/watch?v=d56mG7DezGs", duration: 620, thumbnail: "", order: 2, completed: true, watchedPercent: 100 },
      { id: "v22", title: "Interfaces & Type Aliases", url: "https://www.youtube.com/watch?v=crjIq7LEAYw", duration: 580, thumbnail: "", order: 3, completed: true, watchedPercent: 100 },
      { id: "v23", title: "Functions & Generics", url: "https://www.youtube.com/watch?v=nViEqpgwxHE", duration: 700, thumbnail: "", order: 4, completed: true, watchedPercent: 100 },
      { id: "v24", title: "Enums, Tuples & Utility Types", url: "https://www.youtube.com/watch?v=BwuLxPH8IDs", duration: 650, thumbnail: "", order: 5, completed: true, watchedPercent: 100 },
      { id: "v25", title: "TypeScript with React", url: "https://www.youtube.com/watch?v=TPACABQTHvM", duration: 780, thumbnail: "", order: 6, completed: true, watchedPercent: 100 },
      { id: "v26", title: "Advanced Patterns", url: "https://www.youtube.com/watch?v=F2Z8bk5XQBI", duration: 850, thumbnail: "", order: 7, completed: false, watchedPercent: 15 },
    ],
  },
  {
    id: "course_005",
    title: "API Integration & REST",
    description: "Fetch, Axios, error handling, caching, and real-world API patterns",
    icon: "🔗",
    category: "Backend",
    difficulty: "Intermediate",
    totalVideos: 6,
    completedVideos: 3,
    progress: 55,
    estimatedHours: 6,
    tags: ["API", "REST", "HTTP"],
    videoLinks: [
      { id: "v27", title: "HTTP Fundamentals", url: "https://www.youtube.com/watch?v=-MTSQjw5DrM", duration: 620, thumbnail: "", order: 1, completed: true, watchedPercent: 100 },
      { id: "v28", title: "Fetch API & Promises", url: "https://www.youtube.com/watch?v=cuEtnrL9-H0", duration: 700, thumbnail: "", order: 2, completed: true, watchedPercent: 100 },
      { id: "v29", title: "Axios & Interceptors", url: "https://www.youtube.com/watch?v=6LyagkoRWYA", duration: 680, thumbnail: "", order: 3, completed: true, watchedPercent: 100 },
      { id: "v30", title: "Error Handling Patterns", url: "https://www.youtube.com/watch?v=DFN5Zl9S6eq", duration: 550, thumbnail: "", order: 4, completed: false, watchedPercent: 0 },
      { id: "v31", title: "Caching & SWR/React Query", url: "https://www.youtube.com/watch?v=aLQGQovz3ww", duration: 800, thumbnail: "", order: 5, completed: false, watchedPercent: 0 },
      { id: "v32", title: "Authentication & JWT", url: "https://www.youtube.com/watch?v=mbsmsi7l3r4", duration: 900, thumbnail: "", order: 6, completed: false, watchedPercent: 0 },
    ],
  },
  {
    id: "course_006",
    title: "Web Security Essentials",
    description: "XSS, CSRF, CORS, CSP, and secure coding for modern web apps",
    icon: "🔐",
    category: "Security",
    difficulty: "Advanced",
    totalVideos: 5,
    completedVideos: 0,
    progress: 0,
    estimatedHours: 4,
    tags: ["Security", "XSS", "CORS"],
    videoLinks: [
      { id: "v33", title: "Web Security Overview", url: "https://www.youtube.com/watch?v=WlmKwIe9z1Q", duration: 750, thumbnail: "", order: 1, completed: false, watchedPercent: 0 },
      { id: "v34", title: "Cross-Site Scripting (XSS)", url: "https://www.youtube.com/watch?v=EoaDgUgS6QA", duration: 680, thumbnail: "", order: 2, completed: false, watchedPercent: 0 },
      { id: "v35", title: "CSRF & CORS Deep Dive", url: "https://www.youtube.com/watch?v=eWEgUcHPle0", duration: 700, thumbnail: "", order: 3, completed: false, watchedPercent: 0 },
      { id: "v36", title: "Content Security Policy", url: "https://www.youtube.com/watch?v=txHc4zk6w3s", duration: 600, thumbnail: "", order: 4, completed: false, watchedPercent: 0 },
      { id: "v37", title: "Secure Coding Practices", url: "https://www.youtube.com/watch?v=4YOpILi9Oxs", duration: 850, thumbnail: "", order: 5, completed: false, watchedPercent: 0 },
    ],
  },
]

export const DUMMY_LEADERBOARD: LeaderboardEntry[] = [
  { rank: 1, studentId: "s10", name: "Priya Sharma", avatar: "", xp: 12500, level: 24, streak: 32, coursesCompleted: 12 },
  { rank: 2, studentId: "s11", name: "Marcus Chen", avatar: "", xp: 11200, level: 22, streak: 28, coursesCompleted: 10 },
  { rank: 3, studentId: "s12", name: "Sofia Reyes", avatar: "", xp: 10800, level: 21, streak: 15, coursesCompleted: 11 },
  { rank: 4, studentId: "s13", name: "Aiden Okafor", avatar: "", xp: 9500, level: 19, streak: 20, coursesCompleted: 9 },
  { rank: 5, studentId: "s14", name: "Emma Williams", avatar: "", xp: 8900, level: 18, streak: 12, coursesCompleted: 8 },
  { rank: 6, studentId: "s15", name: "Kai Tanaka", avatar: "", xp: 8200, level: 17, streak: 10, coursesCompleted: 7 },
  { rank: 7, studentId: "s16", name: "Luna Petrov", avatar: "", xp: 7600, level: 16, streak: 9, coursesCompleted: 7 },
  { rank: 8, studentId: "s17", name: "Ravi Patel", avatar: "", xp: 6900, level: 15, streak: 14, coursesCompleted: 6 },
  { rank: 9, studentId: "s18", name: "Chloe Dubois", avatar: "", xp: 5800, level: 14, streak: 6, coursesCompleted: 5 },
  { rank: 10, studentId: "s19", name: "Hassan Ali", avatar: "", xp: 5200, level: 13, streak: 11, coursesCompleted: 5 },
  // Current student
  { rank: 23, studentId: "student_001", name: "Alex Johnson", avatar: "", xp: 4250, level: 12, streak: 7, coursesCompleted: 4 },
]

export const DUMMY_DAILY_CHALLENGES: DailyChallenge[] = [
  { id: "dc1", title: "Watch 30 minutes", description: "Watch any video for 30 minutes", xpReward: 50, type: "watch", completed: true, progress: 30, target: 30 },
  { id: "dc2", title: "Perfect Quiz", description: "Score 100% on any quiz", xpReward: 100, type: "quiz", completed: false, progress: 0, target: 1 },
  { id: "dc3", title: "Streak Keeper", description: "Log in and study today", xpReward: 25, type: "streak", completed: true, progress: 1, target: 1 },
  { id: "dc4", title: "Review Master", description: "Review 3 completed lessons", xpReward: 75, type: "review", completed: false, progress: 1, target: 3 },
]

export const DUMMY_NOTIFICATIONS: Notification[] = [
  { id: "n1", type: "achievement", title: "Badge Earned!", message: "You earned the Night Owl badge", timestamp: "2 hours ago", read: false, icon: "🦉" },
  { id: "n2", type: "milestone", title: "Level Up!", message: "You reached Level 12", timestamp: "1 day ago", read: false, icon: "⬆️" },
  { id: "n3", type: "challenge", title: "Daily Challenge", message: "New challenges available!", timestamp: "3 hours ago", read: true, icon: "🎯" },
  { id: "n4", type: "reminder", title: "Keep Your Streak!", message: "Don't forget to study today", timestamp: "5 hours ago", read: true, icon: "🔥" },
]

// ============================================================
// ASSESSMENT QUESTION BANKS BY DIFFICULTY
// These simulate what your FLAN-T5 / LLM API would return as JSON
// ============================================================

export const QUESTION_BANK: Record<string, AssessmentQuestion[]> = {
  easy: [
    {
      id: "q_e1", type: "mcq", question: "What is React?",
      options: ["A database", "A JavaScript library for building UIs", "A CSS framework", "A backend language"],
      correctAnswer: 1, difficulty: "easy", points: 10, explanation: "React is a JavaScript library developed by Facebook for building user interfaces.",
      topicId: "course_001",
      llmMetadata: { model: "flan-t5-base", generatedFrom: "video_transcript", difficultyScore: 0.2, bloomsLevel: "remember" },
    },
    {
      id: "q_e2", type: "mcq", question: "What does JSX stand for?",
      options: ["JavaScript XML", "Java Syntax Extension", "JSON Extra", "JavaScript XHR"],
      correctAnswer: 0, difficulty: "easy", points: 10, explanation: "JSX stands for JavaScript XML, a syntax extension for JavaScript.",
      topicId: "course_001",
      llmMetadata: { model: "flan-t5-base", generatedFrom: "video_transcript", difficultyScore: 0.15, bloomsLevel: "remember" },
    },
    {
      id: "q_e3", type: "true-false", question: "React components must always return JSX.",
      options: ["True", "False"],
      correctAnswer: 1, difficulty: "easy", points: 10, explanation: "Components can return null, which means they render nothing.",
      topicId: "course_001",
      llmMetadata: { model: "flan-t5-base", generatedFrom: "video_transcript", difficultyScore: 0.25, bloomsLevel: "understand" },
    },
    {
      id: "q_e4", type: "mcq", question: "Which hook is used to manage state in a functional component?",
      options: ["useEffect", "useState", "useRef", "useMemo"],
      correctAnswer: 1, difficulty: "easy", points: 10, explanation: "useState is the primary hook for managing local state in functional components.",
      topicId: "course_001",
      llmMetadata: { model: "flan-t5-base", generatedFrom: "video_transcript", difficultyScore: 0.2, bloomsLevel: "remember" },
    },
    {
      id: "q_e5", type: "mcq", question: "What is the virtual DOM?",
      options: ["A direct copy of the real DOM", "A lightweight in-memory representation of the real DOM", "A CSS rendering engine", "A browser API"],
      correctAnswer: 1, difficulty: "easy", points: 10, explanation: "The virtual DOM is a lightweight JavaScript representation that React uses for efficient updates.",
      topicId: "course_001",
      llmMetadata: { model: "flan-t5-base", generatedFrom: "video_transcript", difficultyScore: 0.3, bloomsLevel: "understand" },
    },
  ],
  medium: [
    {
      id: "q_m1", type: "mcq", question: "What is the purpose of the useEffect cleanup function?",
      options: ["To reset state", "To prevent memory leaks by cleaning up subscriptions", "To optimize rendering", "To handle errors"],
      correctAnswer: 1, difficulty: "medium", points: 20, explanation: "The cleanup function in useEffect prevents memory leaks by removing event listeners, subscriptions, etc.",
      topicId: "course_001",
      llmMetadata: { model: "flan-t5-large", generatedFrom: "video_transcript+context", difficultyScore: 0.55, bloomsLevel: "apply" },
    },
    {
      id: "q_m2", type: "mcq", question: "When does React re-render a component?",
      options: ["When props or state change", "Every second", "Only on page refresh", "When CSS changes"],
      correctAnswer: 0, difficulty: "medium", points: 20, explanation: "React re-renders when state or props change, triggering the reconciliation process.",
      topicId: "course_001",
      llmMetadata: { model: "flan-t5-large", generatedFrom: "video_transcript+context", difficultyScore: 0.5, bloomsLevel: "understand" },
    },
    {
      id: "q_m3", type: "mcq", question: "What is prop drilling and how can it be solved?",
      options: ["Passing props through many levels — solved with Context API", "A CSS technique", "A testing pattern", "A build optimization"],
      correctAnswer: 0, difficulty: "medium", points: 20, explanation: "Prop drilling is passing data through many component layers. Context API or state management libraries solve this.",
      topicId: "course_002",
      llmMetadata: { model: "flan-t5-large", generatedFrom: "video_transcript+context", difficultyScore: 0.6, bloomsLevel: "analyze" },
    },
    {
      id: "q_m4", type: "mcq", question: "What is the difference between controlled and uncontrolled components?",
      options: ["Controlled use state for form data, uncontrolled use refs", "They are the same", "Controlled are class components only", "Uncontrolled are faster"],
      correctAnswer: 0, difficulty: "medium", points: 20, explanation: "Controlled components derive form values from state; uncontrolled components use DOM refs directly.",
      topicId: "course_001",
      llmMetadata: { model: "flan-t5-large", generatedFrom: "video_transcript+context", difficultyScore: 0.55, bloomsLevel: "analyze" },
    },
    {
      id: "q_m5", type: "mcq", question: "What does the key prop do in a list?",
      options: ["Styles the element", "Helps React identify which items changed, added, or removed", "Sets the list order", "Adds accessibility"],
      correctAnswer: 1, difficulty: "medium", points: 20, explanation: "Keys help React's reconciliation algorithm efficiently update the DOM by tracking list item identity.",
      topicId: "course_001",
      llmMetadata: { model: "flan-t5-large", generatedFrom: "video_transcript+context", difficultyScore: 0.5, bloomsLevel: "understand" },
    },
  ],
  hard: [
    {
      id: "q_h1", type: "mcq", question: "How does React's fiber reconciliation differ from the stack reconciler?",
      options: ["Fiber allows incremental rendering by splitting work into units", "They are identical", "Stack is newer", "Fiber only works with class components"],
      correctAnswer: 0, difficulty: "hard", points: 30, explanation: "Fiber architecture enables incremental rendering, allowing React to pause and resume work for better performance.",
      topicId: "course_003",
      llmMetadata: { model: "flan-t5-xl", generatedFrom: "video_transcript+research", difficultyScore: 0.85, bloomsLevel: "evaluate" },
    },
    {
      id: "q_h2", type: "mcq", question: "When should you use useCallback vs useMemo?",
      options: ["useCallback memoizes functions, useMemo memoizes computed values", "They are identical", "useCallback is for effects", "useMemo is deprecated"],
      correctAnswer: 0, difficulty: "hard", points: 30, explanation: "useCallback returns a memoized callback function; useMemo returns a memoized computed value.",
      topicId: "course_003",
      llmMetadata: { model: "flan-t5-xl", generatedFrom: "video_transcript+research", difficultyScore: 0.75, bloomsLevel: "analyze" },
    },
    {
      id: "q_h3", type: "mcq", question: "What is the Suspense boundary pattern used for?",
      options: ["Error handling only", "Declarative loading states for async operations", "CSS animations", "Route protection"],
      correctAnswer: 1, difficulty: "hard", points: 30, explanation: "Suspense lets you specify loading fallbacks for components that perform async operations like data fetching or lazy loading.",
      topicId: "course_003",
      llmMetadata: { model: "flan-t5-xl", generatedFrom: "video_transcript+research", difficultyScore: 0.8, bloomsLevel: "apply" },
    },
    {
      id: "q_h4", type: "mcq", question: "What problem does the useTransition hook solve?",
      options: ["It handles CSS transitions", "It marks state updates as non-urgent to keep UI responsive", "It manages page navigation", "It replaces useEffect"],
      correctAnswer: 1, difficulty: "hard", points: 30, explanation: "useTransition lets you mark updates as transitions, keeping the UI responsive during expensive re-renders.",
      topicId: "course_003",
      llmMetadata: { model: "flan-t5-xl", generatedFrom: "video_transcript+research", difficultyScore: 0.8, bloomsLevel: "evaluate" },
    },
    {
      id: "q_h5", type: "mcq", question: "In server components, what determines the client/server boundary?",
      options: ["File extension", "The 'use client' directive at the top of the file", "Component name prefix", "Import order"],
      correctAnswer: 1, difficulty: "hard", points: 30, explanation: "The 'use client' directive marks the boundary — everything below it becomes a client component.",
      topicId: "course_003",
      llmMetadata: { model: "flan-t5-xl", generatedFrom: "video_transcript+research", difficultyScore: 0.7, bloomsLevel: "understand" },
    },
  ],
}

// ============================================================
// SIMULATED ATTENTION DATA (from your OCR/CV model)
// ============================================================

export function generateAttentionSnapshot(): AttentionSnapshot {
  const states: Array<"attentive" | "inattentive" | "unfocused"> = ["attentive", "inattentive", "unfocused"]
  const weights = [0.6, 0.25, 0.15] // More likely to be attentive
  const rand = Math.random()
  let state: "attentive" | "inattentive" | "unfocused" = "attentive"
  if (rand > weights[0] + weights[1]) state = "unfocused"
  else if (rand > weights[0]) state = "inattentive"

  const scoreRanges = { attentive: [70, 100], inattentive: [30, 69], unfocused: [0, 29] }
  const [min, max] = scoreRanges[state]
  const score = Math.floor(Math.random() * (max - min + 1)) + min

  // FIX (B-6/J-1): neutral operational-signal wording, matching the same
  // fix in backend/ml/attention_model.py — no psychological-state claims,
  // no advice.
  const messages = {
    attentive: [
      "Camera-derived behavioural signal: high band.",
      "Operational signal for this interval: high.",
    ],
    inattentive: [
      "Camera-derived behavioural signal: medium band.",
      "Operational signal for this interval: medium.",
    ],
    unfocused: [
      "Camera-derived behavioural signal: low band.",
      "Operational signal for this interval: low.",
    ],
  }

  return {
    timestamp: new Date().toISOString(),
    score,
    state,
    confidence: Math.random() * 0.3 + 0.7,
    message: messages[state][Math.floor(Math.random() * messages[state].length)],
    modelResponse: {
      eye_contact: state === "attentive" ? Math.random() * 0.3 + 0.7 : Math.random() * 0.5,
      head_pose: state === "attentive" ? "forward" : state === "inattentive" ? "slightly_away" : "away",
      face_detected: Math.random() > 0.05,
      blink_rate: Math.floor(Math.random() * 10) + 10,
    },
  }
}

// ============================================================
// SIMULATED TRANSCRIPTION (from your transcription model)
// ============================================================

export const DUMMY_TRANSCRIPT_SEGMENTS: TranscriptSegment[] = [
  {
    id: "t1", text: "Welcome to this lesson on React fundamentals.", timestamp: "00:00", startTime: 0, endTime: 3, confidence: 0.97,
    modelResponse: { language: "en", words: [{ word: "Welcome", start: 0, end: 0.5, confidence: 0.98 }, { word: "to", start: 0.5, end: 0.6, confidence: 0.99 }, { word: "this", start: 0.6, end: 0.8, confidence: 0.97 }, { word: "lesson", start: 0.8, end: 1.2, confidence: 0.96 }] },
  },
  {
    id: "t2", text: "Today we'll explore how React uses a virtual DOM for efficient rendering.", timestamp: "00:04", startTime: 4, endTime: 8, confidence: 0.94,
    modelResponse: { language: "en", words: [{ word: "Today", start: 4, end: 4.3, confidence: 0.95 }, { word: "we'll", start: 4.3, end: 4.5, confidence: 0.93 }] },
  },
  {
    id: "t3", text: "Components are the building blocks of any React application.", timestamp: "00:09", startTime: 9, endTime: 12, confidence: 0.96,
    modelResponse: { language: "en", words: [{ word: "Components", start: 9, end: 9.6, confidence: 0.97 }] },
  },
  {
    id: "t4", text: "You can think of components as reusable, self-contained pieces of UI.", timestamp: "00:13", startTime: 13, endTime: 17, confidence: 0.92,
    modelResponse: { language: "en", words: [] },
  },
  {
    id: "t5", text: "There are two types: functional components and class components.", timestamp: "00:18", startTime: 18, endTime: 22, confidence: 0.95,
    modelResponse: { language: "en", words: [] },
  },
  {
    id: "t6", text: "Modern React strongly favors functional components with hooks.", timestamp: "00:23", startTime: 23, endTime: 27, confidence: 0.93,
    modelResponse: { language: "en", words: [] },
  },
  {
    id: "t7", text: "The useState hook lets you add state to functional components.", timestamp: "00:28", startTime: 28, endTime: 32, confidence: 0.96,
    modelResponse: { language: "en", words: [] },
  },
  {
    id: "t8", text: "useEffect handles side effects like data fetching and subscriptions.", timestamp: "00:33", startTime: 33, endTime: 37, confidence: 0.91,
    modelResponse: { language: "en", words: [] },
  },
]