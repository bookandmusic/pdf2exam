<template>
  <div class="option-group" :class="{ locked: isLocked }">
    <button
      v-for="key in optionKeys"
      :key="key"
      :class="['option-btn', getOptionClass(key)]"
      @click="handleSelect(key)"
      :disabled="isLocked && !showAnswer"
    >
      <span class="opt-radio">
        <svg v-if="mode === 'multiple'" width="20" height="20" viewBox="0 0 20 20" fill="none">
          <rect x="2" y="2" width="16" height="16" rx="4" stroke="currentColor" stroke-width="2" />
          <rect
            v-if="isSelected(key)"
            x="5"
            y="5"
            width="10"
            height="10"
            rx="2"
            fill="currentColor"
          />
        </svg>
        <svg v-else width="20" height="20" viewBox="0 0 20 20" fill="none">
          <circle cx="10" cy="10" r="8" stroke="currentColor" stroke-width="2" />
          <circle v-if="isSelected(key)" cx="10" cy="10" r="5" fill="currentColor" />
        </svg>
      </span>
      <span class="opt-label">{{ key }}</span>
      <span class="opt-text">{{ options[key] }}</span>
    </button>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  options: Record<string, string>
  selected: string | string[]
  showAnswer: boolean
  correctAnswer: string | string[]
  mode: 'single' | 'multiple'
  disabled?: boolean
}>()

const emit = defineEmits<{ select: [key: string] }>()

const optionKeys = computed(() => Object.keys(props.options).sort())

const isLocked = computed(() => props.disabled === true)

function isSelected(key: string): boolean {
  if (Array.isArray(props.selected)) return props.selected.includes(key)
  return props.selected === key
}

function isCorrect(key: string): boolean {
  if (Array.isArray(props.correctAnswer)) return props.correctAnswer.includes(key)
  return props.correctAnswer === key
}

function getOptionClass(key: string): string {
  if (props.showAnswer) {
    if (isCorrect(key)) return 'correct'
    if (isSelected(key) && !isCorrect(key)) return 'wrong'
    return 'dimmed'
  }
  return isSelected(key) ? 'selected' : ''
}

function handleSelect(key: string) {
  if (isLocked.value) return
  emit('select', key)
}
</script>

<style scoped>
.option-group {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.option-group.locked {
  pointer-events: none;
}

.option-btn {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  width: 100%;
  min-height: 52px;
  padding: 14px 16px;
  border-radius: var(--radius-md);
  border: 1px solid var(--border-default);
  background: var(--bg-surface);
  color: var(--text-primary);
  text-align: left;
  cursor: pointer;
  transition: all var(--duration-fast) var(--ease-out);
  font-size: var(--text-base);
  line-height: 1.5;
}

.option-btn:hover:not(:disabled) {
  border-color: var(--c-primary);
  background: var(--bg-surface-hover);
}

.option-btn:active {
  transform: scale(0.99);
}

/* Selected (before answer reveal) */
.option-btn.selected {
  background: rgba(99, 102, 241, 0.08);
  border-color: var(--c-primary);
}

.option-btn.selected .opt-radio {
  color: var(--c-primary);
}

/* Correct answer */
.option-btn.correct {
  background: rgba(52, 199, 89, 0.08);
  border-color: var(--c-success);
}

.option-btn.correct .opt-radio {
  color: var(--c-success);
}

/* Wrong answer */
.option-btn.wrong {
  background: rgba(255, 59, 48, 0.06);
  border-color: var(--c-error);
}

.option-btn.wrong .opt-radio {
  color: var(--c-error);
}

/* Not selected dimmed */
.option-btn.dimmed {
  opacity: 0.5;
}

/* Radio/checkbox icon */
.opt-radio {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  color: var(--text-tertiary);
  transition: color var(--duration-fast) var(--ease-out);
}

.opt-label {
  flex-shrink: 0;
  font-weight: var(--weight-medium);
  color: var(--text-secondary);
  min-width: 16px;
}

.opt-text {
  flex: 1;
  white-space: pre-wrap;
}
</style>
