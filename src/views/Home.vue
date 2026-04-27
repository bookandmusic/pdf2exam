<template>
  <div class="home page">
    <!-- iOS-style Large Title Header -->
    <header class="ios-header">
      <div class="title-group">
        <h1 class="large-title">刷题助手</h1>
        <p class="title-subtitle">智能组卷 · 高效刷题</p>
      </div>
      <button class="settings-btn" @click="$router.push('/settings')" aria-label="设置">
        <svg
          width="22"
          height="22"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
          stroke-linecap="round"
          stroke-linejoin="round"
        >
          <circle cx="12" cy="12" r="3" />
          <path
            d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09a1.65 1.65 0 0 0-1-1.51 1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09a1.65 1.65 0 0 0 1.51-1 1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33A1.65 1.65 0 0 0 9 6.59V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82 1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"
          />
        </svg>
      </button>
    </header>

    <!-- Stats Card + Filter Trigger -->
    <div
      v-if="!isLoading"
      :class="['stats-card', { 'stats-card-filterable': subjects.length > 0 }]"
      @click="subjects.length > 0 ? (showDrawer = true) : $router.push('/settings')"
    >
      <div class="stats-icon-wrap">
        <svg
          width="24"
          height="24"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
          stroke-linecap="round"
          stroke-linejoin="round"
        >
          <path d="M22 19a2 2 0 01-2 2H4a2 2 0 01-2-2V5a2 2 0 012-2h5l2 3h9a2 2 0 012 2z" />
        </svg>
      </div>
      <div class="stats-body">
        <div class="stats-top">
          <span class="stats-count">{{ count }}</span>
          <span class="stats-label">道可用题目</span>
        </div>
        <div v-if="subjects.length > 0" class="stats-filter-summary">
          <span class="filter-chip">{{ subjectLabel }}</span>
          <span class="filter-divider">·</span>
          <span class="filter-chip">{{ chapterLabel }}</span>
        </div>
      </div>
      <svg
        class="stats-chevron"
        width="16"
        height="16"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        stroke-width="2.5"
        stroke-linecap="round"
        stroke-linejoin="round"
      >
        <path d="M9 18l6-6-6-6" />
      </svg>
    </div>

    <!-- Loading skeleton -->
    <div v-if="isLoading" class="skeleton-card">
      <div class="skeleton-line w-32"></div>
      <div class="skeleton-line w-48"></div>
    </div>

    <div v-if="error" class="error-msg">{{ error }}</div>

    <!-- Empty State -->
    <div v-if="count === 0 && !isLoading" class="empty-state">
      <div class="empty-icon-wrap">
        <svg
          width="40"
          height="40"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="1.5"
          stroke-linecap="round"
          stroke-linejoin="round"
        >
          <path d="M13 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V9z" />
          <polyline points="13 2 13 9 20 9" />
        </svg>
      </div>
      <p class="empty-title">题库为空</p>
      <p class="empty-desc">导入题目文件开始练习</p>
      <button class="btn btn-primary" @click="$router.push('/settings')">
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
          <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M17 8l-5-5-5 5M12 3v12" />
        </svg>
        导入题库
      </button>
    </div>

    <!-- Mode Cards (iOS App Store Style) -->
    <section v-if="count > 0" class="section fade-in-delay-1">
      <h2 class="section-label">练习模式</h2>
      <div class="mode-list">
        <div class="mode-card" @click="$router.push('/mock-exam')">
          <div class="mode-card-left">
            <div class="mode-icon mode-icon-exam">
              <svg
                width="24"
                height="24"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="2"
                stroke-linecap="round"
                stroke-linejoin="round"
              >
                <path d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2" />
                <rect x="9" y="3" width="6" height="4" rx="1" />
                <path d="M9 14l2 2 4-4" />
              </svg>
            </div>
            <div class="mode-card-text">
              <h3 class="mode-card-title">模拟考试</h3>
              <p class="mode-card-desc">限时答题，考后查看解析</p>
            </div>
          </div>
          <svg
            class="mode-chevron"
            width="14"
            height="14"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2.5"
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            <path d="M9 18l6-6-6-6" />
          </svg>
        </div>
        <div class="mode-card" @click="$router.push('/sequential')">
          <div class="mode-card-left">
            <div class="mode-icon mode-icon-book">
              <svg
                width="24"
                height="24"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="2"
                stroke-linecap="round"
                stroke-linejoin="round"
              >
                <path d="M4 19.5A2.5 2.5 0 016.5 17H20" />
                <path d="M6.5 2H20v20H6.5A2.5 2.5 0 014 19.5v-15A2.5 2.5 0 016.5 2z" />
                <path d="M8 7h8M8 11h6" />
              </svg>
            </div>
            <div class="mode-card-text">
              <h3 class="mode-card-title">顺序刷题</h3>
              <p class="mode-card-desc">逐题练习，进度自动保存</p>
            </div>
          </div>
          <svg
            class="mode-chevron"
            width="14"
            height="14"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2.5"
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            <path d="M9 18l6-6-6-6" />
          </svg>
        </div>
        <div class="mode-card" @click="$router.push('/wrong')">
          <div class="mode-card-left">
            <div class="mode-icon mode-icon-wrong">
              <svg
                width="24"
                height="24"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="2"
                stroke-linecap="round"
                stroke-linejoin="round"
              >
                <circle cx="12" cy="12" r="10" />
                <path d="M15 9l-6 6M9 9l6 6" />
              </svg>
            </div>
            <div class="mode-card-text">
              <h3 class="mode-card-title">错题集</h3>
              <p class="mode-card-desc" v-if="wrongCount > 0">{{ wrongCount }} 道错题待复习</p>
              <p class="mode-card-desc" v-else>暂无错题，继续保持</p>
            </div>
          </div>
          <div class="mode-card-right">
            <span v-if="wrongCount > 0" class="wrong-badge">{{ wrongCount }}</span>
            <svg
              class="mode-chevron"
              width="14"
              height="14"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="2.5"
              stroke-linecap="round"
              stroke-linejoin="round"
            >
              <path d="M9 18l6-6-6-6" />
            </svg>
          </div>
        </div>
      </div>
    </section>

    <!-- Footer spacer for safe area -->
    <div class="footer-spacer"></div>

    <!-- Filter Drawer -->
    <FilterDrawer
      :visible="showDrawer"
      :subjects="subjects"
      :chapters="chapters"
      :selected-subject-ids="currentSubjectIds"
      :selected-chapter-ids="currentChapterIds"
      @close="showDrawer = false"
      @toggle-subject="toggleSubject"
      @toggle-chapter="toggleChapter"
      @clear-chapters="clearChapters"
      @reset="resetFilters"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useQuestionBank } from '../stores/questionBank'
