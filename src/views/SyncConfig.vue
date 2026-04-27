<template>
  <div class="settings-page page">
    <!-- iOS Standard Navigation Bar -->
    <div class="nav-bar">
      <button class="nav-back-btn" @click="$router.push('/')">
        <svg
          width="18"
          height="18"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2.5"
          stroke-linecap="round"
          stroke-linejoin="round"
        >
          <path d="M19 12H5M12 19l-7-7 7-7" />
        </svg>
        <span>返回</span>
      </button>
      <h1 class="nav-title">设置</h1>
      <div class="nav-spacer"></div>
    </div>

    <!-- Local import -->
    <div class="settings-group">
      <h2 class="group-header">本地导入</h2>
      <div class="group-card">
        <div class="group-row">
          <div class="group-row-content">
            <p class="group-row-desc">选择 JSON 文件导入，追加到本地题库</p>
            <button class="btn-row" @click="handleFileImport">
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
              选择文件
            </button>
          </div>
        </div>
        <div v-if="importMsg" :class="['group-result', importSuccess ? 'success' : 'error']">
          {{ importMsg }}
        </div>
      </div>
    </div>

    <!-- Remote sync -->
    <div class="settings-group">
      <h2 class="group-header">远程同步</h2>
      <div class="group-card">
        <div class="group-row">
          <div class="group-row-content">
            <p class="group-row-desc">同步将覆盖本地题库，支持 HTTP / WebDAV / S3</p>
            <div v-if="config" class="group-config">
              <div class="config-line">
                <span class="config-label">方式</span>
                <span class="config-value">{{ config.type.toUpperCase() }}</span>
              </div>
              <div class="config-line">
                <span class="config-label">链接</span>
                <span class="config-value config-url">{{ config.url }}</span>
              </div>
            </div>
            <p v-else class="group-row-desc muted">尚未配置远程同步</p>
          </div>
        </div>
        <div class="group-row group-row-actions">
          <button class="btn-row" @click="showDialog = true">
            {{ config ? '修改配置' : '添加配置' }}
          </button>
          <button
            v-if="config"
            class="btn-row btn-row-primary"
            @click="handleSync"
            :disabled="syncing"
          >
            {{ syncing ? '同步中…' : '开始同步' }}
          </button>
        </div>
        <div v-if="syncMsg" :class="['group-result', syncSuccess ? 'success' : 'error']">
          {{ syncMsg }}
        </div>
      </div>
    </div>

    <!-- Mock Exam Settings -->
    <div class="settings-group">
      <h2 class="group-header">模拟考试</h2>
      <div class="group-card">
        <div class="group-row group-row-justified">
          <span class="group-row-label">考试时长</span>
          <div class="stepper">
            <button class="stepper-btn" @click="changeDuration(-5)" :disabled="mockDuration <= 5">
              −
            </button>
            <span class="stepper-value">{{ mockDuration }} 分钟</span>
            <button class="stepper-btn" @click="changeDuration(5)" :disabled="mockDuration >= 180">
              +
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Danger zone -->
    <div class="settings-group">
      <h2 class="group-header">数据管理</h2>
      <div class="group-card">
        <button class="group-row group-row-destructive" @click="showConfirm = true">
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
            <polyline points="3 6 5 6 21 6" />
            <path d="M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2" />
          </svg>
          清空题库
        </button>
      </div>
    </div>

    <SyncDialog :show="showDialog" :existing="config" @close="handleDialogClose" />

    <!-- Confirm modal -->
    <div v-if="showConfirm" class="modal-overlay" @click.self="showConfirm = false">
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
        <p class="modal-text">确定要清空所有题目吗？此操作不可撤销。</p>
        <div class="modal-actions">
          <button class="btn-row" @click="showConfirm = false">取消</button>
          <button class="btn-row btn-row-destructive-action" @click="doClear">清空</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import type { SyncConfig, Question } from '../types/question'
import { getSyncConfig, clearQuestionBank } from '../lib/tauri'
import { useQuestionBank } from '../stores/questionBank'
import { useExam } from '../composables/useExam'
import SyncDialog from '../components/SyncDialog.vue'

const { syncRemote, load, count, importJson } = useQuestionBank()
const { resetSession } = useExam()

const MOCK_DURATION_KEY = 'mock_exam_duration'

const config = ref<SyncConfig | null>(null)
const showDialog = ref(false)
const syncing = ref(false)
const syncMsg = ref('')
const syncSuccess = ref(false)
const importMsg = ref('')
const importSuccess = ref(false)
const showConfirm = ref(false)
const mockDuration = ref(getSavedDuration())

