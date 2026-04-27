<template>
  <div v-if="show" class="modal-overlay" @click.self="$emit('close')">
    <div class="sync-dialog glass-card">
      <div class="sync-header">
        <h3>远程同步配置</h3>
        <button class="close-btn" @click="$emit('close')" aria-label="关闭">
          <svg
            width="20"
            height="20"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            stroke-linecap="round"
            stroke-linejoin="round"
          >
            <path d="M18 6L6 18M6 6l12 12" />
          </svg>
        </button>
      </div>

      <div class="sync-body">
        <div class="form-group">
          <label>同步方式</label>
          <div class="type-selector">
            <button
              v-for="t in types"
              :key="t.value"
              :class="['type-btn', { active: form.type === t.value }]"
              @click="form.type = t.value"
            >
              {{ t.label }}
            </button>
          </div>
        </div>

        <div class="form-group">
          <label>下载链接</label>
          <input
            v-model="form.url"
            class="input"
            type="text"
            placeholder="https://example.com/questions.json"
          />
        </div>

        <template v-if="form.type === 'http'">
          <div class="form-group">
            <label>Bearer Token（可选）</label>
            <input v-model="form.token" class="input" type="password" placeholder="sk-xxx" />
          </div>
        </template>

        <template v-if="form.type === 'webdav'">
          <div class="form-group">
            <label>用户名</label>
            <input v-model="form.username" class="input" type="text" placeholder="username" />
          </div>
          <div class="form-group">
            <label>密码</label>
            <input v-model="form.password" class="input" type="password" placeholder="password" />
          </div>
        </template>

        <template v-if="form.type === 's3'">
          <div class="form-group">
            <label>Access Key</label>
            <input v-model="form.accessKey" class="input" type="text" placeholder="AKxxx" />
          </div>
          <div class="form-group">
            <label>Secret Key</label>
            <input v-model="form.secretKey" class="input" type="password" placeholder="SKxxx" />
          </div>
          <div class="form-row">
            <div class="form-group">
              <label>Region（可选）</label>
              <input v-model="form.region" class="input" type="text" placeholder="us-east-1" />
            </div>
            <div class="form-group">
              <label>Bucket（可选）</label>
              <input v-model="form.bucket" class="input" type="text" placeholder="my-bucket" />
            </div>
          </div>
        </template>

        <div v-if="errorMsg" class="error-msg" style="margin-top: var(--space-3)">
          {{ errorMsg }}
        </div>

        <div class="dialog-actions">
          <button class="btn btn-ghost" @click="$emit('close')">取消</button>
          <button class="btn btn-primary" @click="handleSave" :disabled="saving">
            {{ saving ? '保存中...' : '保存' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import type { SyncConfig, SyncType } from '../types/question'
import { setSyncConfig } from '../lib/tauri'

const props = defineProps<{ show: boolean; existing?: SyncConfig | null }>()
const emit = defineEmits<{ close: [] }>()

const types: { value: SyncType; label: string }[] = [
  { value: 'http', label: 'HTTP' },
  { value: 'webdav', label: 'WebDAV' },
  { value: 's3', label: 'S3' },
]

const form = reactive<SyncConfig>({
  type: props.existing?.type || 'http',
  url: props.existing?.url || '',
  token: props.existing?.token || '',
  username: props.existing?.username || '',
  password: props.existing?.password || '',
  accessKey: props.existing?.accessKey || '',
  secretKey: props.existing?.secretKey || '',
  region: props.existing?.region || '',
  bucket: props.existing?.bucket || '',
})

const saving = ref(false)
const errorMsg = ref('')

async function handleSave() {
  if (!form.url) {
    errorMsg.value = '请填写下载链接'
    return
  }
  errorMsg.value = ''
  saving.value = true
  try {
    await setSyncConfig(form)
    emit('close')
  } catch (e: unknown) {
    errorMsg.value = e instanceof Error ? e.message : '保存失败'
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
  padding: var(--space-4);
}

.sync-dialog {
  width: 100%;
  max-width: 480px;
  max-height: 80vh;
  overflow-y: auto;
  padding: var(--space-6);
}

.sync-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--space-5);
}

.sync-header h3 {
  margin: 0;
  font-size: var(--text-lg);
}

.close-btn {
  background: none;
  border: none;
  color: var(--text-secondary);
  cursor: pointer;
  padding: var(--space-1);
  display: flex;
  align-items: center;
  border-radius: var(--radius-sm);
  transition: color var(--duration-fast) var(--ease-out);
}

.close-btn:hover {
  color: var(--text-primary);
}

.form-group {
  margin-bottom: var(--space-4);
}

.form-group label {
  display: block;
  font-size: var(--text-sm);
  color: var(--text-secondary);
  margin-bottom: var(--space-2);
}

.form-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-3);
}

.type-selector {
  display: flex;
  gap: var(--space-2);
}

.type-btn {
  flex: 1;
  min-height: 44px;
  padding: 10px;
  border-radius: var(--radius-sm);
  border: 1px solid var(--border-default);
  background: transparent;
  color: var(--text-secondary);
  font-size: var(--text-sm);
  cursor: pointer;
  transition: all var(--duration-fast) var(--ease-out);
}

.type-btn.active {
  background: var(--c-primary);
  color: white;
  border-color: var(--c-primary);
}

.dialog-actions {
  display: flex;
  gap: var(--space-3);
  justify-content: flex-end;
  margin-top: var(--space-5);
}
</style>
