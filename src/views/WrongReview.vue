<template>
  <div class="wrong-review page">
    <div class="page-header">
      <button class="back-btn" @click="$router.push('/')">
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

    <ProgressBar :current="currentIndex + 1" :total="totalQuestions" />

    <div v-if="currentQuestion" class="fade-in">
      <QuestionCard
        :question="currentQuestion"
        :showAnswer="isAnswered || pendingRemove"
        :current-answer="currentAnswer"
      >
        <template #options>
          <OptionSelector
            :options="currentQuestion.options"
            :selected="selected"
            :show-answer="isAnswered"
            :correct-answer="
              currentQuestion.type === 'multiple'
                ? currentQuestion.answers || []
                : currentQuestion.answer
            "
            :mode="currentQuestion.type || 'single'"
            :disabled="isAnswered"
            @select="handleSelect"
          />
        </template>
      </QuestionCard>

      <div v-if="pendingRemove" class="remove-prompt glass-card">
        <p>回答正确！是否将此题从错题集移除？</p>
        <div class="remove-actions">
          <button class="btn btn-primary" @click="handleRemoveAndNext">移除并继续</button>
          <button class="btn btn-ghost" @click="handleKeepAndNext">保留此题</button>
        </div>
      </div>

      <div class="nav-bar">
        <button class="btn btn-ghost" @click="handlePrev" :disabled="isFirst">上一题</button>
        <span class="nav-info">
          <span v-if="isAnswered" :class="currentAnswer?.isCorrect ? 'correct-text' : 'wrong-text'">
            {{ currentAnswer?.isCorrect ? '✓ 正确' : '✗ 错误' }}
          </span>
          <span v-else>未作答</span>
        </span>
        <button v-if="isLast && isAnswered" class="btn btn-success" @click="handleFinish">
          {{ nextButtonText }}
        </button>
        <button v-else class="btn btn-primary" @click="handleNext">
          {{ nextButtonText }}
        </button>
      </div>
    </div>

    <div v-else class="empty-state glass-card">
      <p>🎉 错题集为空，继续保持！</p>
      <button class="btn btn-primary" @click="$router.push('/')">返回首页</button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useQuestionBank } from '../stores/questionBank'
import { useWrongQuestions } from '../stores/wrongQuestions'
import { usePractice } from '../composables/usePractice'
import ProgressBar from '../components/ProgressBar.vue'
import QuestionCard from '../components/QuestionCard.vue'
import OptionSelector from '../components/OptionSelector.vue'

const router = useRouter()
const { filteredQuestions: questions } = useQuestionBank()
const { wrongIds, remove: removeWrong, recordCorrect } = useWrongQuestions()
const {
  session,
  currentQuestion,
  currentAnswer,
  currentIndex,
  selected,
  isAnswered,
  isFirst,
  isLast,
  nextButtonText,
  totalQuestions,
  handleSelect,
  handleConfirm,
  handlePrev,
  resetSession,
  endSession,
} = usePractice()

const pendingRemove = ref(false)

const wrongQuestions = computed(() => {
  const ids = new Set(wrongIds.value.map((e) => e.id))
  return questions.value.filter((q) => ids.has(q.id))
})

onMounted(() => {
  if (questions.value.length === 0) {
    router.push('/')
    return
  }
  resetSession()
  if (wrongQuestions.value.length === 0) return
  const saved = sessionStorage.getItem('wrong_review_index')
  const startIndex = saved ? parseInt(saved, 10) : 0
  startWrongSession(Math.min(startIndex, wrongQuestions.value.length - 1))
})

function startWrongSession(startIndex: number) {
  const qs = wrongQuestions.value
  const n = qs.length
  session.value = {
    mode: 'sequential',
    questions: qs,
    answers: new Array(n).fill(null),
    currentIndex: startIndex,
    isComplete: false,
    pointsPerQuestion: 0,
  }
}

function handleNext() {
  if (pendingRemove.value) {
    pendingRemove.value = false
    next()
    return
  }
  if (!isAnswered.value) {
    const ok = handleConfirm()
    if (!ok) return
    if (currentAnswer.value?.isCorrect && currentQuestion.value) {
      recordCorrect(currentQuestion.value.id)
      pendingRemove.value = true
    }
  } else {
    next()
  }
}

function next() {
  if (!session.value) return
  if (session.value.currentIndex < session.value.questions.length - 1) {
    session.value.currentIndex++
    pendingRemove.value = false
  }
}

function handleRemoveAndNext() {
  if (!currentQuestion.value) return
  pendingRemove.value = false
  removeWrong(currentQuestion.value.id)
  if (session.value) {
    const idx = session.value.currentIndex
    const remaining = wrongQuestions.value.length
    if (remaining === 0) {
      endSession()
      router.push('/')
      return
    }
    startWrongSession(idx >= remaining ? Math.max(0, remaining - 1) : idx)
  }
}

function handleKeepAndNext() {
  pendingRemove.value = false
}

function handleFinish() {
  if (!isAnswered.value) {
    const ok = handleConfirm()
    if (!ok) return
    if (currentAnswer.value?.isCorrect && currentQuestion.value) {
      recordCorrect(currentQuestion.value.id)
      pendingRemove.value = true
    }
    return
  }
  endSession()
  sessionStorage.removeItem('wrong_review_index')
  router.push('/')
}
</script>

<style scoped>
.remove-prompt {
  padding: var(--space-5);
  margin-top: var(--space-4);
  text-align: center;
}

.remove-prompt p {
  margin: 0 0 var(--space-4);
  color: var(--c-success);
  font-weight: var(--weight-semibold);
}

.remove-actions {
  display: flex;
  gap: var(--space-3);
  justify-content: center;
}

.correct-text {
  color: var(--c-success);
  font-weight: var(--weight-semibold);
}
.wrong-text {
  color: var(--c-error);
  font-weight: var(--weight-semibold);
}
</style>
