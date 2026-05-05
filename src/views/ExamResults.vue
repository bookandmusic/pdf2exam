<template>
  <div :class="['exam-results-page', { 'reviewing-mode': showWrongQuestions }]">
    <div v-if="!showWrongQuestions" class="score-page">
      <ScoreSummary
        :score="score"
        :correct-count="correctCount"
        :wrong-count="wrongCount"
        @review="openReview"
        @home="handleHome"
      />
    </div>

    <div
      v-else
      class="review-page mobile-shell"
      :style="{ '--review-bottom-panel-height': `${bottomPanelHeight}px` }"
    >
      <div class="sticky-header mobile-topbar">
        <div class="header-content mobile-topbar-content">
          <button class="back-btn" @click="showWrongQuestions = false">
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
          <span class="header-title">考后解析</span>
          <span class="header-count">{{ correctCount }} 对 / {{ wrongCount }} 错</span>
        </div>
      </div>

      <div class="review-main">
        <div
          :class="[
            'scrollable-content',
            'review-question-scroll',
            analysisVisible ? 'analysis-open' : 'analysis-closed',
          ]"
        >
          <div class="content-inner mobile-content review-content-inner">
            <div v-if="currentReviewQuestion" class="fade-in review-card-wrap">
              <QuestionCard
                :question="currentReviewQuestion"
                :show-answer="false"
                :current-answer="currentReviewAnswer"
              >
                <template #options>
                  <OptionSelector
                    :options="currentReviewQuestion.options"
                    :selected="reviewSelected"
                    :show-answer="false"
                    :correct-answer="
                      currentReviewQuestion.type === 'multiple'
                        ? currentReviewQuestion.answers || []
                        : currentReviewQuestion.answer
                    "
                    :mode="currentReviewQuestion.type || 'single'"
                    :disabled="true"
                  />
                </template>
              </QuestionCard>
            </div>
          </div>
        </div>

        <div
          v-if="currentReviewQuestion && currentReviewAnswer"
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
              <div :class="['result-badge', currentReviewAnswer.isCorrect ? 'correct' : 'wrong']">
                {{ currentReviewAnswer.isCorrect ? '✓ 回答正确' : '✗ 回答错误' }}
              </div>
              <span class="analysis-hint">下拉关闭</span>
            </div>
            <div class="analysis-sheet-body">
              <div v-if="!currentReviewAnswer.isCorrect" class="analysis-block">
                <span class="analysis-label">你的答案</span>
                <div class="analysis-value analysis-value-wrong">{{ formattedUserAnswer }}</div>
              </div>
              <div class="analysis-block">
                <span class="analysis-label">正确答案</span>
                <div class="analysis-value">{{ formattedCorrectAnswer }}</div>
              </div>
              <div class="analysis-block">
                <span class="analysis-label">解析</span>
                <p class="analysis-text">{{ currentReviewQuestion.knowledge || '暂无解析' }}</p>
              </div>
            </div>
          </div>
        </div>

        <div v-if="sessionQuestions.length > 0" ref="bottomPanelRef" class="mobile-bottom-panel">
          <div class="progress-dots review-progress-dots">
            <span
              v-for="(q, i) in sessionQuestions"
              :key="q.id"
              :class="['dot', reviewDotClass(i), { current: i === currentReviewIndex }]"
              @click="goToReviewQuestion(i)"
            ></span>
          </div>

          <div class="review-nav-bar mobile-actions-grid mobile-actions-split">
            <button
              class="btn btn-ghost"
              @click="goToPrevReview"
              :disabled="currentReviewIndex === 0"
            >
              上一题
            </button>
            <span class="nav-info mobile-progress-meta">
              第 {{ currentReviewIndex + 1 }} / {{ sessionQuestions.length }} 题
            </span>
            <button
              class="btn btn-primary"
              @click="goToNextReview"
              :disabled="currentReviewIndex >= sessionQuestions.length - 1"
            >
              下一题
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useExam } from '../composables/useExam'
import QuestionCard from '../components/QuestionCard.vue'
import OptionSelector from '../components/OptionSelector.vue'
import ScoreSummary from '../components/ScoreSummary.vue'

