<template>
  <div class="exam-results page">
    <div class="page-header">
      <button class="back-btn" @click="handleHome">
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
        返回
      </button>
    </div>

    <ScoreSummary
      :score="score"
      :correct-count="correctCount"
      :wrong-count="wrongCount"
      @review="scrollToReview"
      @home="handleHome"
    />

    <section v-if="wrongQuestions.length > 0" ref="reviewSection" class="results-review">
      <div class="results-review-header">
        <h2>错题解析</h2>
        <button class="btn btn-ghost" @click="$router.push('/review')">单独查看</button>
      </div>

      <div class="review-list">
        <div v-for="(q, i) in wrongQuestions" :key="q.id" class="review-item glass-card fade-in">
          <div class="review-index">错题 {{ i + 1 }} / {{ wrongQuestions.length }}</div>
          <QuestionCard
            :question="q"
            :show-answer="true"
            :current-answer="getAnswerForQuestion(q)"
          />
        </div>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useExam } from '../composables/useExam'
import type { Question, UserAnswer } from '../types/question'
import QuestionCard from '../components/QuestionCard.vue'
import ScoreSummary from '../components/ScoreSummary.vue'

const router = useRouter()
const reviewSection = ref<HTMLElement | null>(null)
const { score, correctCount, wrongCount, wrongQuestions, session, resetSession } = useExam()

function getAnswerForQuestion(q: Question): UserAnswer | null {
  if (!session.value) return null
  const idx = session.value.questions.findIndex((x) => x.id === q.id)
  return session.value.answers[idx] ?? null
}

function scrollToReview() {
  reviewSection.value?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

function handleHome() {
  resetSession()
  router.push('/')
}
</script>

<style scoped>
.results-review {
  margin-top: var(--space-6);
}

.results-review-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  margin-bottom: var(--space-4);
}

.results-review-header h2 {
  margin: 0;
  font-size: var(--text-xl);
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
  margin-bottom: var(--space-3);
  font-size: var(--text-xs);
  color: var(--text-secondary);
}

@media (max-width: 640px) {
  .results-review-header {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
