/* app/components/ui.tsx */
"use client"

import * as React from "react"
import { cn } from "@/lib/utils"
import { LucideIcon } from "lucide-react"

/*
  1) Button
*/
interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "default" | "secondary" | "circle"
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = "default", ...props }, ref) => {
    const baseClasses =
      "inline-flex items-center justify-center text-sm font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-zinc-400 focus:ring-offset-2 focus:ring-offset-zinc-900 disabled:opacity-50 disabled:pointer-events-none"

    const variants: Record<typeof variant, string> = {
      default: "bg-zinc-700 text-zinc-100 hover:bg-zinc-600 rounded-md px-4 py-2",
      secondary: "bg-zinc-600 text-zinc-100 hover:bg-zinc-500 rounded-md px-4 py-2",
      circle:
        "rounded-full w-10 h-10 bg-zinc-700 text-zinc-100 hover:bg-zinc-600",
    }

    return (
      <button
        ref={ref}
        className={cn(baseClasses, variants[variant], className)}
        {...props}
      />
    )
  }
)
Button.displayName = "Button"

/*
  2) Card
  (You can still use Card for any "bubble" or sub-container if you want,
   but we're not using it around the main chat area anymore.)
*/
interface CardProps extends React.HTMLAttributes<HTMLDivElement> {}

export function Card({ className, ...props }: CardProps) {
  return (
    <div
      className={cn(
        "rounded-lg border border-zinc-700 bg-zinc-800 p-4 shadow-md",
        className
      )}
      {...props}
    />
  )
}

/*
  3) Input
*/
interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  icon?: LucideIcon
}

export const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ className, icon: Icon, ...props }, ref) => {
    return (
      <>
        {Icon && (
          <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3">
            <Icon className="h-4 w-4 text-zinc-400" />
          </div>
        )}
        <input
          ref={ref}
          className={cn(
            "w-full min-w-0 text-sm text-zinc-100 placeholder-zinc-400 focus:outline-none",
            Icon ? "pl-9" : "",
            className
          )}
          {...props}
        />
      </>
    )
  }
)
Input.displayName = "Input"

/*
  4) ScrollArea
*/
interface ScrollAreaProps extends React.HTMLAttributes<HTMLDivElement> {}

export const ScrollArea = React.forwardRef<HTMLDivElement, ScrollAreaProps>(
  ({ className, ...props }, ref) => {
    const [hasOverflow, setHasOverflow] = React.useState(false)
    const contentRef = React.useRef<HTMLDivElement>(null)

    React.useEffect(() => {
      const checkOverflow = () => {
        if (contentRef.current) {
          const hasVerticalOverflow = contentRef.current.scrollHeight > contentRef.current.clientHeight
          setHasOverflow(hasVerticalOverflow)
        }
      }

      // Initial check
      checkOverflow()

      // Create a ResizeObserver to check for overflow when content size changes
      const resizeObserver = new ResizeObserver(() => {
        // Add a small delay to ensure content has been rendered
        setTimeout(checkOverflow, 0)
      })

      if (contentRef.current) {
        resizeObserver.observe(contentRef.current)
      }

      // Also check when window resizes
      window.addEventListener('resize', checkOverflow)

      return () => {
        resizeObserver.disconnect()
        window.removeEventListener('resize', checkOverflow)
      }
    }, [])

    return (
      <div
        ref={(node) => {
          // Handle both refs
          if (typeof ref === 'function') {
            ref(node)
          } else if (ref) {
            ref.current = node
          }
          contentRef.current = node
        }}
        className={cn(
          "overflow-y-auto overflow-x-hidden",
          hasOverflow && "scrollbar-thin scrollbar-track-transparent scrollbar-thumb-zinc-700 hover:scrollbar-thumb-zinc-600",
          className
        )}
        {...props}
      />
    )
  }
)
ScrollArea.displayName = "ScrollArea"