function getSavedDuration(): number {
  try {
    const saved = localStorage.getItem(MOCK_DURATION_KEY)
    return saved ? Math.max(1, Math.min(180, parseInt(saved, 10) || 60)) : 60
  } catch {
    return 60
  }
}

function changeDuration(delta: number) {
  const next = mockDuration.value + delta
  if (next < 5 || next > 180) return
  mockDuration.value = next
  localStorage.setItem(MOCK_DURATION_KEY, String(next))
}

onMounted(async () => {
  config.value = await getSyncConfig()
})

function randomUUID(): string {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0
    const v = c === 'x' ? r : (r & 0x3) | 0x8
    return v.toString(16)
  })
}

async function handleFileImport() {
  importMsg.value = ''
  try {
    let content: string
    if (!window.__TAURI__) {
      const input = document.createElement('input')
      input.type = 'file'
      input.accept = '.json'
      const filePromise = new Promise<File | null>((resolve) => {
        input.onchange = () => resolve(input.files?.[0] ?? null)
      })
      input.click()
      const file = await filePromise
      if (!file) return
      content = await file.text()
    } else {
      const file = await window.__TAURI__.dialog.open({
        multiple: false,
        filters: [{ name: 'JSON', extensions: ['json'] }],
      })
      if (!file) return
      const filePath = typeof file === 'string' ? file : file.path
      content = await window.__TAURI__.fs.readTextFile(filePath)
    }
    const data = JSON.parse(content)
    let qs: Question[]
    if (Array.isArray(data)) {
      qs = data
    } else if (data.questions) {
      qs = data.questions
    } else {
      importMsg.value = 'JSON 格式不正确'
      return
    }
    for (const q of qs) {
      if (!q.id) q.id = randomUUID()
      if (!q.type) q.type = 'single'
      if (!q.options) q.options = {}
    }
    await importJson(qs)
    importSuccess.value = true
    importMsg.value = `导入成功！新增 ${qs.length} 道题目`
    resetSession()
  } catch (e: unknown) {
    importSuccess.value = false
    importMsg.value = e instanceof Error ? e.message : '导入失败'
  }
}

async function handleSync() {
  syncing.value = true
  syncMsg.value = ''
  try {
    await clearQuestionBank()
    await syncRemote()
    await load()
    resetSession()
    syncSuccess.value = true
    syncMsg.value = `同步成功！已更新 ${count.value} 道题目`
  } catch (e: unknown) {
    syncSuccess.value = false
    syncMsg.value = e instanceof Error ? e.message : '同步失败'
  } finally {
    syncing.value = false
  }
}

function handleDialogClose() {
  showDialog.value = false
  getSyncConfig().then((c) => {
    config.value = c
  })
}

function doClear() {
  showConfirm.value = false
  clearQuestionBank()
  load()
  resetSession()
}
</script>

<style scoped>
/* ========================================
   Page — override global .page top padding
   ======================================== */
.settings-page.page {
  padding-top: 0;
}

/* ========================================
   iOS Standard Navigation Bar
   ======================================== */
.nav-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 0 var(--space-3);
  min-height: 44px;
}

.nav-back-btn {
  display: flex;
  align-items: center;
  gap: 2px;
  background: none;
  border: none;
  color: var(--c-primary);
  font-size: var(--text-base);
  cursor: pointer;
  padding: var(--space-1) 0;
  min-height: 44px;
  transition: opacity var(--duration-fast) var(--ease-out);
}

.nav-back-btn:hover {
  opacity: 0.7;
}

.nav-back-btn span {
  font-size: var(--text-base);
}

.nav-title {
  font-size: var(--text-lg);
  font-weight: var(--weight-semibold);
  margin: 0;
  color: var(--text-primary);
  position: absolute;
  left: 50%;
  transform: translateX(-50%);
}

.nav-spacer {
  width: 60px;
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

/* Destructive row */
.group-row-destructive {
  color: var(--c-error);
  font-weight: var(--weight-medium);
}

.group-row-destructive:hover {
  background: rgba(255, 59, 48, 0.04);
}

.group-row-destructive:active {
  background: rgba(255, 59, 48, 0.08);
}

/* ========================================
   Confirmation Modal — iOS Alert Style
   ======================================== */
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

.modal-text {
  margin: 0 0 var(--space-5);
  font-size: var(--text-sm);
  color: var(--text-secondary);
  line-height: 1.5;
}

.modal-actions {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.modal-actions .btn-row {
  width: 100%;
  justify-content: center;
  padding: 12px;
  border-radius: var(--radius-md);
  min-height: 44px;
}

.btn-row-destructive-action {
  background: var(--c-error);
  border-color: var(--c-error);
  color: white;
}

.btn-row-destructive-action:hover {
  opacity: 0.9;
}
</style>
