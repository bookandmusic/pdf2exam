<template>
  <div class="score-summary glass-card">
    <div class="score-display">
      <div class="score-ring">
        <svg viewBox="0 0 120 120" class="score-svg">
          <circle
            cx="60"
            cy="60"
            r="54"
            fill="none"
            stroke="var(--bg-surface-secondary)"
            stroke-width="8"
          />
          <circle
            cx="60"
            cy="60"
            r="54"
            fill="none"
            stroke="var(--c-primary)"
            stroke-width="8"
            :stroke-dasharray="circumference"
            :stroke-dashoffset="dashOffset"
            stroke-linecap="round"
            transform="rotate(-90, 60, 60)"
          />
        </svg>
        <div class="score-value">
          <span class="score-num">{{ score }}</span>
          <span class="score-unit">分</span>
        </div>
      </div>
    </div>

    <div class="score-stats">
      <div class="stat">
        <span class="stat-num correct">{{ correctCount }}</span>
        <span class="stat-label">正确</span>
      </div>
      <div class="stat-divider"></div>
      <div class="stat">
        <span class="stat-num wrong">{{ wrongCount }}</span>
        <span class="stat-label">错误</span>
      </div>
      <div class="stat-divider"></div>
      <div class="stat">
        <span class="stat-num">{{ correctCount + wrongCount }}</span>
        <span class="stat-label">总题</span>
      </div>
    </div>

    <div class="score-actions">
      <button v-if="wrongCount > 0" class="btn btn-primary" @click="$emit('review')">
        查看错题解析
      </button>
      <button class="btn btn-ghost" @click="$emit('home')">返回首页</button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  score: number
  correctCount: number
  wrongCount: number
}>()

defineEmits<{ review: []; home: [] }>()

const circumference = 2 * Math.PI * 54
const dashOffset = computed(() => {
  const total = props.correctCount + props.wrongCount
  if (total === 0) return circumference
  return circumference * (1 - props.correctCount / total)
})
</script>

<style scoped>
.score-summary {
  padding: var(--space-8) var(--space-6);
  text-align: center;
  max-width: 420px;
  margin: 0 auto;
}

.score-display {
  display: flex;
  justify-content: center;
  margin-bottom: var(--space-6);
}

.score-ring {
  position: relative;
  width: 120px;
  height: 120px;
}

.score-svg {
  width: 120px;
  height: 120px;
}

.score-value {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}

.score-num {
  font-size: 38px;
  font-weight: var(--weight-bold);
  color: var(--c-primary-light);
  line-height: 1;
}

.score-unit {
  font-size: var(--text-sm);
  color: var(--text-tertiary);
  margin-top: 2px;
}

.score-stats {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-6);
  margin-bottom: var(--space-6);
}

.stat {
  text-align: center;
}

.stat-num {
  display: block;
  font-size: var(--text-2xl);
  font-weight: var(--weight-bold);
  line-height: 1.2;
}

.stat-num.correct {
  color: var(--c-success);
}
.stat-num.wrong {
  color: var(--c-error);
}

.stat-label {
  font-size: var(--text-xs);
  color: var(--text-tertiary);
}

.stat-divider {
  width: 1px;
  height: 36px;
  background: var(--border-default);
}

.score-actions {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}
</style>
