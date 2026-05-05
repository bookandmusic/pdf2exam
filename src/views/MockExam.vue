<template>
  <div class="mock-exam-page mobile-shell">
    <div class="sticky-header mobile-topbar">
      <div class="header-content mobile-topbar-content">
        <button class="back-btn" @click="handleBack">
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
          退出
        </button>
        <div :class="['exam-timer', { urgent: remaining <= 60 }]">
          <svg
            width="16"
            height="16"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            <circle cx="12" cy="12" r="10" />
            <polyline points="12 6 12 12 16 14" />
          </svg>
          {{ formattedTime }}
        </div>
        <button class="submit-btn" @click="confirmSubmit = true">交卷</button>
      </div>
      <ProgressBar :current="currentIndex + 1" :total="totalQuestions" />
    </div>

    <div class="exam-main">
      <div class="scrollable-content exam-question-scroll">
        <div class="content-inner mobile-content">
          <div v-if="currentQuestion" class="fade-in">
            <QuestionCard
              :question="currentQuestion"
              :show-answer="false"
              :current-answer="currentAnswer"
            >
              <template #options>
                <OptionSelector
                  :options="currentQuestion.options"
                  :selected="selected"
                  :show-answer="false"
                  :correct-answer="
                    currentQuestion.type === 'multiple'
                      ? currentQuestion.answers || []
                      : currentQuestion.answer
                  "
                  :mode="currentQuestion.type || 'single'"
                  :disabled="false"
                  @select="handleSelect"
                />
              </template>
            </QuestionCard>
          </div>
        </div>
      </div>

      <div v-if="currentQuestion" class="mobile-bottom-bar exam-bottom-bar">
        <div class="mobile-bottom-panel">
          <div class="progress-dots exam-progress-dots">
            <span
              v-for="(q, i) in sessionQuestions"
              :key="q.id"
              :class="['dot', { answered: answers[i], current: i === currentIndex }]"
              @click="handleGoTo(i)"
            ></span>
          </div>

          <div class="exam-nav-bar mobile-actions-grid mobile-actions-split">
            <button class="btn btn-ghost" @click="handlePrev" :disabled="isFirst">上一题</button>
            <span class="nav-info mobile-progress-meta"
              >第 {{ currentIndex + 1 }} / {{ totalQuestions }} 题</span
            >
            <button v-if="!isLast" class="btn btn-primary" @click="next">下一题</button>
            <button v-else class="btn btn-primary" @click="next" disabled>最后一题</button>
          </div>
        </div>
      </div>
    </div>

    <!-- Confirm submit modal -->
    <div v-if="confirmSubmit" class="modal-overlay" @click.self="confirmSubmit = false">
      <div class="modal">
        <div class="modal-icon-wrap">
          <svg
            width="28"
            height="28"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            <circle cx="12" cy="12" r="10" />
            <path d="M12 8v4M12 16h.01" />
          </svg>
        </div>
        <p class="modal-text">
          共有 <strong>{{ unanswerdCount }}</strong> 道题未作答，未答的题目将视为错误。
        </p>
        <p class="modal-text muted">确定要交卷吗？</p>
        <div class="modal-actions">
          <button class="btn-row btn-row-cancel" @click="confirmSubmit = false">继续答题</button>
          <button class="btn-row btn-row-submit" @click="doSubmit">确认交卷</button>
        </div>
      </div>
    </div>

    <div v-if="confirmExit" class="modal-overlay" @click.self="confirmExit = false">
      <div class="modal">
        <div class="modal-icon-wrap">
          <svg
            width="28"
            height="28"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            <circle cx="12" cy="12" r="10" />
            <path d="M12 8v4M12 16h.01" />
          </svg>
        </div>
        <p class="modal-text">确定要退出考试吗？</p>
        <p class="modal-text muted">当前答题进度将不会保留。</p>
        <div class="modal-actions">
          <button class="btn-row btn-row-cancel" @click="confirmExit = false">继续答题</button>
          <button class="btn-row btn-row-submit" @click="doExit">确认退出</button>
        </div>
      </div>
    </div>

    <!-- Time up modal -->
    <div v-if="showTimeUp" class="modal-overlay">
      <div class="modal">
        <div class="modal-icon-wrap timeup-icon">
          <svg
            width="28"
            height="28"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            <circle cx="12" cy="12" r="10" />
            <polyline points="12 6 12 12 16 14" />
          </svg>
        </div>
        <p class="modal-text">考试时间到，已自动交卷。</p>
        <p class="modal-text muted">共 {{ totalQuestions }} 道题，{{ answeredCount }} 道已作答。</p>
        <div class="modal-actions">
          <button class="btn-row btn-row-submit" @click="goToResults">查看成绩</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useQuestionBank } from '../stores/questionBank'
