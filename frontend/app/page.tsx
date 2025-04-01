/* frontend/app/page.tsx */
"use client"

import React, { useState, useRef, useEffect, FormEvent } from "react"
import { Bot, Search, Sparkles, User, ArrowRight, Lightbulb } from "lucide-react"
import { Button, Input, ScrollArea } from "@/components/ui"
import { ThoughtProcess } from "@/components/thought_process"
import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"

interface Citation {
  id: string
  display_text: string
  source_file: string
  source_pages: number
  reference_number?: number
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

/**
 * Parse citation tags from the raw text.
 *
 * For every occurrence of a citation tag like:
 *
 *    <cit>DXC Corporate FAQs.pdf - page 22</cit>
 *
 * we replace it with a numbered marker (e.g. [1]). If the same source
 * (i.e. the same filename–page combo) appears more than once, we reuse the same number.
 */
const parseCitTags = (text: string) => {
  const citRegex = /<cit>([^<]+)<\/cit>/g
  const citations: Citation[] = []
  const citationMap = new Map<string, number>()

  const processedText = text.replace(citRegex, (_, displayText) => {
    const cleanDisplay = displayText.trim()
    if (citationMap.has(cleanDisplay)) {
      return `[${citationMap.get(cleanDisplay)}]`
    } else {
      const refNumber = citations.length + 1
      citationMap.set(cleanDisplay, refNumber)
      // Expecting format: "filename - page {number}"
      const parts = cleanDisplay.split("-")
      const sourceFile = parts[0].trim()
      const pageMatch = parts[1] ? parts[1].trim().match(/\d+/) : null
      const source_pages = pageMatch ? parseInt(pageMatch[0], 10) : 0
      citations.push({
        id: cleanDisplay,
        display_text: cleanDisplay,
        source_file: sourceFile,
        source_pages,
        reference_number: refNumber,
      })
      return `[${refNumber}]`
    }
  })

  return { processedText, citations }
}

/**
 * Custom paragraph renderer for ReactMarkdown.
 * Recursively processes text nodes to wrap citation markers in clickable links.
 */
const CustomParagraph = ({ children, ...props }: React.ComponentProps<'p'>) => {
  const processNode = (node: React.ReactNode): React.ReactNode => {
    // If the node is a string, process it for citations
    if (typeof node === 'string') {
      return node.split(/(\[\d+\])/g).map((part, i) => {
        if (/^\[\d+\]$/.test(part)) {
          const citationNumber = part.match(/\d+/)?.[0]
          return (
            <sup key={i}>
              <a
                href="#"
                className="text-blue-400 hover:text-blue-300"
                onClick={(e) => {
                  e.preventDefault()
                  handleCitationClick(citationNumber)
                }}
              >
                {part}
              </a>
            </sup>
          )
        }
        return part
      })
    }
    
    // If the node is an array, process each child
    if (Array.isArray(node)) {
      return node.map((child, i) => <React.Fragment key={i}>{processNode(child)}</React.Fragment>)
    }
    
    // If the node is a React element, process its children
    if (React.isValidElement(node)) {
      const elementNode = node as React.ReactElement<{ children?: React.ReactNode }>
      return React.cloneElement(elementNode, {
        key: elementNode.key,
        children: processNode(elementNode.props.children)
      })
    }
    
    // Return unchanged if none of the above
    return node
  }

  return <p {...props}>{processNode(children)}</p>
}

/**
 * Handler for citation clicks.
 */
const handleCitationClick = (citationNumber: string | undefined) => {
  if (citationNumber) {
    console.log("Citation clicked:", citationNumber)
    alert(`Citation ${citationNumber} clicked.`)
  }
}

/**
 * Custom heading components for ReactMarkdown.
 * Maps h1-h6 tags to appropriate Tailwind classes for styling.
 */
const CustomHeading = (level: 1 | 2 | 3 | 4 | 5 | 6) => {
  const Tag = `h${level}` as const
  return function Heading({ children, ...props }: React.ComponentProps<typeof Tag>) {
    const sizeClasses = {
      1: 'text-2xl font-bold mb-4',
      2: 'text-xl font-semibold mb-3',
      3: 'text-lg font-medium mb-2',
      4: 'text-base font-medium mb-2',
      5: 'text-sm font-medium mb-1',
      6: 'text-sm font-medium mb-1'
    }[level]

    return React.createElement(Tag, { className: sizeClasses, ...props }, children)
  }
}

export default function ChatInterface() {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState("")
  const [isProcessing, setIsProcessing] = useState(false)
  const [isThoughtProcessOpen, setIsThoughtProcessOpen] = useState(false)
  const [currentThoughtProcess, setCurrentThoughtProcess] = useState<
    Array<{ step: string; details: Record<string, any> }>
  >([])
  // Buffer for the raw response text.
  const [rawResponse, setRawResponse] = useState("")

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    if (!input.trim() || isProcessing) return

    const userQuestion = input.trim()
    setInput("")
    setIsProcessing(true)
    setRawResponse("") // Reset raw text for new query.

    // Add user message.
    setMessages((prev) => [...prev, { type: "user", content: userQuestion }])

    try {
      const query = encodeURIComponent(userQuestion)
      const eventSource = new EventSource(`http://localhost:5000/chat?user_input=${query}`, {
        withCredentials: true,
      })

      let currentThoughtProcess: Message["thought_process"] = []

      const safeParseJSON = (data: string) => {
        try {
          return data ? JSON.parse(data) : null
        } catch (error) {
          console.error("Failed to parse JSON:", error)
          return null
        }
      }

      // "retrieve" event: blue bubble.
      eventSource.addEventListener("retrieve", (e) => {
        const data = safeParseJSON(e.data)
        if (data?.message) {
          setMessages((prev) => {
            const newMessages = [...prev]
            // Mark any previous retrieve/review messages as completed
            newMessages.forEach(msg => {
              if (msg.type === "status" && !msg.completed) {
                msg.completed = true
              }
            })
            return [
              ...newMessages,
              {
                type: "status",
                content: STATUS_MESSAGES.SEARCHING,
                icon: "search",
                color: "blue",
                completed: false,
              },
            ]
          })
        }
      })

      // "review" event: purple bubble.
      eventSource.addEventListener("review", (e) => {
        const data = safeParseJSON(e.data)
        if (data?.message) {
          setMessages((prev) => {
            const newMessages = [...prev]
            // Mark any previous retrieve/review messages as completed
            newMessages.forEach(msg => {
              if (msg.type === "status" && !msg.completed) {
                msg.completed = true
              }
            })
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

      // Accumulate streaming response.
      eventSource.addEventListener("response_chunk", (e) => {
        const data = safeParseJSON(e.data)
        if (data?.chunk) {
          setRawResponse((prevRaw) => {
            const newRaw = prevRaw + data.chunk
            const { processedText, citations } = parseCitTags(newRaw)
            setMessages((prev) => {
              const newMessages = [...prev]
              // Mark any previous retrieve/review messages as completed
              newMessages.forEach(msg => {
                if (msg.type === "status" && !msg.completed) {
                  msg.completed = true
                }
              })
              
              const lastMsg = prev.slice(-1)[0]
              if (lastMsg && lastMsg.type === "assistant") {
                lastMsg.content = processedText
                lastMsg.citations = citations
                return [...prev.slice(0, -1), lastMsg]
              } else {
                return [
                  ...newMessages,
                  {
                    type: "assistant",
                    content: processedText,
                    citations,
                    thought_process: currentThoughtProcess,
                  },
                ]
              }
            })
            return newRaw
          })
        }
      })

      // Final payload: update only the thought process (leave citations as parsed inline).
      eventSource.addEventListener("final_payload", (e) => {
        const data = safeParseJSON(e.data)
        if (data?.payload) {
          const { thought_process } = data.payload as {
            citations: Citation[]
            thought_process: Array<{ step: string; details: Record<string, any> }>
          }
          currentThoughtProcess = thought_process
          setMessages((prev) => {
            const lastMsg = prev.slice(-1)[0]
            if (lastMsg && lastMsg.type === "assistant") {
              lastMsg.thought_process = thought_process
              return [...prev.slice(0, -1), lastMsg]
            }
            return prev
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
        console.error("EventSource error:", error)
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

  return (
    <div className="flex flex-col items-center min-h-screen w-full bg-zinc-900 text-zinc-100">
      {/* Header */}
      <header className="my-6 text-center">
        <h1 className="text-2xl font-semibold tracking-tight">Agentic RAG Chat</h1>
      </header>

      {/* Main chat area */}
      <div className="w-full max-w-4xl flex-1 px-4 pb-2">
        <ScrollArea className="h-[calc(100vh-10rem)]">
          <div className="space-y-4 pt-2">
            {messages.map((message, index) => {
              const isUser = message.type === "user"
              const isStatus = message.type === "status"
              const alignmentClass = isUser ? "justify-end" : "justify-start"

              // For status messages, reapply color-based styling.
              let bubbleClass = isUser
                ? "bg-zinc-800/70 border border-zinc-600/50 shadow-sm"
                : "bg-zinc-800/90 border border-zinc-700/90 shadow-sm"
              if (isStatus) {
                const statusBase = message.color === "blue" ? "border-blue-700/80" : "border-purple-700/80"
                const statusState = message.completed
                  ? "bg-zinc-800/20 opacity-75"
                  : message.color === "blue"
                  ? "bg-blue-900/20 animate-fade-in"
                  : "bg-purple-900/20 animate-fade-in"
                bubbleClass = `${statusBase} ${statusState}`
              }

              // Select appropriate icon.
              let iconEl = null
              if (isUser) {
                iconEl = <User className="w-5 h-5 text-blue-400/90" />
              } else if (isStatus) {
                iconEl =
                  message.icon === "search" ? (
                    <Search className={`w-5 h-5 text-blue-400 ${!message.completed && "animate-pulse"}`} />
                  ) : (
                    <Sparkles className={`w-5 h-5 text-purple-400 ${!message.completed && "animate-pulse"}`} />
                  )
              } else {
                iconEl = <Bot className="w-5 h-5 text-blue-400/90" />
              }

              return (
                <div key={index} className={`flex w-full ${alignmentClass}`}>
                  <div
                    className={`${bubbleClass} p-3 rounded-lg max-w-xl flex items-start gap-2.5 text-sm relative backdrop-blur-sm ${
                      isUser ? "rounded-br-none" : "rounded-bl-none"
                    }`}
                  >
                    {iconEl}
                    <div className="flex-1 leading-relaxed whitespace-pre-wrap pr-12">
                      {isStatus ? (
                        <span className="text-zinc-300">{message.content}</span>
                      ) : (
                        <ReactMarkdown
                          remarkPlugins={[remarkGfm]}
                          components={{
                            p: CustomParagraph,
                            h1: CustomHeading(1),
                            h2: CustomHeading(2),
                            h3: CustomHeading(3),
                            h4: CustomHeading(4),
                            h5: CustomHeading(5),
                            h6: CustomHeading(6)
                          }}
                        >
                          {message.content}
                        </ReactMarkdown>
                      )}
                      {/* Render citation list below the message */}
                      {!isStatus && message.citations && message.citations.length > 0 && (
                        <div className="mt-3 pt-3 border-t border-zinc-700/40 flex flex-wrap gap-2 text-sm text-blue-400/90">
                          {message.citations.map((cite, idx) => (
                            <div
                              key={cite.id}
                              className="hover:text-blue-300 cursor-pointer transition-colors duration-150"
                              title={cite.display_text}
                              onClick={() => handleCitationClick(String(idx + 1))}
                            >
                              <span className="text-xs">[{idx + 1}]</span>{" "}
                              {cite.display_text}
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                    {message.thought_process && (
                      <button
                        onClick={() => {
                          setCurrentThoughtProcess(message.thought_process || [])
                          setIsThoughtProcessOpen(true)
                        }}
                        className="absolute top-3 right-3 p-1.5 rounded-full bg-blue-500/10 hover:bg-blue-500/20 text-blue-400/90 transition-all transform hover:scale-105 focus:outline-none focus:ring-2 focus:ring-blue-500/40"
                        title="View thought process"
                      >
                        <Lightbulb className="w-5 h-5" />
                      </button>
                    )}
                  </div>
                </div>
              )
            })}
          </div>
        </ScrollArea>
      </div>

      {/* Bottom input area */}
      <div className="w-full max-w-4xl px-4 pb-6">
        <form onSubmit={handleSubmit} className="relative">
          <div className="relative flex items-center w-full rounded-full bg-zinc-800 border border-zinc-700 shadow-sm px-5 py-3">
            <Input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask anything..."
              disabled={isProcessing}
              className="flex-1 bg-transparent border-0 focus:ring-0 focus:outline-none pr-12 px-0"
            />
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
