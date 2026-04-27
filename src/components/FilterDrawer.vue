<template>
  <Teleport to="body">
    <Transition name="drawer">
      <div v-if="visible" class="drawer-overlay" @click.self="close">
        <div class="drawer-panel" @click.stop>
          <!-- Drag handle -->
          <div class="drawer-handle-bar">
            <div class="drawer-handle"></div>
          </div>

          <!-- Header -->
          <div class="drawer-header">
            <button class="drawer-header-btn" @click="reset">重置</button>
            <h2 class="drawer-title">筛选条件</h2>
            <button class="drawer-header-btn drawer-header-btn-primary" @click="close">完成</button>
          </div>

          <div class="drawer-body">
            <!-- Subject Section -->
            <div class="drawer-section">
              <h3 class="drawer-section-title">科目</h3>
              <div class="drawer-list">
                <button
                  v-for="s in subjects"
                  :key="s.id"
                  :class="['drawer-item', { checked: selectedSubjects.has(s.id) }]"
                  @click="$emit('toggle-subject', s.id)"
                >
                  <div class="drawer-item-left">
                    <span :class="['check-box', { checked: selectedSubjects.has(s.id) }]">
                      <svg
                        v-if="selectedSubjects.has(s.id)"
                        width="14"
                        height="14"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        stroke-width="3"
                        stroke-linecap="round"
                        stroke-linejoin="round"
                      >
                        <path d="M20 6L9 17l-5-5" />
                      </svg>
                    </span>
                    <span class="drawer-item-text">{{ s.name }}</span>
                  </div>
                  <span class="drawer-item-count">{{ s.questions.length }}题</span>
                </button>
              </div>
            </div>

            <!-- Chapter Section -->
            <div v-if="chapters.length > 0" class="drawer-section">
              <h3 class="drawer-section-title">章节</h3>
              <div class="drawer-list">
                <button
                  :class="['drawer-item', { checked: selectedChapters.size === 0 }]"
                  @click="$emit('clear-chapters')"
                >
                  <div class="drawer-item-left">
                    <span :class="['check-box', { checked: selectedChapters.size === 0 }]">
                      <svg
                        v-if="selectedChapters.size === 0"
                        width="14"
                        height="14"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        stroke-width="3"
                        stroke-linecap="round"
                        stroke-linejoin="round"
                      >
                        <path d="M20 6L9 17l-5-5" />
                      </svg>
                    </span>
                    <span class="drawer-item-text">全部章节</span>
                  </div>
                </button>
                <button
                  v-for="ch in chapters"
                  :key="ch.id"
                  :class="['drawer-item', { checked: selectedChapters.has(ch.id) }]"
                  @click="$emit('toggle-chapter', ch.id)"
                >
                  <div class="drawer-item-left">
                    <span :class="['check-box', { checked: selectedChapters.has(ch.id) }]">
                      <svg
                        v-if="selectedChapters.has(ch.id)"
                        width="14"
                        height="14"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        stroke-width="3"
                        stroke-linecap="round"
                        stroke-linejoin="round"
                      >
                        <path d="M20 6L9 17l-5-5" />
                      </svg>
                    </span>
                    <span class="drawer-item-text">{{ ch.name }}</span>
                    <span v-if="ch.subjectName" class="drawer-item-subject">{{
                      ch.subjectName
                    }}</span>
                  </div>
                </button>
              </div>
            </div>

            <!-- Bottom safe area spacer -->
            <div class="drawer-bottom-safe"></div>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  visible: boolean
  subjects: { id: string; name: string; questions: { length: number } }[]
  chapters: { id: string; name: string; subjectName?: string }[]
  selectedSubjectIds: string[]
  selectedChapterIds: string[]
}>()

const emit = defineEmits<{
  close: []
  'toggle-subject': [id: string]
  'toggle-chapter': [id: string]
  'clear-chapters': []
  reset: []
}>()

const selectedSubjects = computed(() => new Set(props.selectedSubjectIds))
const selectedChapters = computed(() => new Set(props.selectedChapterIds))

function close() {
  emit('close')
}

function reset() {
  emit('reset')
}
</script>

<style scoped>
/* ========================================
   Overlay
   ======================================== */
.drawer-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.4);
  backdrop-filter: blur(2px);
  -webkit-backdrop-filter: blur(2px);
  display: flex;
  align-items: flex-end;
  z-index: 1000;
  animation: overlayIn 0.25s var(--ease-out) both;
}

@keyframes overlayIn {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}

/* ========================================
   Panel — iOS bottom sheet style
   ======================================== */