import { useWrongQuestions } from '../stores/wrongQuestions'
import { usePractice } from '../composables/usePractice'
import ProgressBar from '../components/ProgressBar.vue'
import QuestionCard from '../components/QuestionCard.vue'
import OptionSelector from '../components/OptionSelector.vue'

const router = useRouter()
const { filteredQuestions: questions } = useQuestionBank()
const { wrongIds } = useWrongQuestions()
const {
  session,
  currentQuestion,
  currentAnswer,
  currentIndex,
  selected,
  isFirst,
  isLast,
  totalQuestions,
  next,
  handlePrev,
  handleGoTo,
  resetSession,
  endSession,
  submitAnswer,
} = usePractice()

const answers = computed(() => session.value?.answers ?? [])
const sessionQuestions = computed(() => session.value?.questions ?? [])

const answeredCount = computed(() => session.value?.answers.filter((a) => a !== null).length ?? 0)
const unanswerdCount = computed(() => totalQuestions.value - answeredCount.value)

// ─── Timer ──────────────────────────────────────────────
const MOCK_DURATION_KEY = 'mock_exam_duration'
const remaining = ref(0)
let timerInterval: ReturnType<typeof setInterval> | null = null
const confirmSubmit = ref(false)
const confirmExit = ref(false)
const showTimeUp = ref(false)

const formattedTime = computed(() => {
  const m = Math.floor(remaining.value / 60)
  const s = remaining.value % 60
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
})

function getDuration(): number {
  try {
    const saved = localStorage.getItem(MOCK_DURATION_KEY)
    return saved ? Math.max(1, parseInt(saved, 10) || 60) : 60
  } catch {
    return 60
  }
}

function startTimer() {
  remaining.value = getDuration() * 60
  timerInterval = setInterval(() => {
    if (remaining.value <= 0) {
      clearTimer()
      autoSubmit()
      return
    }
    remaining.value--
  }, 1000)
}

function clearTimer() {
  if (timerInterval) {
    clearInterval(timerInterval)
    timerInterval = null
  }
}

// ─── Exam Logic ─────────────────────────────────────────

function shuffle<T>(arr: T[]): T[] {
  const a = [...arr]
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1))
    ;[a[i], a[j]] = [a[j], a[i]]
  }
  return a
}

function startMockExam() {
  const wrongIdSet = new Set(wrongIds.value.map((e) => e.id))
  const wrongQs = questions.value.filter((q) => wrongIdSet.has(q.id))
  const normalQs = questions.value.filter((q) => !wrongIdSet.has(q.id))

  const shuffledWrong = shuffle(wrongQs)
  const shuffledNormal = shuffle(normalQs)

  const MAX = 100
  const picked =
    shuffledWrong.length >= MAX
      ? shuffledWrong.slice(0, MAX)
      : [...shuffledWrong, ...shuffledNormal.slice(0, MAX - shuffledWrong.length)]

  const n = picked.length
  session.value = {
    mode: 'mock',
    questions: picked,
    answers: new Array(n).fill(null),
    currentIndex: 0,
    isComplete: false,
    pointsPerQuestion: n > 0 ? 100 / n : 0,
  }
}

