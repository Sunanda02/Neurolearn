import type { Metadata } from "next"
import "./globals.css"
import { AuthProvider } from "@/lib/auth"
import RouteGuard from "@/components/RouteGuard"

export const metadata: Metadata = {
  title: "NeuroLearn",
  description: "Adaptive learning platform",
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <body className="font-sans antialiased noise-bg">
        <AuthProvider>
          <RouteGuard>{children}</RouteGuard>
        </AuthProvider>
      </body>
    </html>
  )
}
