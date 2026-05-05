<template>
  <div class="settings-page">
    <!-- 固定顶部导航 -->
    <div class="sticky-header">
      <div class="header-content">
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
        <span class="header-title">设置</span>
        <div class="header-spacer"></div>
      </div>
    </div>

    <!-- 可滚动的设置内容 -->
    <div class="scrollable-content">
      <div class="settings-content-inner">
        <!-- Mock Exam Settings -->
        <div class="settings-group">
          <h2 class="group-header">模拟考试</h2>
          <div class="group-card">
            <div class="group-row group-row-justified">
              <span class="group-row-label">考试时长</span>
              <div class="stepper">
                <button
                  class="stepper-btn"
                  @click="changeDuration(-5)"
                  :disabled="mockDuration <= MIN_MOCK_DURATION"
                >
                  −
                </button>
                <label class="duration-input-wrap">
                  <input
                    v-model="mockDurationInput"
                    class="duration-input"
                    type="number"
                    inputmode="numeric"
                    :min="MIN_MOCK_DURATION"
                    :max="MAX_MOCK_DURATION"
                    step="5"
                    aria-label="考试时长（分钟）"
                    @blur="commitDurationInput"
                    @keydown.enter="commitDurationInput"
                  />
                  <span class="duration-suffix">分钟</span>
                </label>
                <button
                  class="stepper-btn"
                  @click="changeDuration(5)"
                  :disabled="mockDuration >= MAX_MOCK_DURATION"
                >
                  +
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'

const MOCK_DURATION_KEY = 'mock_exam_duration'
const MIN_MOCK_DURATION = 5
const MAX_MOCK_DURATION = 180
const DEFAULT_MOCK_DURATION = 120

const mockDuration = ref(getSavedDuration())
const mockDurationInput = ref(String(mockDuration.value))

function getSavedDuration(): number {
  try {
    const saved = localStorage.getItem(MOCK_DURATION_KEY)
    return saved
      ? clampDuration(parseInt(saved, 10) || DEFAULT_MOCK_DURATION)
      : DEFAULT_MOCK_DURATION
  } catch {
    return DEFAULT_MOCK_DURATION
  }
}

function clampDuration(value: number): number {
  return Math.max(MIN_MOCK_DURATION, Math.min(MAX_MOCK_DURATION, value))
}

function saveDuration(value: number) {
  const next = clampDuration(value)
  mockDuration.value = next
  mockDurationInput.value = String(next)
  localStorage.setItem(MOCK_DURATION_KEY, String(next))
}

function changeDuration(delta: number) {
  saveDuration(mockDuration.value + delta)
}

function commitDurationInput() {
  const parsed = parseInt(mockDurationInput.value, 10)
  if (Number.isNaN(parsed)) {
    mockDurationInput.value = String(mockDuration.value)
    return
  }
  saveDuration(parsed)
}
</script>

<style scoped>
/* 根容器：占满视口，禁止整体滚动 */
.settings-page {
  height: 100vh;
  overflow: hidden;
  position: relative;
  background: var(--bg-page);
}

/* 固定顶部导航 */
.sticky-header {
  flex-shrink: 0;
  background: var(--bg-page);
  border-bottom: 1px solid var(--border-default);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
  padding: 0 var(--space-4);
}

.header-content {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-3) 0;
  min-height: 56px;
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

.header-spacer {
  width: 60px;
}

/* 可滚动的设置内容 */
.scrollable-content {
  flex: 1;
  overflow-y: auto;
  padding: var(--space-4);
  -webkit-overflow-scrolling: touch;
}

.settings-content-inner {
  max-width: 800px;
  margin: 0 auto;
}

/* ========================================
    Settings Group — iOS Grouped Table Style
    ======================================== */
.settings-group {
  margin-bottom: var(--space-6);
}

.group-header {
  font-size: 13px;
  font-weight: var(--weight-semibold);
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin: 0 0 var(--space-2) var(--space-1);
  padding: 0;
}

.group-card {
  background: var(--bg-surface);
  border-radius: var(--radius-lg);
  overflow: hidden;
  box-shadow: var(--shadow-sm);
}

.group-row {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-4) var(--space-4);
  border: none;
  background: none;
  width: 100%;
  font: inherit;
  font-size: var(--text-base);
  color: var(--text-primary);
  text-align: left;
  cursor: pointer;
  min-height: 44px;
  transition: background var(--duration-fast) var(--ease-out);
}