function fillUnanswered() {
  const s = session.value
  if (!s) return
  s.answers = s.answers.map((a, i) => {
    if (a) return a
    const q = s.questions[i]
    return {
      questionId: q.id,
      selected: q.type === 'multiple' ? [] : '',
      correct: q.type === 'multiple' ? q.answers || [] : q.answer,
      isCorrect: false,
    }
  })
}

function doSubmit() {
  fillUnanswered()
  endSession()
  clearTimer()
  confirmSubmit.value = false
  router.push('/results')
}

function goToResults() {
  showTimeUp.value = false
  router.push('/results')
}

function autoSubmit() {
  fillUnanswered()
  endSession()
  clearTimer()
  showTimeUp.value = true
}

function doExit() {
  confirmExit.value = false
  clearTimer()
  resetSession()
  router.push('/')
}

function handleBack() {
  if (answeredCount.value > 0) {
    confirmExit.value = true
  } else {
    doExit()
  }
}

function handleSelect(key: string) {
  if (!session.value || !currentQuestion.value) return
  const type = currentQuestion.value.type || 'single'
  const answer = session.value.answers[session.value.currentIndex]
  const current = answer?.selected ?? (type === 'multiple' ? [] : '')

  if (type === 'multiple') {
    const arr = Array.isArray(current) ? [...current] : []
    const idx = arr.indexOf(key)
    if (idx >= 0) arr.splice(idx, 1)
    else arr.push(key)
    submitAnswer(arr)
  } else {
    submitAnswer(key)
  }
}

onMounted(() => {
  if (questions.value.length === 0) {
    router.push('/')
    return
  }
  resetSession()
  startMockExam()
  startTimer()
})

onUnmounted(() => {
  clearTimer()
})
</script>

<style scoped>
/* 根容器 */
.mock-exam-page {
  height: 100vh;
  height: 100dvh;
  overflow: hidden;
  background: transparent;
}

.exam-main {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.sticky-header {
  flex-shrink: 0;
  box-shadow: none;
}

.header-content {
  min-height: 48px;
}

.back-btn {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  background: none;
  border: none;
  color: var(--c-primary);
  font-size: var(--text-base);
  cursor: pointer;
  padding: var(--space-2) 0;
  min-height: 44px;
  transition: opacity var(--duration-fast) var(--ease-out);
}

.back-btn:hover {
  opacity: 0.7;
}

/* Timer */
.exam-timer {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: 10px 14px;
  border-radius: var(--radius-full);
  background: rgba(255, 255, 255, 0.55);
  border: 1px solid rgba(255, 255, 255, 0.7);
  font-size: var(--text-base);
  font-weight: var(--weight-semibold);
  color: var(--text-primary);
  font-variant-numeric: tabular-nums;
  letter-spacing: 0.4px;
}

.exam-timer svg {
  color: var(--c-primary);
}

.exam-timer.urgent {
  color: var(--c-error);
  animation: timerPulse 1s ease-in-out infinite;
}

.exam-timer.urgent svg {
  color: var(--c-error);
}

@keyframes timerPulse {
  0%,
  100% {
    opacity: 1;
  }
  50% {
    opacity: 0.6;
  }
}

/* Submit button */
.submit-btn {
  min-width: 52px;
  padding: 8px 12px;
  border-radius: 13px;
  border: 1px solid rgba(255, 59, 48, 0.24);
  background: rgba(255, 59, 48, 0.08);
  color: var(--c-error);
  font-size: var(--text-sm);
  font-weight: var(--weight-medium);
  cursor: pointer;
  min-height: 38px;
  transition: all var(--duration-fast) var(--ease-out);
  white-space: nowrap;
  justify-content: center;
  text-align: center;
}

.submit-btn:hover {
  background: var(--c-error);
  color: white;
}

.submit-btn:active {
  transform: scale(0.95);
}

/* 可滚动的答题内容 */
.scrollable-content {
  padding-top: var(--space-3);
}

.content-inner {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.exam-question-scroll {
  flex: 1;
  min-height: 0;
  overflow: hidden;
  padding: var(--space-3) calc(var(--space-4) + var(--safe-right)) var(--space-4)
    calc(var(--space-4) + var(--safe-left));
}

.exam-bottom-bar {
  flex-shrink: 0;
  position: relative;
}

.exam-progress-dots {
  margin-top: 0;
  margin-bottom: var(--space-3);
}

.exam-question-scroll .content-inner {
  height: 100%;
}

.exam-question-scroll .fade-in {
  height: 100%;
}

.exam-question-scroll :deep(.question-card) {
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.exam-question-scroll :deep(.question-card) > .q-header,
.exam-question-scroll :deep(.question-card-body) > .q-text {
  flex-shrink: 0;
}

.exam-question-scroll :deep(.question-card-body) {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding-right: 4px;
  -webkit-overflow-scrolling: touch;
}

/* Exam navigation bar */
.exam-nav-bar {
  margin-top: 0;
  padding: 0;
  grid-template-columns: minmax(88px, 108px) minmax(0, 1fr) minmax(88px, 108px);
}

.exam-nav-bar .nav-info {
  font-size: var(--text-sm);
  color: var(--text-secondary);
  text-align: center;
  min-width: 0;
}

.exam-nav-bar .btn {
  min-height: 40px;
  padding: 8px 14px;
  font-size: var(--text-sm);
}

/* Confirm Modal */
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.4);
  backdrop-filter: blur(4px);
  -webkit-backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
  padding: var(--space-8);
  animation: fadeIn 0.2s var(--ease-out) both;
}

.modal {
  width: 100%;
  max-width: 280px;
  background: var(--bg-surface);
  border-radius: var(--radius-xl);
  padding: var(--space-6) var(--space-5) var(--space-4);
  text-align: center;
  box-shadow: var(--shadow-lg);
  animation: modalIn 0.3s var(--ease-spring) both;
}

@keyframes fadeIn {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}

@keyframes modalIn {
  from {
    opacity: 0;
    transform: scale(0.9);
  }
  to {
    opacity: 1;
    transform: scale(1);
  }
}

.modal-icon-wrap {
  width: 48px;
  height: 48px;
  margin: 0 auto var(--space-3);
  border-radius: var(--radius-full);
  background: rgba(255, 59, 48, 0.1);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--c-error);
}

