import { Lightbulb, Search, Sparkles, MessageSquare } from "lucide-react"

interface ThoughtProcessStep {
  step: string
  details: {
    user_question?: string
    generated_search_query?: string
    filter?: string
    results_summary?: Array<{ source_file: string; source_pages: number }>
    review_thought_process?: string
    valid_results?: Array<{ source_file: string; source_pages: number }>
    invalid_results?: Array<{ source_file: string; source_pages: number }>
    decision?: string
    final_answer?: string
  }
}

interface ThoughtProcessProps {
  isOpen: boolean
  onClose: () => void
  steps: ThoughtProcessStep[]
}

const StepIcon = ({ step }: { step: string }) => {
  switch (step) {
    case "retrieve":
      return <Search className="w-4 h-4 text-blue-400" />
    case "review":
      return <Sparkles className="w-4 h-4 text-purple-400" />
    case "response":
      return <MessageSquare className="w-4 h-4 text-green-400" />
    default:
      return null
  }
}

export function ThoughtProcess({ isOpen, onClose, steps }: ThoughtProcessProps) {
  if (!isOpen) return null

  return (
    <div className="fixed inset-y-0 right-0 w-96 bg-zinc-900 border-l border-zinc-700 p-4 overflow-y-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-2">
          <Lightbulb className="w-6 h-6 text-blue-400" />
          <h2 className="text-lg font-semibold">Thought Process</h2>
        </div>
        <button
          onClick={onClose}
          className="text-zinc-400 hover:text-zinc-200"
        >
          ×
        </button>
      </div>

      {/* Steps */}
      <div className="space-y-6">
        {steps.map((step, index) => (
          <div key={index} className="relative">
            {/* Step header */}
            <div className="flex items-center gap-2 mb-2">
              <StepIcon step={step.step} />
              <h3 className="font-medium capitalize">
                {step.step}
              </h3>
            </div>

            {/* Step content */}
            <div className="pl-6 space-y-3 text-sm">
              {step.step === "retrieve" && (
                <>
                  <div className="text-zinc-300">
                    <div className="font-medium mb-1">Searching for text similar to...</div>
                    <div className="bg-zinc-800 p-2 rounded">
                      {step.details.generated_search_query}
                    </div>
                  </div>
                  {step.details.filter && (
                    <div className="text-zinc-300">
                      <div className="font-medium mb-1">Filter</div>
                      <div className="bg-zinc-800 p-2 rounded">
                        {step.details.filter}
                      </div>
                    </div>
                  )}
                  {step.details.results_summary && (
                    <div className="text-zinc-300">
                      <div className="font-medium mb-1">Found Documents</div>
                      <div className="space-y-1">
                        {step.details.results_summary.map((result, i) => (
                          <div key={i} className="text-blue-400">
                            {result.source_file} (p.{result.source_pages})
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </>
              )}

              {step.step === "review" && (
                <>
                  <div className="text-zinc-300">
                    <div className="font-medium mb-1">Analysis</div>
                    <div className="bg-zinc-800 p-2 rounded">
                      {step.details.review_thought_process}
                    </div>
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    <div className="text-zinc-300">
                      <div className="font-medium mb-1 text-green-400">Valid Results</div>
                      <div className="space-y-1">
                        {step.details.valid_results?.map((result, i) => (
                          <div key={i} className="text-blue-400">
                            {result.source_file} (p.{result.source_pages})
                          </div>
                        ))}
                      </div>
                    </div>
                    <div className="text-zinc-300">
                      <div className="font-medium mb-1 text-red-400">Invalid Results</div>
                      <div className="space-y-1">
                        {step.details.invalid_results?.map((result, i) => (
                          <div key={i} className="text-blue-400">
                            {result.source_file} (p.{result.source_pages})
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                  <div className="text-zinc-300">
                    <div className="font-medium mb-1">Decision</div>
                    <div className="bg-zinc-800 p-2 rounded capitalize">
                      {step.details.decision}
                    </div>
                  </div>
                </>
              )}

              {step.step === "response" && (
                <div className="text-zinc-300">
                  <div className="font-medium mb-1">Generated Response</div>
                  <div className="bg-zinc-800 p-2 rounded">
                    {step.details.final_answer}
                  </div>
                </div>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
} 