.group-row:not(:last-child) {
  border-bottom: 1px solid var(--border-default);
}

.group-row:hover {
  background: var(--bg-surface-hover);
}

.group-row:active {
  background: var(--bg-surface-secondary);
}

.group-row-content {
  flex: 1;
  min-width: 0;
}

.group-row-desc {
  margin: 0 0 var(--space-3);
  font-size: var(--text-sm);
  color: var(--text-secondary);
  line-height: 1.5;
}

.group-row-desc.muted {
  margin-bottom: 0;
}

/* Config display */
.group-config {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.config-line {
  display: flex;
  gap: var(--space-2);
  font-size: var(--text-sm);
}

.config-label {
  color: var(--text-secondary);
  min-width: 36px;
  flex-shrink: 0;
}

.config-value {
  color: var(--text-primary);
}

.config-url {
  word-break: break-all;
}

/* Row buttons */
.group-row-actions {
  display: flex;
  gap: var(--space-2);
  flex-wrap: wrap;
  padding-top: var(--space-2);
  padding-bottom: var(--space-4);
  border-bottom: none;
}

.group-row-justified {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--space-3) var(--space-4);
}

.group-row-label {
  font-size: var(--text-base);
  color: var(--text-primary);
  font-weight: var(--weight-medium);
}

.stepper {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.duration-input-wrap {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  min-height: 40px;
  padding: 0 12px;
  border-radius: var(--radius-full);
  border: 1px solid var(--border-default);
  background: var(--bg-surface);
}

.duration-input {
  width: 56px;
  border: none;
  background: transparent;
  color: var(--text-primary);
  font-size: var(--text-base);
  font-weight: var(--weight-semibold);
  text-align: right;
  outline: none;
  font-variant-numeric: tabular-nums;
}

.duration-input::-webkit-outer-spin-button,
.duration-input::-webkit-inner-spin-button {
  -webkit-appearance: none;
  margin: 0;
}

.duration-input[type='number'] {
  -moz-appearance: textfield;
}

.duration-suffix {
  font-size: var(--text-sm);
  color: var(--text-secondary);
  white-space: nowrap;
}

.stepper-btn {
  width: 32px;
  height: 32px;
  border-radius: var(--radius-full);
  border: 1px solid var(--border-default);
  background: var(--bg-surface);
  color: var(--c-primary);
  font-size: 18px;
  font-weight: var(--weight-semibold);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all var(--duration-fast) var(--ease-out);
}

.stepper-btn:hover {
  background: var(--c-primary);
  color: white;
  border-color: var(--c-primary);
}

.stepper-btn:disabled {
  opacity: 0.3;
  cursor: not-allowed;
  background: var(--bg-surface);
  color: var(--text-tertiary);
  border-color: var(--border-default);
}

.stepper-btn:active:not(:disabled) {
  transform: scale(0.9);
}

.stepper-value {
  font-size: var(--text-base);
  font-weight: var(--weight-semibold);
  color: var(--text-primary);
  min-width: 64px;
  text-align: center;
}

.btn-row {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  padding: 8px 16px;
  border-radius: var(--radius-sm);
  border: 1px solid var(--border-default);
  background: var(--bg-surface);
  color: var(--c-primary);
  font-size: var(--text-sm);
  font-weight: var(--weight-medium);
  cursor: pointer;
  min-height: 36px;
  transition: all var(--duration-fast) var(--ease-out);
  white-space: nowrap;
}

.btn-row:hover {
  background: var(--bg-surface-hover);
  border-color: var(--c-primary);
}

.btn-row:active {
  transform: scale(0.97);
}

.btn-row:disabled {
  opacity: 0.4;
  cursor: not-allowed;
  transform: none;
}

.btn-row-primary {
  background: var(--c-primary);
  border-color: var(--c-primary);
  color: white;
}

.btn-row-primary:hover {
  background: var(--c-primary-dark);
  border-color: var(--c-primary-dark);
}

/* Group result message */
.group-result {
  font-size: var(--text-sm);
  margin: 0 var(--space-4) var(--space-3);
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-sm);
}

.group-result.success {
  background: rgba(52, 199, 89, 0.08);
  color: var(--c-success);
}

.group-result.error {
  background: rgba(255, 59, 48, 0.08);
  color: var(--c-error);
}

@media (max-width: 640px) {
  .header-content {
    padding: var(--space-3);
  }

  .scrollable-content {
    padding: var(--space-3);
  }
}
</style>