import { useWrongQuestions } from '../stores/wrongQuestions'
import type { Question } from '../types/question'
import FilterDrawer from '../components/FilterDrawer.vue'

const {
  count,
  isLoading,
  error,
  load,
  importJson,
  subjects,
  currentSubjectIds,
  currentChapterIds,
  chapters,
  filteredQuestions,
  loadBuiltinSubjects,
  toggleSubject,
  toggleChapter,
  clearChapters,
  resetFilters,
} = useQuestionBank()
const { wrongIds } = useWrongQuestions()

const showDrawer = ref(false)

const wrongCount = computed(() => {
  const wrongIdSet = new Set(wrongIds.value.map((entry) => entry.id))
  return filteredQuestions.value.filter((question) => wrongIdSet.has(question.id)).length
})

const subjectLabel = computed(() => {
  if (currentSubjectIds.value.length === 0) return '全部科目'
  if (currentSubjectIds.value.length === 1) {
    const s = subjects.value.find((s) => s.id === currentSubjectIds.value[0])
    return s ? s.name : '已选 1 个科目'
  }
  return `已选 ${currentSubjectIds.value.length} 个科目`
})

const chapterLabel = computed(() => {
  if (currentChapterIds.value.length === 0) return '全部章节'
  if (currentChapterIds.value.length === 1) {
    const ch = chapters.value.find((c) => c.id === currentChapterIds.value[0])
    return ch ? ch.name : '已选 1 个章节'
  }
  return `已选 ${currentChapterIds.value.length} 个章节`
})

