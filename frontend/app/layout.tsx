/* app/layout.tsx */
import "./globals.css"
import { Inter } from "next/font/google"
import { cn } from "@/lib/utils"

const inter = Inter({ subsets: ["latin"] })

export const metadata = {
  title: "Agentic RAG Chat",
  description: "Your RAG Chat interface",
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en" className="dark">
      <body
        className={cn(
          "bg-gray-900 text-gray-100 min-h-screen",
          inter.className
        )}
      >
        {children}
      </body>
    </html>
  )
}
