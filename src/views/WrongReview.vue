<template>
  <div class="wrong-review-page mobile-shell">
    <div class="sticky-header mobile-topbar">
      <div class="header-content mobile-topbar-content">
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
        <span class="header-title">错题集</span>
        <span v-if="totalQuestions > 0" class="header-count">{{ totalQuestions }} 题</span>
        <div v-else class="header-spacer"></div>
      </div>
      <ProgressBar v-if="totalQuestions > 0" :current="currentIndex + 1" :total="totalQuestions" />
    </div>

    <div class="scrollable-content mobile-scroll" :class="{ 'has-analysis-sheet': isAnswered }">
      <div class="content-inner mobile-content">
        <div v-if="currentQuestion" class="fade-in">
          <QuestionCard
            :question="currentQuestion"
            :showAnswer="false"
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
                :disabled="isAnswered"
                @select="handleSelect"
              />
            </template>
          </QuestionCard>
        </div>

        <div v-else class="empty-state">
          <div class="empty-icon">
            <svg
              width="48"
              height="48"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="1.5"
              stroke-linecap="round"
              stroke-linejoin="round"
            >
              <path d="M9 11l3 3L22 4" />
              <path d="M21 12v7a2 2 0 01-2 2H5a2 2 0 01-2-2V5a2 2 0 012-2h11" />
            </svg>
          </div>
          <p class="empty-text">错题集为空，继续保持！</p>
        </div>
      </div>
    </div>

    <div
      v-if="isAnswered && currentQuestion"
      :class="[
        'analysis-sheet-layer',
        analysisVisible ? 'analysis-sheet-layer-expanded' : 'analysis-sheet-layer-collapsed',
      ]"
      aria-live="polite"
    >
      <div
        v-if="!analysisVisible"
        class="analysis-sheet analysis-sheet-collapsed"
        role="button"
        tabindex="0"
        @click="showAnalysis"
        @keydown.enter="showAnalysis"
      >
        <div class="analysis-sheet-handle-wrap">
          <div class="analysis-sheet-handle"></div>
        </div>
        <div class="analysis-sheet-header analysis-sheet-header-collapsed">
          <span class="analysis-peek-label">点击查看解析</span>
          <span class="analysis-hint">上滑查看</span>
        </div>
      </div>

      <div
        v-else
        class="analysis-sheet analysis-sheet-expanded"
        :class="{ 'is-dragging': isDraggingSheet }"
        :style="analysisSheetStyle"
      >
        <div class="analysis-sheet-handle-wrap" @pointerdown="startSheetDrag">
          <div class="analysis-sheet-handle"></div>
        </div>
        <div class="analysis-sheet-header">
          <div :class="['result-badge', currentAnswer?.isCorrect ? 'correct' : 'wrong']">
            {{ currentAnswer?.isCorrect ? '✓ 回答正确' : '✗ 回答错误' }}
          </div>
          <span class="analysis-hint">下拉关闭</span>
        </div>
        <div class="analysis-sheet-body">
          <div v-if="pendingRemove" class="remove-prompt-inline">
            <p>回答正确！是否将此题从错题集移除？</p>
            <button class="btn btn-ghost btn-remove" @click="handleRemoveAndNext">移除</button>
          </div>
          <div v-if="!currentAnswer?.isCorrect" class="analysis-block">
            <span class="analysis-label">你的答案</span>
            <div class="analysis-value analysis-value-wrong">{{ formattedUserAnswer }}</div>
          </div>
          <div class="analysis-block">
            <span class="analysis-label">正确答案</span>
            <div class="analysis-value">{{ formattedAnswer }}</div>
          </div>
          <div class="analysis-block">
            <span class="analysis-label">解析</span>
            <p class="analysis-text">{{ currentQuestion.knowledge || '暂无解析' }}</p>
          </div>
        </div>
      </div>
    </div>

    <div v-if="currentQuestion" class="mobile-bottom-panel">
      <div class="review-nav-bar mobile-actions-grid">
        <button class="btn btn-ghost" @click="handlePrev" :disabled="isFirst">上一题</button>
        <span class="nav-info mobile-progress-meta">
          第 {{ currentIndex + 1 }} / {{ totalQuestions }} 题
        </span>
        <button v-if="isLast && isAnswered" class="btn btn-success" @click="handleFinish">
          {{ nextButtonText }}
        </button>
        <button v-else class="btn btn-primary" @click="handleNext">
          {{ nextButtonText }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount, watch } from 'vue'
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
const analysisVisible = ref(false)
const sheetDragOffset = ref(0)
const isDraggingSheet = ref(false)
let dragStartY = 0
let dragPointerId: number | null = null

