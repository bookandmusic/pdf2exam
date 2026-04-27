import { createRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'
import { useQuestionBank } from '../stores/questionBank'
import { useExam } from '../composables/useExam'

const routes: RouteRecordRaw[] = [
  { path: '/', name: 'Home', component: () => import('../views/Home.vue') },
  {
    path: '/mock-exam',
    name: 'MockExam',
    component: () => import('../views/MockExam.vue'),
    meta: { requiresQuestions: true },
  },
  {
    path: '/sequential',
    name: 'SequentialPractice',
    component: () => import('../views/SequentialPractice.vue'),
    meta: { requiresQuestions: true },
  },
  {
    path: '/results',
    name: 'ExamResults',
    component: () => import('../views/ExamResults.vue'),
    meta: { requiresSession: true },
  },
  {
    path: '/review',
    name: 'QuestionReview',
    component: () => import('../views/QuestionReview.vue'),
    meta: { requiresSession: true },
  },
  {
    path: '/wrong',
    name: 'WrongReview',
    component: () => import('../views/WrongReview.vue'),
    meta: { requiresQuestions: true },
  },
  { path: '/settings', name: 'Settings', component: () => import('../views/SyncConfig.vue') },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to) => {
  const { filteredQuestions } = useQuestionBank()
  const { session } = useExam()

  if (to.meta.requiresQuestions && filteredQuestions.value.length === 0) {
    return { name: 'Home' }
  }
  if (to.meta.requiresSession && !session.value) {
    return { name: 'Home' }
  }
})

export default router