const router = useRouter()
const { score, correctCount, wrongCount, session, resetSession } = useExam()

const showWrongQuestions = ref(false)
const currentReviewIndex = ref(0)
const analysisVisible = ref(true)
const sheetDragOffset = ref(0)
const isDraggingSheet = ref(false)
const bottomPanelRef = ref<HTMLElement | null>(null)
const bottomPanelHeight = ref(88)
let dragStartY = 0
let dragPointerId: number | null = null
let bottomPanelObserver: ResizeObserver | null = null

const sessionQuestions = computed(() => session.value?.questions ?? [])
const sessionAnswers = computed(() => session.value?.answers ?? [])
const currentReviewQuestion = computed(
  () => sessionQuestions.value[currentReviewIndex.value] ?? null
)
const currentReviewAnswer = computed(() => sessionAnswers.value[currentReviewIndex.value] ?? null)

const reviewSelected = computed(() => {
  const answer = currentReviewAnswer.value
  if (!answer) return ''
  return answer.selected
})

const formattedCorrectAnswer = computed(() => {
  const question = currentReviewQuestion.value
  if (!question) return ''
  return (question.type === 'multiple' ? question.answers || [] : [question.answer]).join(', ')
})

const formattedUserAnswer = computed(() => {
  const answer = currentReviewAnswer.value
  if (!answer) return '未作答'
  const selected = Array.isArray(answer.selected) ? answer.selected : [answer.selected]
  const filtered = selected.filter((s) => s !== null && s !== undefined && s !== '')
  return filtered.length > 0 ? filtered.join(', ') : '未作答'
})

const analysisSheetStyle = computed(() => ({
  transform: `translateY(${sheetDragOffset.value}px)`,
}))

function openReview() {
  const firstWrongIndex = sessionAnswers.value.findIndex((answer) => answer && !answer.isCorrect)
  currentReviewIndex.value = firstWrongIndex >= 0 ? firstWrongIndex : 0
  showWrongQuestions.value = true
  analysisVisible.value = true
  resetSheetDrag()
  nextTick(syncBottomPanelHeight)
}

function handleHome() {
  resetSession()
  router.push('/')
}

function reviewDotClass(index: number) {
  const answer = sessionAnswers.value[index]
  if (!answer) return 'dot-unanswered'
  return answer.isCorrect ? 'dot-correct' : 'dot-wrong'
}

function goToReviewQuestion(index: number) {
  currentReviewIndex.value = index
  showAnalysis()
}

function goToPrevReview() {
  if (currentReviewIndex.value <= 0) return
  currentReviewIndex.value -= 1
  showAnalysis()
}

