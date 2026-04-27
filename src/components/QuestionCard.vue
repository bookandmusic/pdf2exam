<template>
  <div class="question-card glass-card fade-in">
    <div class="q-header">
      <span :class="['badge', question.type === 'multiple' ? 'badge-purple' : 'badge-primary']">
        {{ question.type === 'multiple' ? '多选' : '单选' }}
      </span>
      <span v-if="question.difficulty" class="difficulty">{{ question.difficulty }}</span>
    </div>
    <div class="q-text">{{ question.question }}</div>
    <slot name="options" />

    <div v-if="showAnswer" class="answer-section">
      <div class="result-row">
        <div :class="['result-badge', currentAnswer?.isCorrect ? 'correct' : 'wrong']">
          {{ currentAnswer?.isCorrect ? '✓ 正确' : '✗ 错误' }}
        </div>
      </div>
      <div class="correct-answer">
        <span class="label">正确答案：</span>
        <span class="value">{{
          formatAnswer(question.type === 'multiple' ? question.answers || [] : [question.answer])
        }}</span>
      </div>
      <div v-if="question.knowledge" class="knowledge">
        <span class="label">解析：</span>
        <p>{{ question.knowledge }}</p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { Question, UserAnswer } from '../types/question'

defineProps<{
  question: Question
  showAnswer: boolean
  currentAnswer?: UserAnswer | null
}>()

function formatAnswer(answers: string[]): string {
  return answers.join(', ')
}
</script>

<style scoped>
.question-card {
  padding: var(--space-5);
  margin-bottom: var(--space-4);
}

.q-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--space-4);
}

.difficulty {
  font-size: var(--text-xs);
  color: var(--text-tertiary);
}

.q-text {
  font-size: var(--text-base);
  line-height: 1.7;
  margin-bottom: var(--space-4);
  white-space: pre-wrap;
}

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
