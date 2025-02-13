/* app/page.tsx */
"use client"

import { useState, useRef, useEffect, FormEvent } from "react"
import { Bot, Search, Sparkles, User, ArrowRight, Lightbulb } from "lucide-react"
import { Button, Input, ScrollArea } from "@/components/ui"
import { ThoughtProcess } from "@/components/thought_process"

interface Citation {
  id: string
  content: string
  source_file: string
  source_pages: number
  score: number
}

interface Message {
  type: "status" | "assistant" | "user"
  content: string
  icon?: "search" | "analyze"
  color?: "blue" | "purple"
  citations?: Citation[]
  thought_process?: Array<{ step: string; details: Record<string, any> }>
  completed?: boolean
}

const STATUS_MESSAGES = {
  SEARCHING: "Searching for documents...",
  ANALYZING: "Reviewing the documents...",
} as const

export default function ChatInterface() {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState("")
  const [isProcessing, setIsProcessing] = useState(false)
  const [isThoughtProcessOpen, setIsThoughtProcessOpen] = useState(false)
  const [currentThoughtProcess, setCurrentThoughtProcess] = useState<Array<{ step: string; details: Record<string, any> }>>([])
  const scrollRef = useRef<HTMLDivElement>(null)

  // Auto-scroll effect
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTo({
        top: scrollRef.current.scrollHeight,
        behavior: "smooth"
      })
    }
  }, [messages]) // Scroll whenever messages change

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    if (!input.trim() || isProcessing) return

    const userQuestion = input.trim()
    setInput("")
    setIsProcessing(true)

    // Add user message
    setMessages((prev) => [...prev, { type: "user", content: userQuestion }])

    try {
      // SSE
      const query = encodeURIComponent(userQuestion)
      const eventSource = new EventSource(
        `http://localhost:5000/chat?user_input=${query}`,
        { withCredentials: true }
      )

      let responseText = ""
      let currentCitations: Message["citations"] = []
      let currentThoughtProcess: Message["thought_process"] = []

      const safeParseJSON = (data: string) => {
        try {
          return data ? JSON.parse(data) : null
        } catch (error) {
          console.error("Failed to parse JSON:", error)
          return null
        }
      }

      eventSource.addEventListener("retrieve", (e) => {
        const data = safeParseJSON(e.data)
        if (data?.message) {
          setMessages((prev) => [
            ...prev,
            {
              type: "status",
              content: STATUS_MESSAGES.SEARCHING,
              icon: "search",
              color: "blue",
            },
          ])
        }
      })

      eventSource.addEventListener("review", (e) => {
        const data = safeParseJSON(e.data)
        if (data?.message) {
          setMessages((prev) => {
            const newMessages = [...prev]
            // Mark the previous status as completed if it exists
            const lastMessage = newMessages[newMessages.length - 1]
            if (lastMessage?.type === "status") {
              lastMessage.completed = true
            }
            return [
              ...newMessages,
              {
                type: "status",
                content: STATUS_MESSAGES.ANALYZING,
                icon: "analyze",
                color: "purple",
                completed: false,
              },
            ]
          })
        }
      })

      eventSource.addEventListener("response_chunk", (e) => {
        const data = safeParseJSON(e.data)
        if (data?.chunk) {
          responseText += data.chunk
          setMessages((prev) => {
            const newMessages = [...prev]
            // Mark the last status message as completed
            const lastStatus = newMessages.findLast(m => m.type === "status")
            if (lastStatus) {
              lastStatus.completed = true
            }
            
            const lastMsg = newMessages[newMessages.length - 1]
            if (lastMsg && lastMsg.type === "assistant") {
              lastMsg.content = responseText
              lastMsg.citations = currentCitations
              lastMsg.thought_process = currentThoughtProcess
            } else {
              newMessages.push({
                type: "assistant",
                content: responseText,
                citations: currentCitations,
                thought_process: currentThoughtProcess,
              })
            }
            return newMessages
          })
        }
      })

      eventSource.addEventListener("final_payload", (e) => {
        const data = safeParseJSON(e.data)
        if (data?.payload) {
          const { citations, thought_process } = data.payload as {
            citations: Citation[]
            thought_process: Array<{ step: string; details: Record<string, any> }>
          }
          currentCitations = citations
          currentThoughtProcess = thought_process

          setMessages((prev) => {
            const newMessages = [...prev]
            const lastMessage = newMessages[newMessages.length - 1]
            if (lastMessage?.type === "assistant") {
              lastMessage.citations = citations
              lastMessage.thought_process = thought_process
            }
            return newMessages
          })
        }
      })

      eventSource.addEventListener("server-error", (e: MessageEvent) => {
        const data = safeParseJSON(e.data)
        setMessages((prev) => [
          ...prev,
          {
            type: "assistant",
            content: `Error: ${data?.message || "An error occurred"}`,
          },
        ])
        eventSource.close()
        setIsProcessing(false)
      })

      eventSource.addEventListener("end", () => {
        eventSource.close()
        setIsProcessing(false)
      })

      eventSource.onerror = (error) => {
        console.error("EventSource failed:", error)
        setMessages((prev) => [
          ...prev,
          {
            type: "assistant",
            content: "Connection to server failed. Please try again.",
          },
        ])
        eventSource.close()
        setIsProcessing(false)
      }
    } catch (error) {
      console.error("Error in chat handler:", error)
      setMessages((prev) => [
        ...prev,
        { type: "assistant", content: "An error occurred while processing your request." },
      ])
      setIsProcessing(false)
    }
  }

  const renderCitations = (citations?: Citation[]) => {
    if (!citations || citations.length === 0) return null
    return (
      <div className="mt-2 space-y-1 text-sm">
        {citations.map((cite) => (
          <div 
            key={cite.id} 
            className="text-blue-400 hover:text-blue-300 cursor-pointer inline-block mr-3"
            title={cite.content}
          >
            {cite.source_file} (p.{cite.source_pages})
          </div>
        ))}
      </div>
    )
  }

  return (
    <div className="flex flex-col items-center min-h-screen w-full bg-zinc-900 text-zinc-100">
      {/* Header */}
      <header className="my-6 text-center">
        <h1 className="text-2xl font-semibold">Agentic RAG Chat</h1>
      </header>

      {/* Main chat area */}
      <div className="w-full max-w-4xl flex-1 px-4 pb-2">
        <ScrollArea ref={scrollRef} className="h-[calc(100vh-10rem)]">
          <div className="space-y-4 pt-2">
            {messages.map((message, index) => {
              const isUser = message.type === "user"
              const isStatus = message.type === "status"

              const alignmentClass = isUser ? "justify-end" : "justify-start"

              let bubbleClass = "bg-zinc-800 border border-zinc-700"
              if (isStatus) {
                const statusBase = message.color === "blue"
                  ? "border-blue-700"
                  : "border-purple-700"
                
                const statusState = message.completed
                  ? "bg-zinc-800/30 opacity-75"
                  : `${message.color === "blue" ? "bg-blue-900/30" : "bg-purple-900/30"} animate-fade-in relative overflow-hidden before:absolute before:inset-0 before:bg-gradient-to-r before:from-transparent before:via-white/5 before:to-transparent before:animate-shimmer`
                
                bubbleClass = `${statusBase} ${statusState}`
              }

              // Icon logic
              let iconEl = null
              if (isUser) {
                iconEl = <User className="w-5 h-5 text-zinc-200" />
              } else if (isStatus) {
                iconEl =
                  message.icon === "search" ? (
                    <Search className={`w-5 h-5 text-blue-400 ${!message.completed && 'animate-pulse'}`} />
                  ) : (
                    <Sparkles className={`w-5 h-5 text-purple-400 ${!message.completed && 'animate-pulse'}`} />
                  )
              } else {
                iconEl = <Bot className="w-5 h-5 text-zinc-300" />
              }

              return (
                <div key={index} className={`flex w-full ${alignmentClass}`}>
                  <div
                    className={`p-3 rounded-lg max-w-xl flex items-start gap-2 text-sm ${bubbleClass} ${
                      isUser ? "rounded-tr-none" : "rounded-tl-none"
                    } relative ${!isUser && message.thought_process ? 'pr-12' : ''}`}
                  >
                    {iconEl}
                    <div className="flex-1 leading-normal whitespace-pre-wrap">
                      {message.content}
                      {!isStatus && renderCitations(message.citations)}
                    </div>
                    {message.thought_process && (
                      <button
                        onClick={() => {
                          setCurrentThoughtProcess(message.thought_process || [])
                          setIsThoughtProcessOpen(true)
                        }}
                        className="absolute top-3 right-3 p-1 rounded-full bg-blue-500/10 hover:bg-blue-500/20 text-blue-400 hover:text-blue-300 transition-all transform hover:scale-110"
                        title="View thought process"
                      >
                        <Lightbulb className="w-6 h-6" />
                      </button>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        </ScrollArea>
      </div>

      {/* Bottom input bar */}
      <div className="w-full max-w-4xl px-4 pb-6">
        <form onSubmit={handleSubmit} className="relative">
          {/* The big 'pill' container */}
          <div className="relative flex items-center w-full rounded-full bg-zinc-800 border border-zinc-700 shadow-sm px-5 py-3">
            {/* Enough right padding so text doesn't collide with arrow */}
            <Input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask anything..."
              disabled={isProcessing}
              className="flex-1 bg-transparent border-0 focus:ring-0 focus:outline-none pr-12 px-0"
            />

            {/* The arrow button is absolutely placed at right */}
            <Button
              type="submit"
              variant="circle"
              disabled={isProcessing}
              className="absolute right-2 bg-zinc-700 hover:bg-zinc-600 w-9 h-9 flex items-center justify-center"
            >
              <ArrowRight className="w-4 h-4" />
            </Button>
          </div>
        </form>
      </div>

      {/* Thought Process Panel */}
      <ThoughtProcess
        isOpen={isThoughtProcessOpen}
        onClose={() => setIsThoughtProcessOpen(false)}
        steps={currentThoughtProcess}
      />
    </div>
  )
}
