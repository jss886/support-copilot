<script setup lang="ts">
import { ref } from 'vue'

import { sendChatMessage } from '../api/chat'
import ChatComposer from '../components/ChatComposer.vue'
import ChatMessageCard from '../components/ChatMessageCard.vue'
import SidebarNav from '../components/SidebarNav.vue'
import type { ChatMessage, ChatMode } from '../types/chat'

const currentMode = ref<ChatMode>('rag')
const loading = ref(false)
const errorMessage = ref('')
const messages = ref<ChatMessage[]>([
  {
    id: 'welcome-assistant',
    role: 'assistant',
    text: '我可以帮你检索知识、分析问题、组织排查步骤。你可以直接发问题，也可以切换回答模式后再发送。',
  },
])

const quickQuestions = [
  '支付成功但库存没扣怎么办？',
  '如何定位订单接口的超时问题？',
  '给我总结一下 RAG 和 Direct 的适用区别。',
]

// 作用：把现有消息整理成接口需要的历史格式，便于后续扩展多轮上下文。
function buildHistoryPayload() {
  return messages.value.map((message) => ({
    role: message.role,
    content: message.text,
  }))
}

// 作用：往消息列表追加一条用户消息，保证提问会先落在界面上。
function appendUserMessage(question: string): void {
  messages.value.push({
    id: `user-${Date.now()}`,
    role: 'user',
    text: question,
    mode: currentMode.value,
  })
}

// 作用：把后端返回结果转成助手消息卡片，并附带路由信息和检索证据。
function appendAssistantMessage(payload: {
  answer: string
  retrieval_items: ChatMessage['sources']
}): void {
  messages.value.push({
    id: `assistant-${Date.now()}`,
    role: 'assistant',
    text: payload.answer,
    mode: currentMode.value,
    sources: payload.retrieval_items,
  })
}

// 作用：统一处理用户发送动作，串联提问、接口调用和结果落卡片。
async function handleSubmit(question: string): Promise<void> {
  errorMessage.value = ''
  appendUserMessage(question)
  loading.value = true

  try {
    const payload = await sendChatMessage(question, currentMode.value, buildHistoryPayload())
    appendAssistantMessage(payload)
  } catch (error) {
    const message = error instanceof Error ? error.message : '回答生成失败，请稍后重试。'
    errorMessage.value = message
    messages.value.push({
      id: `assistant-error-${Date.now()}`,
      role: 'assistant',
      text: `这次请求没有成功完成：${message}`,
      mode: currentMode.value,
    })
  } finally {
    loading.value = false
  }
}

// 作用：让示例问题可以一键带起真实请求，方便本地演示主流程。
function askQuickQuestion(question: string): void {
  void handleSubmit(question)
}
</script>

<template>
  <div class="app-shell">
    <SidebarNav />
    <main class="workspace-shell">
      <section class="quick-question-row">
        <button
          v-for="question in quickQuestions"
          :key="question"
          type="button"
          class="quick-question"
          @click="askQuickQuestion(question)"
        >
          {{ question }}
        </button>
      </section>

      <section class="chat-panel">
        <div class="chat-panel-header">
          <div>
            <div class="section-caption">对话流</div>
            <h2>问题分析与知识回答</h2>
          </div>
          <div class="chat-panel-status">
            <span class="online-dot"></span>
            <span>{{ loading ? '正在生成回答' : '接口已连接' }}</span>
          </div>
        </div>

        <div v-if="errorMessage" class="error-banner">{{ errorMessage }}</div>

        <div class="chat-message-list">
          <ChatMessageCard
            v-for="message in messages"
            :key="message.id"
            :message="message"
          />
        </div>
      </section>

      <ChatComposer
        :loading="loading"
        :mode="currentMode"
        @submit="handleSubmit"
        @update:mode="currentMode = $event"
      />
    </main>
  </div>
</template>