const wrongQuestions = computed(() => {
  const ids = new Set(wrongIds.value.map((e) => e.id))
  return questions.value.filter((q) => ids.has(q.id))
})

const formattedAnswer = computed(() => {
  const question = currentQuestion.value
  if (!question) return ''
  return (question.type === 'multiple' ? question.answers || [] : [question.answer]).join(', ')
})

const formattedUserAnswer = computed(() => {
  const answer = currentAnswer.value
  if (!answer) return '未作答'
  const selected = Array.isArray(answer.selected) ? answer.selected : [answer.selected]
  const filtered = selected.filter((s) => s !== null && s !== undefined && s !== '')
  return filtered.length > 0 ? filtered.join(', ') : '未作答'
})

const analysisSheetStyle = computed(() => ({
  transform: `translateY(${sheetDragOffset.value}px)`,
}))

watch(currentIndex, () => {
  analysisVisible.value = false
  resetSheetDrag()
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

function showAnalysis() {
  analysisVisible.value = true
  resetSheetDrag()
}

function closeAnalysis() {
  analysisVisible.value = false
  resetSheetDrag()
}

function resetSheetDrag() {
  sheetDragOffset.value = 0
  isDraggingSheet.value = false
  dragStartY = 0
  dragPointerId = null
}

function startSheetDrag(event: PointerEvent) {
  if (!analysisVisible.value) return
  dragPointerId = event.pointerId
  dragStartY = event.clientY
  isDraggingSheet.value = true
  window.addEventListener('pointermove', onSheetDragMove)
  window.addEventListener('pointerup', endSheetDrag)
  window.addEventListener('pointercancel', endSheetDrag)
}

function onSheetDragMove(event: PointerEvent) {
  if (!isDraggingSheet.value || event.pointerId !== dragPointerId) return
  sheetDragOffset.value = Math.max(0, event.clientY - dragStartY)
}

function endSheetDrag(event: PointerEvent) {
  if (dragPointerId !== null && event.pointerId !== dragPointerId) return
  const shouldClose = sheetDragOffset.value > 72
  window.removeEventListener('pointermove', onSheetDragMove)
  window.removeEventListener('pointerup', endSheetDrag)
  window.removeEventListener('pointercancel', endSheetDrag)
  if (shouldClose) {
    closeAnalysis()
    return
  }
  resetSheetDrag()
}

function handleNext() {
  if (pendingRemove.value) {
    pendingRemove.value = false
    closeAnalysis()
    next()
    return
  }
  if (!isAnswered.value) {
    const ok = handleConfirm()
    if (!ok) return
    analysisVisible.value = true
    resetSheetDrag()
    if (currentAnswer.value?.isCorrect && currentQuestion.value) {
      recordCorrect(currentQuestion.value.id)
      pendingRemove.value = true
    }
  } else {
    closeAnalysis()
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

function handleFinish() {
  if (!isAnswered.value) {
    const ok = handleConfirm()
    if (!ok) return
    analysisVisible.value = true
    resetSheetDrag()
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

onBeforeUnmount(() => {
  window.removeEventListener('pointermove', onSheetDragMove)
  window.removeEventListener('pointerup', endSheetDrag)
  window.removeEventListener('pointercancel', endSheetDrag)
})
</script>

<style scoped>
/* 根容器 */
.wrong-review-page {
  height: 100vh;
  height: 100dvh;
  overflow: hidden;
  background: transparent;
  overscroll-behavior: none;
}

.sticky-header {
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

.header-title {
  font-size: var(--text-lg);
  font-weight: var(--weight-semibold);
  color: var(--text-primary);
}

.header-count {
  font-size: var(--text-sm);
  color: var(--text-secondary);
  background: rgba(255, 255, 255, 0.55);
  border: 1px solid rgba(255, 255, 255, 0.72);
  padding: var(--space-1) var(--space-3);
  border-radius: var(--radius-full);
}

.header-spacer {
  width: 60px;
}

/* 可滚动的答题内容 */
.scrollable-content {
  flex: 1;
  min-height: 0;
  overflow: hidden;
  padding: var(--space-3) calc(var(--space-4) + var(--safe-right)) calc(88px + var(--space-3))
    calc(var(--space-4) + var(--safe-left));
  transition: padding-bottom 0.2s var(--ease-out);
}
.scrollable-content.has-analysis-sheet {
  padding-bottom: calc(148px + var(--space-3));
}

.content-inner {
  height: 100%;
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.content-inner .fade-in {
  height: 100%;
}

.scrollable-content :deep(.question-card) {
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.scrollable-content :deep(.question-card) > .q-header,
.scrollable-content :deep(.question-card-body) > .q-text {
  flex-shrink: 0;
}

.scrollable-content :deep(.question-card-body) {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding-right: 4px;
  -webkit-overflow-scrolling: touch;
}

/* Analysis sheet */
.analysis-sheet-layer {
  position: fixed;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 10;
  display: flex;
  justify-content: center;
  pointer-events: none;
  padding: 0 calc(var(--space-4) + var(--safe-right)) 0 calc(var(--space-4) + var(--safe-left));
}

.analysis-sheet {
  pointer-events: auto;
  width: min(100%, 760px);
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.88), rgba(248, 250, 255, 0.94)),
    rgba(255, 255, 255, 0.84);
  backdrop-filter: blur(30px);
  -webkit-backdrop-filter: blur(30px);
  border: 1px solid rgba(255, 255, 255, 0.82);
  border-radius: 26px;
  box-shadow: var(--shadow-lg);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  animation: sheetRise 220ms cubic-bezier(0.22, 1, 0.36, 1);
  transition: transform 180ms cubic-bezier(0.22, 1, 0.36, 1);
}

.analysis-sheet-expanded {
  height: 50vh;
  max-height: calc(100vh - 120px);
  min-height: 300px;
}

.analysis-sheet-collapsed {
  height: calc(88px + 60px);
  background:
    linear-gradient(180deg, rgba(221, 235, 255, 0.98), rgba(237, 245, 255, 0.98)),
    rgba(228, 239, 255, 0.96);
  border: 1px solid rgba(196, 216, 244, 0.98);
  box-shadow:
    0 16px 34px rgba(39, 76, 145, 0.18),
    0 4px 10px rgba(39, 76, 145, 0.08);
  padding: 0;
  color: inherit;
  cursor: pointer;
  overflow: visible;
}
.analysis-sheet-collapsed .analysis-sheet-handle-wrap {
  padding: 10px 0 4px;
  text-align: center;
}
.analysis-sheet-collapsed .analysis-sheet-handle {
  display: inline-block;
  margin: 0 auto;
}
.analysis-sheet-collapsed .analysis-sheet-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--space-3) var(--space-5) 0;
  border-bottom: none;
  flex-shrink: 0;
}

.analysis-sheet.is-dragging {
  transition: none;
}

.analysis-sheet-handle-wrap {
  display: flex;
  justify-content: center;
  padding-top: 10px;
  padding-bottom: 4px;
  cursor: grab;
  touch-action: none;
}

.analysis-sheet-handle-wrap:active {
  cursor: grabbing;
}

.analysis-sheet-handle {
  width: 44px;
  height: 5px;
  border-radius: var(--radius-full);
  background: rgba(60, 60, 67, 0.24);
}

.analysis-peek-label {
  font-size: var(--text-sm);
  font-weight: var(--weight-medium);
}

.analysis-sheet-header-collapsed {
  padding-top: var(--space-3);
  border-bottom: none;
}

.analysis-sheet-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  padding: var(--space-4) var(--space-5) var(--space-3);
  border-bottom: 1px solid rgba(15, 23, 42, 0.08);
  flex-shrink: 0;
}

.analysis-hint {
  font-size: var(--text-sm);
  color: var(--text-tertiary);
}

.analysis-sheet-body {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 0 var(--space-5) var(--space-5);
  -webkit-overflow-scrolling: touch;
}

.analysis-sheet-expanded .analysis-sheet-body {
  padding-bottom: calc(88px + var(--space-5));
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
  font-size: 18px;
  font-weight: var(--weight-semibold);
  color: var(--c-success);
}

.analysis-value-wrong {
  color: var(--c-error);
}

.analysis-text {
  margin: 0;
  padding: var(--space-3);
  border-radius: var(--radius-md);
  background: rgba(245, 247, 252, 0.9);
  color: var(--text-secondary);
  line-height: 1.7;
  white-space: pre-wrap;
}

@keyframes sheetRise {
  from {
    opacity: 0;
    transform: translateY(24px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

/* Review navigation bar */
.mobile-bottom-panel {
  position: fixed;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 20;
  border-radius: var(--radius-xl) var(--radius-xl) 0 0;
  padding: var(--space-4) calc(var(--space-4) + var(--safe-right))
    calc(var(--space-4) + var(--safe-bottom)) calc(var(--space-4) + var(--safe-left));
}

.review-nav-bar {
  margin-top: 0;
  padding: 0;
  grid-template-columns: minmax(90px, 110px) 1fr minmax(90px, 110px);
  gap: var(--space-3);
  align-items: center;
}

.review-nav-bar .btn {
  min-height: 44px;
  padding: 10px 16px;
  font-size: var(--text-base);
  font-weight: var(--weight-medium);
}

.review-nav-bar .nav-info {
  font-size: var(--text-sm);
  text-align: center;
}

.correct-text {
  color: var(--c-success);
  font-weight: var(--weight-semibold);
}

.wrong-text {
  color: var(--c-error);
  font-weight: var(--weight-semibold);
}

/* Remove prompt inline */
.remove-prompt-inline {
  padding: var(--space-4);
  margin-bottom: var(--space-4);
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  border-radius: var(--radius-lg);
  background: rgba(52, 199, 89, 0.08);
  border: 1px solid rgba(52, 199, 89, 0.2);
}

.remove-prompt-inline p {
  margin: 0;
  color: var(--c-success);
  font-weight: var(--weight-semibold);
  font-size: var(--text-base);
  flex: 1;
}

.btn-remove {
  flex-shrink: 0;
  font-size: var(--text-sm);
  padding: var(--space-2) var(--space-3);
  min-height: 36px;
  background: var(--c-error);
  border-color: var(--c-error);
  color: white;
}

.btn-remove:hover {
  background: #d32f2f;
  border-color: #d32f2f;
}

/* Empty state */
.empty-state {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--space-4);
  min-height: 300px;
}

.empty-icon {
  color: var(--c-success);
  opacity: 0.6;
}

.empty-text {
  margin: 0;
  font-size: var(--text-lg);
  color: var(--text-secondary);
  font-weight: var(--weight-medium);
}

@media (max-width: 640px) {
  .header-content {
    gap: var(--space-2);
  }

  .scrollable-content {
    padding: var(--space-2) var(--safe-right) calc(88px + var(--space-2)) var(--safe-left);
  }
  .scrollable-content.has-analysis-sheet {
    padding-bottom: calc(148px + var(--space-2));
  }

  .analysis-sheet-layer {
    padding: 0 var(--safe-right) 0 var(--safe-left);
  }

  .analysis-sheet {
    border-radius: 24px 24px 0 0;
    width: 100%;
  }

  .analysis-sheet-expanded {
    height: 50vh;
    max-height: calc(100vh - 100px);
    min-height: 320px;
  }

  .analysis-sheet-header {
    padding-inline: var(--space-4);
  }

  .analysis-sheet-body {
    padding-inline: var(--space-4);
    padding-bottom: var(--space-4);
  }

  .analysis-sheet-expanded .analysis-sheet-body {
    padding-bottom: calc(88px + var(--space-4));
  }

  .remove-prompt-inline {
    padding: var(--space-3);
  }

  .mobile-bottom-panel {
    padding: var(--space-4) calc(var(--space-4) + var(--safe-right))
      calc(var(--space-4) + var(--safe-bottom)) calc(var(--space-4) + var(--safe-left));
  }
}
</style>