onMounted(async () => {
  await loadBuiltinSubjects()
  if (subjects.value.length === 0) {
    await load()
    if (count.value === 0) {
      try {
        const res = await fetch('/questions.json')
        const qs: Question[] = await res.json()
        await importJson(qs)
      } catch (_e) {
        // Bundled questions not available
      }
    }
  }
})
</script>

<style scoped>
/* ========================================
   iOS-style Large Title Header
   ======================================== */
.ios-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  padding-top: var(--space-2);
  margin-bottom: var(--space-6);
}

.title-group {
  flex: 1;
}

.large-title {
  font-size: 34px;
  font-weight: var(--weight-bold);
  letter-spacing: -0.5px;
  color: var(--text-primary);
  margin: 0;
  line-height: 1.1;
}

.title-subtitle {
  font-size: var(--text-sm);
  color: var(--text-secondary);
  margin: var(--space-1) 0 0 0;
  font-weight: var(--weight-normal);
}

.settings-btn {
  flex-shrink: 0;
  width: 40px;
  height: 40px;
  border-radius: var(--radius-full);
  background: var(--bg-surface-secondary);
  border: none;
  color: var(--text-secondary);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-top: 4px;
  min-width: 44px;
  min-height: 44px;
  transition:
    background var(--duration-fast) var(--ease-out),
    color var(--duration-fast) var(--ease-out);
}

.settings-btn:hover {
  background: var(--border-default);
  color: var(--text-primary);
}

.settings-btn:active {
  transform: scale(0.92);
}

/* ========================================
   Stats Card — iOS Widget Style + Filter
   ======================================== */
.stats-card {
  display: flex;
  align-items: center;
  gap: var(--space-4);
  padding: var(--space-4) var(--space-5);
  background: var(--bg-surface);
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-sm);
  margin-bottom: var(--space-6);
  cursor: pointer;
  transition:
    transform var(--duration-fast) var(--ease-spring),
    box-shadow var(--duration-fast) var(--ease-out);
}

.stats-card:hover {
  box-shadow: var(--shadow-md);
}

.stats-card:active {
  transform: scale(0.97);
}

.stats-icon-wrap {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 48px;
  height: 48px;
  border-radius: var(--radius-md);
  background: rgba(99, 102, 241, 0.1);
  color: var(--c-primary);
  flex-shrink: 0;
}

.stats-body {
  flex: 1;
  min-width: 0;
}

.stats-top {
  display: flex;
  align-items: baseline;
  gap: var(--space-2);
  margin-bottom: 2px;
}

.stats-count {
  font-size: 28px;
  font-weight: var(--weight-bold);
  color: var(--text-primary);
  letter-spacing: -0.5px;
  line-height: 1;
}

.stats-label {
  font-size: var(--text-base);
  color: var(--text-secondary);
  white-space: nowrap;
}

.stats-filter-summary {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  font-size: var(--text-sm);
  color: var(--text-tertiary);
  line-height: 1;
}

.filter-chip {
  max-width: 120px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.filter-divider {
  color: var(--border-strong);
}

.stats-chevron {
  flex-shrink: 0;
  color: var(--text-tertiary);
  opacity: 0.6;
}

/* ========================================
   Section Labels
   ======================================== */
.section {
  margin-bottom: var(--space-5);
}

.section-label {
  font-size: var(--text-sm);
  font-weight: var(--weight-semibold);
  color: var(--text-secondary);
  margin: 0 0 var(--space-3);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

/* ========================================
   iOS App Store Style Mode Cards
   ======================================== */
.mode-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.mode-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-4) var(--space-5);
  background: var(--bg-surface);
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-sm);
  cursor: pointer;
  transition:
    transform var(--duration-fast) var(--ease-spring),
    box-shadow var(--duration-fast) var(--ease-out);
}

