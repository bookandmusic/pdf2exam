<template>
  <div class="sequential-practice page">
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
      <QuestionCard :question="currentQuestion" :showAnswer="false" :current-answer="currentAnswer">
        <template #options>
          <OptionSelector
            :options="currentQuestion.options"
            :selected="selected"
            :show-answer="showAnsweredState"
            :correct-answer="
              currentQuestion.type === 'multiple'
                ? currentQuestion.answers || []
                : currentQuestion.answer
            "
            :mode="currentQuestion.type || 'single'"
            :disabled="showAnsweredState"
            @select="handleSelect"
          />
        </template>
      </QuestionCard>

      <div class="nav-bar">
        <button class="btn btn-ghost" @click="handlePrev" :disabled="isFirst">上一题</button>
        <button :class="analysisButtonClass" @click="showAnalysis" :disabled="!showAnsweredState">
          解析
        </button>
        <button v-if="isLast && showAnsweredState" class="btn btn-success" @click="handleFinish">
          完成练习
        </button>
        <button v-else class="btn btn-primary" @click="handleNext">
          {{ nextButtonText }}
        </button>
      </div>
    </div>

    <div
      v-if="analysisVisible && currentQuestion && showAnsweredState"
      class="modal-overlay"
      @click.self="closeAnalysis"
    >
      <div class="modal analysis-modal">
        <button class="modal-close" @click="closeAnalysis" aria-label="关闭解析">×</button>
        <div class="analysis-header">
          <div :class="['result-badge', currentAnswer?.isCorrect ? 'correct' : 'wrong']">
            {{ currentAnswer?.isCorrect ? '✓ 正确' : '✗ 错误' }}
          </div>
        </div>
        <div class="analysis-block">
          <span class="analysis-label">正确答案</span>
          <div class="analysis-value">{{ formattedAnswer }}</div>
        </div>
        <div v-if="currentQuestion.knowledge" class="analysis-block">
          <span class="analysis-label">解析</span>
          <p class="analysis-text">{{ currentQuestion.knowledge }}</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onBeforeUnmount, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useQuestionBank } from '../stores/questionBank'
import { useWrongQuestions } from '../stores/wrongQuestions'
import { usePractice } from '../composables/usePractice'
import ProgressBar from '../components/ProgressBar.vue'
import QuestionCard from '../components/QuestionCard.vue'
import OptionSelector from '../components/OptionSelector.vue'
import type { UserAnswer } from '../types/question'

const router = useRouter()
const {
  filteredQuestions: questions,
  subjects,
  currentSubjectIds,
  currentChapterIds,
} = useQuestionBank()
const { add: addWrong, remove: removeWrong, resetCorrect } = useWrongQuestions()
const {
  session,
  currentQuestion,
  currentAnswer,
  currentIndex,
  selected,
  showAnsweredState,
  isFirst,
  isLast,
  nextButtonText,
  totalQuestions,
  handleSelect,
  handleConfirm,
  next,
  prev,
  resetCurrentAnswer,
  resetSession,
  endSession,
  startSession,
} = usePractice()

const STORAGE_KEY = 'pdf2exam_sequential_state'
const analysisVisible = ref(false)
const retryQuestionIds = ref<string[]>([])

const formattedAnswer = computed(() => {
  const question = currentQuestion.value
  if (!question) return ''
  return (question.type === 'multiple' ? question.answers || [] : [question.answer]).join(', ')
})

const analysisButtonClass = computed(() => [
  'btn',
  'analysis-btn',
  showAnsweredState.value
    ? currentAnswer.value?.isCorrect
      ? 'analysis-btn-correct'
      : 'analysis-btn-wrong'
    : 'analysis-btn-pending',
])

watch(currentIndex, () => {
  analysisVisible.value = false
})

watch(
  session,
  (value) => {
    if (!value || value.mode !== 'sequential') return
    saveProgress()
  },
  { deep: true }
)

onMounted(() => {
  if (questions.value.length === 0) {
    router.push('/')
    return
  }
  resetSession()
  restoreProgress()
})

onBeforeUnmount(() => {
  saveProgress()
})

function saveProgress() {
  if (!shouldPersistProgress.value) {
    clearProgress()
    return
  }
  if (session.value) {
    localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({
        questionIds: session.value.questions.map((question) => question.id),
        answers: session.value.answers,
        currentIndex: session.value.currentIndex,
        retryQuestionIds: retryQuestionIds.value,
      })
    )
  }
}

function clearProgress() {
  localStorage.removeItem(STORAGE_KEY)
  retryQuestionIds.value = []
}

