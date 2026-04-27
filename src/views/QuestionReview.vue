<template>
  <div class="question-review page">
    <div class="page-header">
      <button class="back-btn" @click="$router.push('/results')">
        <svg
          width="18"
          height="18"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
          stroke-linecap="round"
          stroke-linejoin="round"
        >
          <path d="M19 12H5M12 19l-7-7 7-7" />
        </svg>
        返回成绩
      </button>
      <span class="review-title">错题解析</span>
    </div>

    <div v-if="wrongQuestions.length === 0" class="empty-state glass-card">
      <p>🎉 全部正确，太棒了！</p>
      <button class="btn btn-primary" @click="handleHome">返回首页</button>
    </div>

    <div v-else class="review-list">
      <div v-for="(q, i) in wrongQuestions" :key="q.id" class="review-item glass-card fade-in">
        <div class="review-index">错题 {{ i + 1 }} / {{ wrongQuestions.length }}</div>
        <QuestionCard :question="q" :show-answer="true" :current-answer="getAnswerForQuestion(q)" />
      </div>

      <div class="review-footer">
        <button class="btn btn-primary" @click="handleHome">返回首页</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'
import { useExam } from '../composables/useExam'
import type { Question, UserAnswer } from '../types/question'
import QuestionCard from '../components/QuestionCard.vue'

const router = useRouter()
const { wrongQuestions, session, resetSession } = useExam()

function getAnswerForQuestion(q: Question): UserAnswer | null {
  if (!session.value) return null
  const idx = session.value.questions.findIndex((x) => x.id === q.id)
  return session.value.answers[idx] ?? null
}

function handleHome() {
  resetSession()
  router.push('/')
}
</script>

<style scoped>
.page-header {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.review-title {
  font-size: var(--text-lg);
  font-weight: var(--weight-semibold);
}

.review-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.review-item {
  padding: var(--space-4);
}

.review-item > :deep(.question-card) {
  padding: 0;
  margin-bottom: 0;
  box-shadow: none;
  background: none;
}

.review-index {
  font-size: var(--text-xs);
  color: var(--text-secondary);
  margin-bottom: var(--space-3);
}

.review-footer {
  text-align: center;
  padding: var(--space-4) 0;
}
</style>
