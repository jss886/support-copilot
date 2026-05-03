<script setup lang="ts">
import { ref, watch } from 'vue'

import ModeSwitch from './ModeSwitch.vue'
import type { ChatMode } from '../types/chat'

const props = defineProps<{
  loading: boolean
  mode: ChatMode
}>()

const emit = defineEmits<{
  (event: 'submit', value: string): void
  (event: 'update:mode', value: ChatMode): void
}>()

const draft = ref('支付成功但库存没扣怎么办？')

watch(
  () => props.loading,
  (loading) => {
    if (!loading) {
      draft.value = ''
    }
  },
)

// 作用：在输入内容有效时提交问题，避免前端发送空消息。
function submitQuestion(): void {
  const value = draft.value.trim()
  if (!value || props.loading) {
    return
  }
  emit('submit', value)
}

// 作用：让输入框支持回车发送，提升聊天场景下的交互效率。
function handleKeydown(event: KeyboardEvent): void {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault()
    submitQuestion()
  }
}
</script>

<template>
  <section class="composer-shell">
    <textarea
      v-model="draft"
      class="composer-input"
      :disabled="loading"
      placeholder="输入你的问题，助手会结合模式给出回答..."
      rows="3"
      @keydown="handleKeydown"
    ></textarea>
    <div class="composer-toolbar">
      <div class="composer-tools">
        <button type="button" class="tool-button">⌘ 附件</button>
        <button type="button" class="tool-button">◫ 图片</button>
        <button type="button" class="tool-button"># 话题</button>
      </div>
      <div class="composer-actions">
        <ModeSwitch
          :model-value="mode"
          @update:model-value="emit('update:mode', $event)"
        />
        <button type="button" class="send-button" :disabled="loading" @click="submitQuestion">
          {{ loading ? '回答中...' : '发送' }}
        </button>
      </div>
    </div>
  </section>
</template>
