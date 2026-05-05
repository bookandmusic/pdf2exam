<template>
  <div class="question-card glass-card fade-in">
    <div class="q-header">
      <span :class="['badge', question.type === 'multiple' ? 'badge-purple' : 'badge-primary']">
        {{ question.type === 'multiple' ? '多选' : '单选' }}
      </span>
      <DirectoryIndicator
        :topic="question.topic"
        :chapter="question.chapter"
        :section="question.section"
        class="q-dir"
      />
      <span v-if="question.difficulty" class="difficulty">{{ question.difficulty }}</span>
    </div>
    <div class="question-card-body" data-card-scroll>
      <div class="q-text">{{ question.question }}</div>

      <!-- 答题模式：使用父组件传入的选项插槽 -->
      <slot name="options" />

      <!-- 解析模式：显示只读选项，标记用户选择和正确答案 -->
      <div v-if="showAnswer && question.options" class="review-options">
        <div v-for="key in optionKeys" :key="key" :class="['review-option', getOptionClass(key)]">
          <span class="opt-icon">
            <svg v-if="mode === 'multiple'" width="20" height="20" viewBox="0 0 20 20" fill="none">
              <rect
                x="2"
                y="2"
                width="16"
                height="16"
                rx="4"
                stroke="currentColor"
                stroke-width="2"
              />
              <rect
                v-if="isUserSelected(key)"
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
              <circle v-if="isUserSelected(key)" cx="10" cy="10" r="5" fill="currentColor" />
            </svg>
          </span>
          <span class="opt-label">{{ key }}</span>
          <span class="opt-text">{{ question.options[key] }}</span>
        </div>
      </div>

      <div v-if="showAnswer" class="answer-section">
        <div class="result-row">
          <div :class="['result-badge', currentAnswer?.isCorrect ? 'correct' : 'wrong']">
            {{ currentAnswer?.isCorrect ? '✓ 正确' : '✗ 错误' }}
          </div>
        </div>
        <div class="user-answer" v-if="!currentAnswer?.isCorrect">
          <span class="label">你的答案：</span>
          <span class="value">{{ formatUserAnswer }}</span>
        </div>
        <div v-if="question.knowledge" class="knowledge">
          <span class="label">解析：</span>
          <p>{{ question.knowledge }}</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { Question, UserAnswer } from '../types/question'
import DirectoryIndicator from './DirectoryIndicator.vue'

const props = defineProps<{
  question: Question
  showAnswer: boolean
  currentAnswer?: UserAnswer | null
}>()

const optionKeys = computed(() => {
  if (!props.question.options) return []
  return Object.keys(props.question.options).sort()
})

const mode = computed(() => (props.question.type === 'multiple' ? 'multiple' : 'single'))

const userSelectedKeys = computed(() => {
  if (!props.currentAnswer) return []
  const sel = props.currentAnswer.selected
  return Array.isArray(sel) ? sel : [sel]
})

const correctKeys = computed(() => {
  if (props.question.type === 'multiple') {
    return props.question.answers || []
  }
  return [props.question.answer]
})

const formatUserAnswer = computed(() => {
  if (!props.currentAnswer) return '未作答'
  const sel = props.currentAnswer.selected
  const keys = Array.isArray(sel) ? sel : [sel]
  return keys.length > 0 ? keys.join(', ') : '未作答'
})

function isUserSelected(key: string): boolean {
  return userSelectedKeys.value.includes(key)
}

function isCorrect(key: string): boolean {
  return correctKeys.value.includes(key)
}

function getOptionClass(key: string): string {
  const userSelected = isUserSelected(key)
  const correct = isCorrect(key)

  if (correct) return 'review-correct'
  if (userSelected && !correct) return 'review-wrong'
  return 'review-dimmed'
}
</script>

<style scoped>
.question-card {
  padding: var(--space-5);
  margin-bottom: 0;
  box-shadow: var(--shadow-md);
}

.question-card-body {
  display: flex;
  flex-direction: column;
  gap: 0;
  min-height: 0;
}

.q-header {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-bottom: var(--space-4);
}

.q-dir {
  flex: 1;
  min-width: 0;
  padding: 0;
  overflow: hidden;
}
.q-dir :deep(.dir-indicator) {
  flex-wrap: nowrap;
  overflow: hidden;
  padding: 0;
}
.q-dir :deep(.dir-part) {
  overflow: hidden;
  flex-shrink: 1;
  min-width: 0;
}
.q-dir :deep(.dir-text) {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.q-dir :deep(.dir-part):last-child {
  flex-shrink: 1;
}
.q-dir :deep(.dir-sep) {
  flex-shrink: 0;
}

.difficulty {
  font-size: var(--text-xs);
  color: var(--text-tertiary);
  flex-shrink: 0;
}

.q-text {
  font-size: 16px;
  line-height: 1.7;
  margin-bottom: var(--space-4);
  white-space: pre-wrap;
}

/* 解析模式下的选项列表 */
.review-options {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  margin-bottom: var(--space-4);
}

.review-option {
  display: flex;
  align-items: flex-start;
  gap: var(--space-3);
  width: 100%;
  min-height: 44px;
  padding: 12px 14px;
  border-radius: var(--radius-md);
  border: 1px solid var(--border-default);
  background: rgba(255, 255, 255, 0.74);
  text-align: left;
  font-size: var(--text-base);
  line-height: 1.5;
}

.review-option.review-correct {
  background: rgba(52, 199, 89, 0.08);
  border-color: var(--c-success);
}

.review-option.review-correct .opt-icon {
  color: var(--c-success);
}

.review-option.review-wrong {
  background: rgba(255, 59, 48, 0.06);
  border-color: var(--c-error);
}

.review-option.review-wrong .opt-icon {
  color: var(--c-error);
}

.review-option.review-dimmed {
  opacity: 0.5;
}

.opt-icon {
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

/* 答案区域 */
.answer-section {
  margin-top: var(--space-5);
  padding-top: var(--space-4);
  border-top: 1px solid var(--border-default);
}

.result-row {
  margin-bottom: var(--space-3);
}

.label {
  font-weight: var(--weight-semibold);
  font-size: var(--text-sm);
}

.user-answer {
  font-size: var(--text-sm);
  margin-bottom: var(--space-2);
}

.user-answer .value {
  color: var(--c-error);
}

.correct-answer {
  font-size: var(--text-sm);
  margin-bottom: var(--space-3);
}

.correct-answer .value {
  color: var(--c-success);
}

.knowledge {
  font-size: var(--text-sm);
  color: var(--text-secondary);
  line-height: 1.7;
  padding: var(--space-3);
  background: var(--bg-surface-secondary);
  border-radius: var(--radius-sm);
}

.knowledge p {
  margin: var(--space-1) 0 0;
}
</style>
