<template>
  <div v-if="parts.length > 0" class="dir-indicator">
    <span v-for="(part, i) in parts" :key="i" class="dir-part">
      <span class="dir-text">{{ part }}</span>
      <span v-if="i < parts.length - 1" class="dir-sep">›</span>
    </span>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  topic?: string
  chapter?: string
  section?: string
}>()

const parts = computed(() => {
  const result: string[] = []
  if (props.topic) result.push(props.topic)
  if (props.chapter) result.push(props.chapter)
  if (props.section) result.push(props.section)
  return result
})
</script>

<style scoped>
.dir-indicator {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 2px;
  padding: 0 var(--space-1) var(--space-2);
  font-size: var(--text-xs);
  color: var(--text-tertiary);
  line-height: 1.4;
}
.dir-part {
  display: inline-flex;
  align-items: center;
  gap: 2px;
}
.dir-sep {
  color: var(--text-quaternary, var(--text-tertiary));
  opacity: 0.5;
  margin: 0 2px;
  font-size: var(--text-sm);
}
</style>