.mode-card:hover {
  box-shadow: var(--shadow-md);
}

.mode-card:active {
  transform: scale(0.98);
}

.mode-card-left {
  display: flex;
  align-items: center;
  gap: var(--space-4);
  flex: 1;
  min-width: 0;
}

.mode-card-right {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.mode-icon {
  flex-shrink: 0;
  width: 48px;
  height: 48px;
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
}

.mode-icon-exam {
  background: rgba(99, 102, 241, 0.1);
  color: var(--c-primary);
}

.mode-icon-book {
  background: rgba(52, 199, 89, 0.1);
  color: var(--c-success);
}

.mode-icon-wrong {
  background: rgba(255, 59, 48, 0.1);
  color: var(--c-error);
}

.mode-card-text {
  flex: 1;
  min-width: 0;
}

.mode-card-title {
  font-size: var(--text-base);
  font-weight: var(--weight-semibold);
  margin: 0 0 2px;
  color: var(--text-primary);
}

.mode-card-desc {
  margin: 0;
  font-size: var(--text-sm);
  color: var(--text-secondary);
  line-height: 1.4;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.mode-chevron {
  flex-shrink: 0;
  color: var(--text-tertiary);
  opacity: 0.5;
}

.wrong-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 22px;
  height: 22px;
  padding: 0 7px;
  border-radius: var(--radius-full);
  background: var(--c-error);
  color: white;
  font-size: 12px;
  font-weight: var(--weight-semibold);
  line-height: 1;
}

/* ========================================
   Empty State
   ======================================== */
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: var(--space-12) var(--space-6);
  text-align: center;
}

.empty-icon-wrap {
  width: 72px;
  height: 72px;
  border-radius: var(--radius-xl);
  background: var(--bg-surface-secondary);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-tertiary);
  margin-bottom: var(--space-5);
}

.empty-title {
  font-size: var(--text-xl);
  font-weight: var(--weight-semibold);
  margin: 0 0 var(--space-2);
  color: var(--text-primary);
}

.empty-desc {
  font-size: var(--text-base);
  color: var(--text-secondary);
  margin: 0 0 var(--space-6);
}

/* ========================================
   Skeleton Loading
   ======================================== */
.skeleton-card {
  padding: var(--space-5);
  background: var(--bg-surface);
  border-radius: var(--radius-xl);
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  margin-bottom: var(--space-6);
}

.skeleton-line {
  height: 16px;
  background: var(--bg-surface-secondary);
  border-radius: var(--radius-sm);
  animation: shimmer 1.5s ease-in-out infinite;
}

.skeleton-line.w-32 {
  width: 160px;
}
.skeleton-line.w-48 {
  width: 240px;
}

@keyframes shimmer {
  0%,
  100% {
    opacity: 1;
  }
  50% {
    opacity: 0.4;
  }
}

/* ========================================
   Entrance Animations
   ======================================== */
.fade-in-delay-1 {
  animation: fadeSlideIn 0.4s var(--ease-out) both;
  animation-delay: 0.05s;
}

.fade-in-delay-2 {
  animation: fadeSlideIn 0.4s var(--ease-out) both;
  animation-delay: 0.1s;
}

.fade-in-delay-3 {
  animation: fadeSlideIn 0.4s var(--ease-out) both;
  animation-delay: 0.15s;
}

@keyframes fadeSlideIn {
  from {
    opacity: 0;
    transform: translateY(8px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

/* ========================================
   Footer Spacer
   ======================================== */
.footer-spacer {
  height: var(--space-8);
}
</style>
