<template>
  <Teleport to="body">
    <Transition name="drawer">
      <div v-if="visible" class="drawer-overlay" @click.self="close">
        <div class="drawer-panel" @click.stop>
          <div class="drawer-handle-bar">
            <div class="drawer-handle"></div>
          </div>

          <div class="drawer-header">
            <button class="drawer-header-btn" @click="reset">重置</button>
            <h2 class="drawer-title">筛选条件</h2>
            <button class="drawer-header-btn drawer-header-btn-primary" @click="close">完成</button>
          </div>

          <div class="drawer-body">
            <div class="drawer-section">
              <h3 class="drawer-section-title">科目</h3>
              <div class="drawer-list">
                <button
                  v-for="s in subjects"
                  :key="s.id"
                  :class="['drawer-item', { checked: selectedSubject === s.id }]"
                  @click="$emit('select-subject', s.id)"
                >
                  <div class="drawer-item-left">
                    <span :class="['radio-box', { checked: selectedSubject === s.id }]">
                      <span v-if="selectedSubject === s.id" class="radio-dot"></span>
                    </span>
                    <span class="drawer-item-text">{{ s.name }}</span>
                  </div>
                  <span class="drawer-item-count">{{ s.questions.length }}题</span>
                </button>
              </div>
            </div>

            <div v-if="filterTree.length > 0" class="drawer-section">
              <h3 class="drawer-section-title">章节</h3>
              <div class="drawer-list">
                <button
                  :class="['drawer-item', { checked: noFilter }]"
                  @click="$emit('clear-filters')"
                >
                  <div class="drawer-item-left">
                    <span :class="['check-box', { checked: noFilter }]">
                      <svg
                        v-if="noFilter"
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
                    <span class="drawer-item-text">全部</span>
                  </div>
                </button>

                <template v-for="topic in filterTree" :key="topic.id">
                  <button
                    :class="[
                      'drawer-item',
                      { checked: isChecked(topic.id), 'drawer-item-parent': true },
                    ]"
                    @click="$emit('toggle-section', topic.id)"
                  >
                    <div class="drawer-item-left">
                      <span class="expand-btn" @click.stop="toggleExpand(topic.id)">
                        <svg
                          :class="[
                            'expand-icon',
                            { expanded: expanded.has(topic.id) && hasChildren(topic) },
                          ]"
                          width="14"
                          height="14"
                          viewBox="0 0 24 24"
                          fill="none"
                          stroke="currentColor"
                          stroke-width="2.5"
                          stroke-linecap="round"
                          stroke-linejoin="round"
                        >
                          <path v-if="hasChildren(topic)" d="M9 6l6 6-6 6" />
                        </svg>
                      </span>
                      <span
                        :class="[
                          'check-box',
                          { checked: isChecked(topic.id), indirect: isIndirect(topic.id) },
                        ]"
                      >
                        <svg
                          v-if="isChecked(topic.id) && !isIndirect(topic.id)"
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
                        <svg
                          v-if="isIndirect(topic.id)"
                          width="14"
                          height="14"
                          viewBox="0 0 24 24"
                          fill="none"
                          stroke="currentColor"
                          stroke-width="3"
                          stroke-linecap="round"
                          stroke-linejoin="round"
                        >
                          <rect x="5" y="10" width="14" height="4" rx="1" />
                        </svg>
                      </span>
                      <span class="drawer-item-text">{{ topic.label }}</span>
                    </div>
                    <span class="drawer-item-count">{{ topic.count }}题</span>
                  </button>

                  <template v-if="expanded.has(topic.id) && topic.children">
                    <div v-for="ch in topic.children" :key="ch.id">
                      <button
                        :class="['drawer-item', { checked: isChecked(ch.id) }]"
                        @click="$emit('toggle-section', ch.id)"
                      >
                        <div class="drawer-item-left">
                          <span class="expand-btn" @click.stop="toggleExpand(ch.id)">
                            <svg
                              :class="[
                                'expand-icon',
                                { expanded: expanded.has(ch.id) && hasChildren(ch) },
                              ]"
                              width="14"
                              height="14"
                              viewBox="0 0 24 24"
                              fill="none"
                              stroke="currentColor"
                              stroke-width="2.5"
                              stroke-linecap="round"
                              stroke-linejoin="round"
                            >
                              <path v-if="hasChildren(ch)" d="M9 6l6 6-6 6" />
                            </svg>
                          </span>
                          <span
                            :class="[
                              'check-box',
                              { checked: isChecked(ch.id), indirect: isIndirect(ch.id) },
                            ]"
                          >
                            <svg
                              v-if="isChecked(ch.id) && !isIndirect(ch.id)"
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
                            <svg
                              v-if="isIndirect(ch.id)"
                              width="14"
                              height="14"
                              viewBox="0 0 24 24"
                              fill="none"
                              stroke="currentColor"
                              stroke-width="3"
                              stroke-linecap="round"
                              stroke-linejoin="round"
                            >
                              <rect x="5" y="10" width="14" height="4" rx="1" />
                            </svg>
                          </span>
                          <span class="drawer-item-text">{{ ch.label }}</span>
                        </div>
                        <span class="drawer-item-count">{{ ch.count }}题</span>
                      </button>

                      <template v-if="expanded.has(ch.id) && ch.children">
                        <button
                          v-for="sec in ch.children"
                          :key="sec.id"
                          :class="['drawer-item', { checked: selectedIds.has(sec.id) }]"
                          @click="$emit('toggle-section', sec.id)"
                        >
                          <div class="drawer-item-left">
                            <span class="expand-btn-placeholder"></span>
                            <span :class="['check-box', { checked: selectedIds.has(sec.id) }]">
                              <svg
                                v-if="selectedIds.has(sec.id)"
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
                            <span class="drawer-item-text">{{ sec.label }}</span>
                          </div>
                          <span class="drawer-item-count">{{ sec.count }}题</span>
                        </button>
                      </template>
                    </div>
                  </template>
                </template>
              </div>
            </div>

            <div class="drawer-bottom-safe"></div>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import type { FilterNode } from '../types/question'

