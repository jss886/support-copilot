<script setup lang="ts">
import type { RetrievalItem } from '../types/chat'

defineProps<{
  items: RetrievalItem[]
}>()

// 作用：把过长的来源路径压缩成更适合卡片展示的短标签。
function formatSource(source: string): string {
  const parts = source.split(/[\\/]/).filter(Boolean)
  return parts.slice(-2).join(' / ') || source
}

// 作用：把检索分数转成更直观的百分比，方便演示时快速判断证据强弱。
function formatScore(score: number): string {
  return `${Math.max(0, Math.min(100, Math.round(score * 100)))}%`
}
</script>

<template>
  <div v-if="items.length" class="source-list">
    <div class="source-list-header">相关文档</div>
    <article v-for="(item, index) in items" :key="`${item.source}-${index}`" class="source-item">
      <div class="source-item-topline">
        <span class="source-item-name">{{ formatSource(item.source) }}</span>
        <span class="source-item-score">相关度 {{ formatScore(item.score) }}</span>
      </div>
      <p class="source-item-text">{{ item.text }}</p>
    </article>
  </div>
</template>
