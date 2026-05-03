<script setup lang="ts">
import { computed } from 'vue'
import { RouterLink, useRoute } from 'vue-router'

interface NavItem {
  label: string
  to: string
  icon: string
}

const route = useRoute()
const navItems: NavItem[] = [
  { label: '对话', to: '/conversation', icon: '◌' },
  { label: '知识库', to: '/knowledge', icon: '◍' },
  { label: '任务记忆', to: '/memory', icon: '⌘' },
  { label: '智能体', to: '/agents', icon: '✦' },
  { label: '设置', to: '/settings', icon: '⚙' },
]

// 作用：根据当前路由高亮左侧导航项，保持工作台结构稳定。
function isActive(path: string): boolean {
  return route.path === path
}

const adminLabel = computed(() => 'Admin')
</script>

<template>
  <aside class="sidebar-shell">
    <div class="sidebar-brand">
      <div class="sidebar-brand-mark">
        <span class="brand-orb brand-orb-left"></span>
        <span class="brand-orb brand-orb-right"></span>
      </div>
      <div>
        <div class="sidebar-brand-title">研发知识助手</div>
        <div class="sidebar-brand-subtitle">Support Copilot</div>
      </div>
    </div>

    <button class="new-chat-button" type="button">+ 新建对话</button>

    <nav class="sidebar-nav">
      <RouterLink
        v-for="item in navItems"
        :key="item.to"
        :to="item.to"
        class="sidebar-nav-item"
        :class="{ 'is-active': isActive(item.to) }"
      >
        <span class="sidebar-nav-icon">{{ item.icon }}</span>
        <span>{{ item.label }}</span>
      </RouterLink>
    </nav>

    <div class="sidebar-admin">
      <div class="sidebar-admin-avatar">A</div>
      <div>
        <div class="sidebar-admin-name">{{ adminLabel }}</div>
        <div class="sidebar-admin-status">统一演示账号</div>
      </div>
    </div>
  </aside>
</template>
