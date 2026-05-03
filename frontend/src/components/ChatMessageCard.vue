<script setup lang="ts">
import SourceList from './SourceList.vue'
import type { ChatMessage } from '../types/chat'

defineProps<{
  message: ChatMessage
}>()
</script>

<template>
  <article class="chat-card" :class="[`is-${message.role}`]">
    <div class="chat-card-body">
      <div v-if="message.mode" class="chat-card-meta">
        <span class="chat-card-badge">{{ message.mode.toUpperCase() }}</span>
      </div>
      <div class="chat-card-text">{{ message.text }}</div>
      <SourceList v-if="message.sources?.length" :items="message.sources" />
    </div>
  </article>
</template>
