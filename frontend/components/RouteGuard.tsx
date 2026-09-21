"use client"

// FIX (auth request): previously every route rendered regardless of
// login state, since there was no login state — student_id was just a
// hardcoded constant. This component is mounted once, in the root
// layout, and gates every route in the app behind a real session.

import { useEffect } from "react"
import { usePathname, useRouter } from "next/navigation"
import { useAuth } from "@/lib/auth"

const PUBLIC_ROUTES = ["/login", "/signup", "/forgot-password", "/reset-password"]

export default function RouteGuard({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth()
  const pathname = usePathname()
  const router = useRouter()
  const isPublicRoute = PUBLIC_ROUTES.includes(pathname)

  useEffect(() => {
    if (loading) return
    if (!user && !isPublicRoute) {
      router.replace("/login")
    } else if (user && isPublicRoute) {
      router.replace("/dashboard")
    }
  }, [user, loading, isPublicRoute, router])

  // Avoid a flash of protected content before the redirect effect runs.
  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[var(--bg-primary)]">
        <div className="h-8 w-8 rounded-full border-2 border-[var(--border-strong)] border-t-transparent animate-spin" />
      </div>
    )
  }
  if (!user && !isPublicRoute) return null
  if (user && isPublicRoute) return null

  return <>{children}</>
}