function restoreProgress() {
  if (!shouldPersistProgress.value) {
    clearProgress()
    startSession(questions.value, 0)
    return
  }

  const saved = localStorage.getItem(STORAGE_KEY)
  if (!saved) {
    startSession(questions.value, 0)
    return
  }

  try {
    const parsed = JSON.parse(saved) as {
      questionIds?: string[]
      answers?: Array<UserAnswer | null>
      currentIndex?: number
      retryQuestionIds?: string[]
    }
    const questionIds = questions.value.map((question) => question.id)
    const matchesCurrentQuestions =
      Array.isArray(parsed.questionIds) &&
      parsed.questionIds.length === questionIds.length &&
      parsed.questionIds.every((id, index) => id === questionIds[index])

    if (!matchesCurrentQuestions) {
      startSession(questions.value, 0)
      return
    }

    const answers = Array.isArray(parsed.answers) ? parsed.answers : undefined
    const startIndex =
      typeof parsed.currentIndex === 'number'
        ? Math.min(Math.max(parsed.currentIndex, 0), questions.value.length - 1)
        : 0

    retryQuestionIds.value = Array.isArray(parsed.retryQuestionIds) ? parsed.retryQuestionIds : []
    startSession(questions.value, startIndex, answers)
  } catch {
    startSession(questions.value, 0)
  }
}

const shouldPersistProgress = computed(() => {
  if (currentChapterIds.value.length > 0) return false
  const totalSubjects = subjects.value.length
  if (totalSubjects === 0) return true

  const selectedCount = currentSubjectIds.value.length
  return selectedCount === 0 || selectedCount === 1 || selectedCount === totalSubjects
})

function closeAnalysis() {
  analysisVisible.value = false
}

function showAnalysis() {
  if (!showAnsweredState.value) return
  analysisVisible.value = true
}

function syncWrongQuestionState() {
  if (!currentQuestion.value || !currentAnswer.value) return
  const id = currentQuestion.value.id
  const isRetry = retryQuestionIds.value.includes(id)

  if (isRetry) {
    if (!currentAnswer.value.isCorrect) {
      addWrong(id)
      resetCorrect(id)
    }
    retryQuestionIds.value = retryQuestionIds.value.filter((questionId) => questionId !== id)
    return
  }

  if (currentAnswer.value.isCorrect) {
    removeWrong(id)
    return
  }
  addWrong(id)
  resetCorrect(id)
}

function confirmAndMaybeShowAnalysis() {
  const confirmed = handleConfirm()
  if (!confirmed) return false
  syncWrongQuestionState()
  if (!currentAnswer.value?.isCorrect) {
    analysisVisible.value = true
  }
  return true
}

function handleNext() {
  if (!showAnsweredState.value) {
    confirmAndMaybeShowAnalysis()
    return
  }
  closeAnalysis()
  if (!isLast.value) {
    next()
  }
}

function handlePrev() {
  closeAnalysis()
  const targetIndex = currentIndex.value - 1
  if (targetIndex < 0) return

  prev()
  const targetQuestionId = session.value?.questions[targetIndex]?.id
  if (targetQuestionId && !retryQuestionIds.value.includes(targetQuestionId)) {
    retryQuestionIds.value.push(targetQuestionId)
  }
  resetCurrentAnswer()
}

function handleFinish() {
  if (!showAnsweredState.value) {
    const confirmed = confirmAndMaybeShowAnalysis()
    if (!confirmed) return
    if (!currentAnswer.value?.isCorrect) return
  }
  closeAnalysis()
  clearProgress()
  endSession()
  router.push('/')
}
</script>

<style scoped>
.nav-bar {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.modal-overlay {
  position: fixed;
  inset: 0;
  z-index: 100;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--space-6);
  background: rgba(0, 0, 0, 0.42);
  backdrop-filter: blur(4px);
  -webkit-backdrop-filter: blur(4px);
}

.modal {
  position: relative;
  width: min(100%, 420px);
  background: var(--bg-surface);
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-lg);
  padding: var(--space-6);
}

.analysis-modal {
  animation: fadeIn var(--duration-normal) var(--ease-out);
}

.modal-close {
  position: absolute;
  top: var(--space-3);
  right: var(--space-3);
  width: 32px;
  height: 32px;
  border: none;
  border-radius: var(--radius-full);
  background: var(--bg-surface-secondary);
  color: var(--text-secondary);
  font-size: 22px;
  line-height: 1;
  cursor: pointer;
}

.analysis-header {
  margin-bottom: var(--space-4);
}

.analysis-block + .analysis-block {
  margin-top: var(--space-4);
}

.analysis-label {
  display: block;
  margin-bottom: var(--space-2);
  font-size: var(--text-sm);
  font-weight: var(--weight-semibold);
  color: var(--text-secondary);
}

.analysis-value {
  font-size: var(--text-lg);
  font-weight: var(--weight-semibold);
  color: var(--c-success);
}

.analysis-text {
  margin: 0;
  padding: var(--space-3);
  border-radius: var(--radius-md);
  background: var(--bg-surface-secondary);
  color: var(--text-secondary);
  line-height: 1.7;
  white-space: pre-wrap;
}

.analysis-btn {
  min-width: 96px;
}

.analysis-btn-pending {
  background: var(--bg-surface-secondary);
  border: 1px solid var(--border-default);
  color: var(--text-tertiary);
}

.analysis-btn-pending:disabled {
  opacity: 1;
}

.analysis-btn-correct {
  background: rgba(52, 199, 89, 0.12);
  border: 1px solid var(--c-success);
  color: var(--c-success);
}

.analysis-btn-wrong {
  background: rgba(255, 59, 48, 0.12);
  border: 1px solid var(--c-error);
  color: var(--c-error);
}
</style>
