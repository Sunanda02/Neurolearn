import { redirect } from "next/navigation"

/**
 * Root route (/) — redirect immediately to /dashboard.
 *
 * Previously this file rendered AutoCourseGenerator directly, with no
 * Sidebar or Navbar, because there is no layout.tsx at the app root that
 * provides the shell. Every other route (/dashboard, /video, /assessment,
 * /results, /leaderboard, /profile, /discover) has its own layout.tsx
 * wrapping Sidebar + Navbar — root was the only one missing it.
 *
 * Fix: redirect / → /dashboard. The AutoCourseGenerator content now lives
 * at /discover (app/discover/page.tsx) with its own proper layout.
 */
export default function RootPage() {
  redirect("/dashboard")
}