.timeup-icon {
  background: rgba(255, 149, 0, 0.1);
  color: var(--c-warning);
}

.modal-text {
  margin: 0 0 var(--space-2);
  font-size: var(--text-sm);
  color: var(--text-primary);
  line-height: 1.5;
}

.modal-text.muted {
  color: var(--text-secondary);
}

.modal-text strong {
  font-weight: var(--weight-semibold);
}

.modal-actions {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  margin-top: var(--space-4);
}

.modal-actions .btn-row {
  width: 100%;
  justify-content: center;
  padding: 12px;
  border-radius: var(--radius-md);
  min-height: 44px;
  font-size: var(--text-base);
  font-weight: var(--weight-medium);
  border: none;
  cursor: pointer;
  transition: all var(--duration-fast) var(--ease-out);
}

.btn-row-cancel {
  background: var(--bg-surface-secondary);
  color: var(--c-primary);
}

.btn-row-cancel:hover {
  background: var(--border-default);
}

.btn-row-submit {
  background: var(--c-error);
  color: white;
}

.btn-row-submit:hover {
  opacity: 0.9;
}

@media (max-width: 640px) {
  .header-content {
    gap: var(--space-2);
  }

  .scrollable-content {
    padding-top: var(--space-2);
  }

  .exam-question-scroll {
    padding: var(--space-2) calc(var(--space-3) + var(--safe-right)) var(--space-3)
      calc(var(--space-3) + var(--safe-left));
  }

  .exam-timer {
    padding-inline: 12px;
    font-size: var(--text-sm);
  }

  .submit-btn {
    min-width: 48px;
    padding-inline: 10px;
    min-height: 36px;
  }

  .exam-nav-bar {
    grid-template-columns: 84px minmax(0, 1fr) 84px;
  }

  .exam-nav-bar .btn {
    padding-inline: 10px;
  }
}
</style>
