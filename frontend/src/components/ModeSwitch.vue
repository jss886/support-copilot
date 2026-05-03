<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

import type { ChatMode } from '../types/chat'

interface ModeCard {
  key: ChatMode
  title: string
  icon: string
}

const props = defineProps<{
  modelValue: ChatMode
}>()

const emit = defineEmits<{
  (event: 'update:modelValue', value: ChatMode): void
}>()

const rootRef = ref<HTMLElement | null>(null)
const expanded = ref(false)

const modeCards: ModeCard[] = [
  {
    key: 'rag',
    title: 'RAG',
    icon: '◍',
  },
  {
    key: 'direct',
    title: 'Direct',
    icon: '⚡',
  },
  {
    key: 'auto',
    title: 'Auto',
    icon: '✦',
  },
]

// 作用：把用户点击的模式同步给父组件，统一驱动当前聊天策略。
function selectMode(mode: ChatMode): void {
  emit('update:modelValue', mode)
  expanded.value = false
}

// 作用：当前只把非激活模式放进弹层，避免底部同时出现三个按钮。
const popupModes = computed(() => modeCards.filter((mode) => mode.key !== props.modelValue))

// 作用：点击控件外部时自动收起弹层，避免模式菜单一直悬浮。
function handleDocumentClick(event: MouseEvent): void {
  if (!rootRef.value) {
    return
  }
  const target = event.target
  if (target instanceof Node && !rootRef.value.contains(target)) {
    expanded.value = false
  }
}

onMounted(() => {
  document.addEventListener('click', handleDocumentClick)
})

onBeforeUnmount(() => {
  document.removeEventListener('click', handleDocumentClick)
})
</script>

<template>
  <div ref="rootRef" class="mode-switch-inline">
    <button
      type="button"
      class="mode-pill is-active"
      @click="expanded = !expanded"
    >
      <span class="mode-pill-icon">{{ modeCards.find((mode) => mode.key === props.modelValue)?.icon }}</span>
      <span>{{ modeCards.find((mode) => mode.key === props.modelValue)?.title }}</span>
      <span class="mode-pill-caret">{{ expanded ? '▴' : '▾' }}</span>
    </button>
    <div v-if="expanded" class="mode-switch-popup">
      <button
        v-for="mode in popupModes"
        :key="mode.key"
        type="button"
        class="mode-popup-item"
        @click="selectMode(mode.key)"
      >
        <span class="mode-pill-icon">{{ mode.icon }}</span>
        <span>{{ mode.title }}</span>
      </button>
    </div>
  </div>
</template>
