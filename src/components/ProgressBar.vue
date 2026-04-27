<template>
  <div class="progress-bar">
    <div class="progress-track">
      <div class="progress-fill" :style="{ width: `${percent}%` }"></div>
    </div>
    <span class="progress-text">{{ current }} / {{ total }}</span>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{ current: number; total: number }>()
const percent = computed(() => (props.total > 0 ? (props.current / props.total) * 100 : 0))
</script>

<style scoped>
.progress-bar {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  margin-bottom: var(--space-4);
}

.progress-track {
  flex: 1;
  height: 6px;
  background: var(--bg-surface-secondary);
  border-radius: var(--radius-full);
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, var(--c-primary), var(--c-primary-light));
  border-radius: var(--radius-full);
  transition: width 0.3s var(--ease-out);
}

.progress-text {
  font-size: var(--text-sm);
  color: var(--text-secondary);
  white-space: nowrap;
  flex-shrink: 0;
  min-width: 60px;
  text-align: right;
}
</style>