function goToNextReview() {
  if (currentReviewIndex.value >= sessionQuestions.value.length - 1) return
  currentReviewIndex.value += 1
  showAnalysis()
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

function syncBottomPanelHeight() {
  const panel = bottomPanelRef.value
  if (!panel) return
  bottomPanelHeight.value = Math.round(panel.getBoundingClientRect().height)
}

function startSheetDrag(event: PointerEvent) {
  if (!analysisVisible.value) return
  event.preventDefault()
  dragPointerId = event.pointerId
  dragStartY = event.clientY
  isDraggingSheet.value = true
  window.addEventListener('pointermove', onSheetDragMove)
  window.addEventListener('pointerup', endSheetDrag)
  window.addEventListener('pointercancel', endSheetDrag)
}

function onSheetDragMove(event: PointerEvent) {
  if (!isDraggingSheet.value || event.pointerId !== dragPointerId) return
  event.preventDefault()
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

onBeforeUnmount(() => {
  window.removeEventListener('pointermove', onSheetDragMove)
  window.removeEventListener('pointerup', endSheetDrag)
  window.removeEventListener('pointercancel', endSheetDrag)
  bottomPanelObserver?.disconnect()
})

onMounted(() => {
  nextTick(syncBottomPanelHeight)
  if (typeof ResizeObserver !== 'undefined') {
    bottomPanelObserver = new ResizeObserver(() => syncBottomPanelHeight())
    if (bottomPanelRef.value) {
      bottomPanelObserver.observe(bottomPanelRef.value)
    }
  }
})
</script>

<style scoped>
.exam-results-page {
  min-height: 100vh;
  min-height: 100dvh;
  background: transparent;
  overscroll-behavior: none;
}

.exam-results-page.reviewing-mode {
  height: 100vh;
  height: 100dvh;
  overflow: hidden;
  overscroll-behavior: none;
}

.score-page {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  min-height: 100dvh;
  padding: calc(var(--safe-top) + var(--space-4)) calc(var(--space-4) + var(--safe-right))
    calc(var(--safe-bottom) + var(--space-4)) calc(var(--space-4) + var(--safe-left));
  overflow-y: auto;
  -webkit-overflow-scrolling: touch;
}

.review-page {
  display: flex;
  flex-direction: column;
  height: 100vh;
  height: 100dvh;
  overflow: hidden;
  background: transparent;
}

.review-main {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
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
  padding: 10px 14px;
  border-radius: var(--radius-full);
  background: rgba(255, 255, 255, 0.52);
  border: 1px solid rgba(255, 255, 255, 0.72);
}

.header-count {
  font-size: var(--text-sm);
  color: var(--text-secondary);
  background: rgba(255, 255, 255, 0.55);
  border: 1px solid rgba(255, 255, 255, 0.72);
  padding: var(--space-1) var(--space-3);
  border-radius: var(--radius-full);
}

.review-question-scroll {
  flex: 1;
  min-height: 0;
  overflow: hidden;
  padding: var(--space-3) calc(var(--space-4) + var(--safe-right))
    calc(var(--review-bottom-panel-height) + var(--space-3)) calc(var(--space-4) + var(--safe-left));
  transition: padding-bottom 0.2s var(--ease-out);
}
.review-question-scroll.analysis-closed {
  padding-bottom: calc(var(--review-bottom-panel-height) + 60px + var(--space-3));
}

.review-question-scroll .content-inner,
.review-question-scroll .fade-in {
  height: 100%;
}

.review-content-inner {
  display: flex;
  flex: 1;
  min-height: 0;
}

.review-question-scroll :deep(.question-card) {
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.74), rgba(244, 248, 255, 0.86)),
    rgba(255, 255, 255, 0.72);
  border: 1px solid rgba(255, 255, 255, 0.68);
  box-shadow: 0 16px 36px rgba(28, 54, 107, 0.08);
}

.review-question-scroll :deep(.question-card) > .q-header,
.review-question-scroll :deep(.question-card-body) > .q-text {
  flex-shrink: 0;
}

.review-question-scroll :deep(.question-card-body) {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding-right: 4px;
  -webkit-overflow-scrolling: touch;
}

.review-card-wrap {
  height: 100%;
  flex: 1;
  min-height: 0;
}

.review-card-wrap :deep(.option-group.locked) {
  pointer-events: none;
}

.mobile-bottom-panel {
  position: fixed;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 20;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.96), rgba(247, 250, 255, 0.98)),
    rgba(255, 255, 255, 0.94);
  border: 1px solid rgba(255, 255, 255, 0.92);
  border-radius: var(--radius-xl) var(--radius-xl) 0 0;
  box-shadow:
    0 22px 54px rgba(28, 54, 107, 0.2),
    0 6px 14px rgba(28, 54, 107, 0.08);
  padding: var(--space-4) calc(var(--space-4) + var(--safe-right))
    calc(var(--space-4) + var(--safe-bottom)) calc(var(--space-4) + var(--safe-left));
}

