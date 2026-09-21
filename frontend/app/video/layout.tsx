"use client"

import { useEffect, useState } from "react"
import Sidebar from "@/components/Sidebar"
import Navbar from "@/components/Navbar"
import { fetchStudentProfile, type StudentProfile } from "@/lib/api"

export default function VideoLayout({ children }: { children: React.ReactNode }) {
  const [student, setStudent] = useState<StudentProfile | null>(null)

  useEffect(() => {
    fetchStudentProfile().then(setStudent).catch(() => {})
  }, [])

  return (
    <div className="min-h-screen bg-[var(--bg-primary)] flex">
      <Sidebar
        xp={student?.xp || 0}
        xpToNextLevel={student?.xpToNextLevel || 1}
        level={student?.level || 1}
        streak={student?.streak || 0}
      />
      <div className="flex-1 flex flex-col min-h-screen">
        <Navbar
          studentName={student?.name || "Student"}
          level={student?.level || 1}
          xp={student?.xp || 0}
          xpToNextLevel={student?.xpToNextLevel || 1}
          streak={student?.streak || 0}
        />
        <main className="flex-1 overflow-y-auto">{children}</main>
      </div>
    </div>
  )
}
