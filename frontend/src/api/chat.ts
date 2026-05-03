import type { ChatMode, ChatResponsePayload } from '../types/chat'

interface HistoryMessage {
  role: string
  content: string
}

// 作用：调用后端聊天接口，统一返回前端工作台渲染所需的结构。
export async function sendChatMessage(
  question: string,
  mode: ChatMode,
  history: HistoryMessage[],
): Promise<ChatResponsePayload['data']> {
  const response = await fetch('/api/v1/chat/respond', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      question,
      mode,
      messages: history,
    }),
  })

  const payload = (await response.json()) as ChatResponsePayload
  if (!response.ok || !payload.success) {
    throw new Error(payload.message || '聊天接口调用失败。')
  }
  return payload.data
}
