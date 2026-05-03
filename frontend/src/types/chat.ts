export type ChatMode = 'rag' | 'direct' | 'auto'

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  text: string
  timestamp?: string
  status?: string
  sources?: RetrievalItem[]
  routeReason?: string
  mode?: ChatMode
}

export interface RetrievalItem {
  score: number
  source: string
  start: number
  end: number
  text: string
  metadata: Record<string, unknown>
}

export interface ChatResponsePayload {
  success: boolean
  message: string
  data: {
    answer: string
    mode: ChatMode
    intent: string
    route_reason: string
    quality: string | null
    retrieval_items: RetrievalItem[]
  }
}
