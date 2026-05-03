<script setup lang="ts">
import SidebarNav from '../components/SidebarNav.vue'

defineProps<{
  title: string
  description: string
}>()
</script>

<template>
  <div class="app-shell">
    <SidebarNav />
    <main class="page-shell">
      <section class="placeholder-panel">
        <div class="placeholder-kicker">页面占位</div>
        <h1>{{ title }}</h1>
        <p>{{ description }}</p>
      </section>
    </main>
  </div>
</template>