.drawer-panel {
  width: 100%;
  max-height: 85vh;
  background: var(--bg-page);
  border-radius: var(--radius-xl) var(--radius-xl) 0 0;
  display: flex;
  flex-direction: column;
  animation: panelSlideIn 0.35s var(--ease-spring) both;
  overflow: hidden;
}

@keyframes panelSlideIn {
  from {
    transform: translateY(100%);
  }
  to {
    transform: translateY(0);
  }
}

/* ========================================
   Drag Handle
   ======================================== */
.drawer-handle-bar {
  display: flex;
  justify-content: center;
  padding: var(--space-2) 0 0;
  flex-shrink: 0;
}

.drawer-handle {
  width: 36px;
  height: 5px;
  border-radius: var(--radius-full);
  background: var(--text-tertiary);
  opacity: 0.5;
}

/* ========================================
   Header
   ======================================== */
.drawer-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-3) var(--space-5) var(--space-2);
  flex-shrink: 0;
}

.drawer-title {
  font-size: var(--text-lg);
  font-weight: var(--weight-semibold);
  margin: 0;
}

.drawer-header-btn {
  background: none;
  border: none;
  font-size: var(--text-base);
  color: var(--text-secondary);
  cursor: pointer;
  padding: var(--space-1);
  min-height: 44px;
  transition: color var(--duration-fast) var(--ease-out);
}

.drawer-header-btn:hover {
  color: var(--text-primary);
}

.drawer-header-btn-primary {
  color: var(--c-primary);
  font-weight: var(--weight-semibold);
}

.drawer-header-btn-primary:hover {
  color: var(--c-primary-dark);
}

/* ========================================
   Body (scrollable)
   ======================================== */
.drawer-body {
  overflow-y: auto;
  -webkit-overflow-scrolling: touch;
  padding: 0 var(--space-5);
  flex: 1;
}

/* ========================================
   Section
   ======================================== */
.drawer-section {
  margin-bottom: var(--space-4);
}

.drawer-section-title {
  font-size: var(--text-sm);
  font-weight: var(--weight-semibold);
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin: 0 0 var(--space-2);
  padding: 0 var(--space-1);
}

/* ========================================
   List Items
   ======================================== */
.drawer-list {
  display: flex;
  flex-direction: column;
  gap: 1px;
  background: var(--border-default);
  border-radius: var(--radius-md);
  overflow: hidden;
}

.drawer-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-3) var(--space-4);
  background: var(--bg-surface);
  cursor: pointer;
  min-height: 48px;
  transition: background var(--duration-fast) var(--ease-out);
  -webkit-tap-highlight-color: transparent;
  border: none;
  width: 100%;
  font: inherit;
  font-size: var(--text-base);
  color: inherit;
  text-align: left;
}

.drawer-item:hover {
  background: var(--bg-surface-hover);
}

.drawer-item:active {
  background: var(--bg-surface-secondary);
}

.drawer-item-left {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  flex: 1;
  min-width: 0;
}

/* Checkbox */
.check-box {
  flex-shrink: 0;
  width: 22px;
  height: 22px;
  border-radius: var(--radius-sm);
  border: 2px solid var(--border-strong);
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all var(--duration-fast) var(--ease-out);
  color: white;
}

.check-box.checked {
  background: var(--c-primary);
  border-color: var(--c-primary);
}

.drawer-item-text {
  font-size: var(--text-base);
  color: var(--text-primary);
  font-weight: var(--weight-medium);
}

.drawer-item-subject {
  font-size: var(--text-xs);
  color: var(--text-tertiary);
  margin-left: var(--space-2);
  white-space: nowrap;
}

.drawer-item-count {
  font-size: var(--text-sm);
  color: var(--text-tertiary);
  flex-shrink: 0;
  margin-left: var(--space-2);
}

/* ========================================
   Bottom safe area
   ======================================== */
.drawer-bottom-safe {
  height: env(safe-area-inset-bottom, 16px);
}

/* ========================================
   Transition
   ======================================== */
.drawer-enter-active {
  transition: opacity 0.25s var(--ease-out);
}

.drawer-leave-active {
  transition: opacity 0.2s var(--ease-out);
}

.drawer-enter-from,
.drawer-leave-to {
  opacity: 0;
}

.drawer-enter-from .drawer-panel,
.drawer-leave-to .drawer-panel {
  animation: none;
  transform: translateY(100%);
}

.drawer-leave-active .drawer-panel {
  animation: panelSlideOut 0.2s var(--ease-out) both;
}

@keyframes panelSlideOut {
  from {
    transform: translateY(0);
  }
  to {
    transform: translateY(100%);
  }
}
</style>