const props = defineProps<{
  visible: boolean
  subjects: { id: string; name: string; questions: { length: number } }[]
  filterTree: FilterNode[]
  selectedSubjectIds: string[]
  selectedSectionIds: string[]
}>()

const emit = defineEmits<{
  close: []
  'select-subject': [id: string]
  'toggle-section': [id: string]
  'clear-filters': []
  reset: []
}>()

const expanded = ref<Set<string>>(new Set())

const selectedSubject = computed(() => props.selectedSubjectIds[0] || null)
const selectedIds = computed(() => new Set(props.selectedSectionIds))
const noFilter = computed(() => props.selectedSectionIds.length === 0)

const implicitIds = computed(() => {
  const result = new Set<string>()
  for (const sid of props.selectedSectionIds) {
    const parts = sid.split('||')
    if (parts.length === 3) {
      result.add(`${parts[0]}||${parts[1]}`)
      result.add(parts[0])
    } else if (parts.length === 2) {
      result.add(parts[0])
    }
  }
  return result
})

function isChecked(id: string): boolean {
  return selectedIds.value.has(id) || implicitIds.value.has(id)
}

function isIndirect(id: string): boolean {
  return implicitIds.value.has(id) && !selectedIds.value.has(id)
}

function hasChildren(node: FilterNode): boolean {
  return !!node.children && node.children.length > 0
}

function toggleExpand(id: string) {
  const s = new Set(expanded.value)
  if (s.has(id)) s.delete(id)
  else s.add(id)
  expanded.value = s
}

function close() {
  emit('close')
}
function reset() {
  emit('reset')
}
</script>

<style scoped>
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
.drawer-body {
  overflow-y: auto;
  -webkit-overflow-scrolling: touch;
  padding: 0 var(--space-5);
  flex: 1;
}
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
.drawer-item-text {
  font-size: var(--text-base);
  color: var(--text-primary);
  font-weight: var(--weight-medium);
}
.drawer-item-count {
  font-size: var(--text-sm);
  color: var(--text-tertiary);
  flex-shrink: 0;
  margin-left: var(--space-2);
}
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
.check-box.indirect {
  background: var(--c-primary);
  border-color: var(--c-primary);
  opacity: 0.6;
}
.radio-box {
  flex-shrink: 0;
  width: 22px;
  height: 22px;
  border-radius: var(--radius-full);
  border: 2px solid var(--border-strong);
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all var(--duration-fast) var(--ease-out);
}
.radio-box.checked {
  border-color: var(--c-primary);
}
.radio-dot {
  width: 12px;
  height: 12px;
  border-radius: var(--radius-full);
  background: var(--c-primary);
}
.expand-btn {
  flex-shrink: 0;
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  color: var(--text-tertiary);
  margin-left: calc(var(--space-1) * -1);
}
.expand-icon {
  transition: transform var(--duration-fast) var(--ease-out);
}
.expand-icon.expanded {
  transform: rotate(90deg);
}
.expand-btn-placeholder {
  flex-shrink: 0;
  width: 24px;
  height: 24px;
  margin-left: calc(var(--space-1) * -1);
}
.drawer-bottom-safe {
  height: env(safe-area-inset-bottom, 16px);
}
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
