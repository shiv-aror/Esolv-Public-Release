import type { Message } from '../lib/types'

export interface ChatThread {
  id: string
  title: string
  createdAt: number
  updatedAt: number
  messages: Message[]
}

export function titleFromQuestion(question: string): string {
  const line = question.replace(/\s+/g, ' ').trim().replace(/[.!?]+$/, '')
  if (!line) return 'New chat'
  return line.length > 54 ? `${line.slice(0, 51).trimEnd()}…` : line
}

export function storedThread(thread: ChatThread): ChatThread {
  return {
    ...thread,
    messages: thread.messages.slice(-60).map(({ images: _images, files, status: _status, reviewSources: _reviewSources, reviewStage: _reviewStage, streaming, ...rest }) => ({
      ...rest,
      files: files?.map(({ name, size }) => ({ name, size })),
      ...(streaming ? { error: 'Response interrupted. Try again.' } : {}),
      streaming: false,
    })),
  }
}