.review-progress-dots {
  margin-top: 0;
  margin-bottom: var(--space-3);
}

.progress-dots .dot.dot-correct {
  background: var(--c-success);
}

.progress-dots .dot.dot-wrong {
  background: var(--c-error);
}

.progress-dots .dot.dot-unanswered {
  background: var(--text-tertiary);
}

.review-nav-bar {
  margin-top: 0;
  padding: 0;
  grid-template-columns: minmax(90px, 110px) minmax(0, 1fr) minmax(90px, 110px);
}

.review-nav-bar .btn {
  min-height: 44px;
  padding: 10px 16px;
  font-size: var(--text-base);
  font-weight: var(--weight-medium);
}

.analysis-sheet-layer {
  position: fixed;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 10;
  display: flex;
  justify-content: center;
  pointer-events: none;
  overscroll-behavior: none;
  padding: 0 calc(var(--space-4) + var(--safe-right)) 0 calc(var(--space-4) + var(--safe-left));
}

.analysis-peek-line {
  width: 44px;
  height: 5px;
  border-radius: var(--radius-full);
  background: rgba(60, 60, 67, 0.24);
}

.analysis-peek-label {
  font-size: var(--text-sm);
  font-weight: var(--weight-medium);
}

.analysis-sheet {
  pointer-events: auto;
  width: min(100%, 760px);
  background:
    linear-gradient(180deg, rgba(232, 241, 255, 0.94), rgba(243, 248, 255, 0.97)),
    rgba(236, 244, 255, 0.92);
  backdrop-filter: blur(26px);
  -webkit-backdrop-filter: blur(26px);
  border: 1px solid rgba(214, 228, 248, 0.96);
  border-radius: 26px;
  box-shadow:
    0 18px 40px rgba(39, 76, 145, 0.16),
    0 4px 12px rgba(39, 76, 145, 0.06);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  animation: sheetRise 220ms cubic-bezier(0.22, 1, 0.36, 1);
  transition: transform 180ms cubic-bezier(0.22, 1, 0.36, 1);
  overscroll-behavior: contain;
}

.analysis-sheet-expanded {
  height: calc(100vh - var(--review-bottom-panel-height) - 100px);
  max-height: calc(100vh - 60px);
  min-height: 300px;
}

.analysis-sheet-collapsed {
  height: calc(var(--review-bottom-panel-height) + 60px);
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
  overscroll-behavior: contain;
  padding: 0 var(--space-5) var(--space-5);
  -webkit-overflow-scrolling: touch;
}

.analysis-sheet-expanded .analysis-sheet-body {
  padding-bottom: calc(var(--review-bottom-panel-height) + var(--space-5));
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

@media (max-width: 640px) {
  .score-page {
    padding: var(--space-3);
  }

  .review-question-scroll {
    padding: var(--space-2) var(--safe-right)
      calc(var(--review-bottom-panel-height) + var(--space-2)) var(--safe-left);
  }
  .review-question-scroll.analysis-closed {
    padding-bottom: calc(var(--review-bottom-panel-height) + 60px + var(--space-2));
  }

  .analysis-sheet-layer {
    padding: 0 var(--safe-right) 0 var(--safe-left);
  }

  .analysis-sheet {
    border-radius: 24px 24px 0 0;
    width: 100%;
  }

  .analysis-sheet-expanded {
    height: calc(100vh - var(--review-bottom-panel-height) - 80px);
    max-height: calc(100vh - 40px);
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
    padding-bottom: calc(var(--review-bottom-panel-height) + var(--space-4));
  }

  .mobile-bottom-panel {
    padding: var(--space-4) calc(var(--space-4) + var(--safe-right))
      calc(var(--space-4) + var(--safe-bottom)) calc(var(--space-4) + var(--safe-left));
  }
}
</style>
