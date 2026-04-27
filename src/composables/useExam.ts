import { ref, computed } from 'vue'
import type { Question, ExamSession, UserAnswer } from '../types/question'

const session = ref<ExamSession | null>(null)

function shuffle<T>(arr: T[]): T[] {
  const a = [...arr]
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1))
    ;[a[i], a[j]] = [a[j], a[i]]
  }
  return a
}

function checkAnswer(question: Question, selected: string | string[]): boolean {
  const type = question.type || 'single'
  if (type === 'multiple') {
    const correct = (question.answers || []).sort()
    const picked = (Array.isArray(selected) ? selected : [selected]).sort()
    return JSON.stringify(correct) === JSON.stringify(picked)
  }
  return selected === question.answer
}

export function useExam() {
  const currentQuestion = computed(() =>
    session.value ? session.value.questions[session.value.currentIndex] : null
  )
  const currentAnswer = computed(() =>
    session.value ? session.value.answers[session.value.currentIndex] : null
  )
  const progress = computed(() => {
    if (!session.value) return 0
    return (session.value.currentIndex + 1) / session.value.questions.length
  })
  const score = computed(() => {
    if (!session.value) return 0
    const correct = session.value.answers.filter((a) => a?.isCorrect).length
    return Math.round(correct * session.value.pointsPerQuestion)
  })
  const correctCount = computed(() =>
    session.value ? session.value.answers.filter((a) => a?.isCorrect).length : 0
  )
  const wrongCount = computed(() =>
    session.value ? session.value.answers.filter((a) => a && !a.isCorrect).length : 0
  )
  const wrongQuestions = computed(() => {
    const s = session.value
    if (!s) return []
    return s.questions.filter((_, i) => !s.answers[i]?.isCorrect)
  })

  function startMockExam(allQuestions: Question[]) {
    const shuffled = shuffle(allQuestions)
    const examQuestions = shuffled.slice(0, Math.min(100, shuffled.length))
    const n = examQuestions.length
    session.value = {
      mode: 'mock',
      questions: examQuestions,
      answers: new Array(n).fill(null),
      currentIndex: 0,
      isComplete: false,
      pointsPerQuestion: n > 0 ? 100 / n : 0,
    }
  }

  function startSequential(
    allQuestions: Question[],
    startIndex = 0,
    answers?: Array<UserAnswer | null>
  ) {
    const n = allQuestions.length
    session.value = {
      mode: 'sequential',
      questions: allQuestions,
      answers:
        answers && answers.length === n
          ? answers.map((answer) => (answer ? { ...answer } : null))
          : new Array(n).fill(null),
      currentIndex: Math.min(startIndex, n - 1),
      isComplete: false,
      pointsPerQuestion: 0,
    }
  }

  function submitAnswer(selected: string | string[]) {
    if (!session.value) return
    const q = session.value.questions[session.value.currentIndex]
    const isCorrect = checkAnswer(q, selected)
    session.value.answers[session.value.currentIndex] = {
      questionId: q.id,
      selected,
      correct: q.type === 'multiple' ? q.answers || [] : q.answer,
      isCorrect,
    }
  }

  function next() {
    if (!session.value) return
    if (session.value.currentIndex < session.value.questions.length - 1) {
      session.value.currentIndex++
    }
  }

  function prev() {
    if (!session.value) return
    if (session.value.currentIndex > 0) {
      session.value.currentIndex--
    }
  }

  function goTo(index: number) {
    if (!session.value) return
    if (index >= 0 && index < session.value.questions.length) {
      session.value.currentIndex = index
    }
  }

  function clearAnswer(index: number) {
    if (!session.value) return
    if (index >= 0 && index < session.value.answers.length) {
      session.value.answers[index] = null
    }
  }

  function endSession() {
    if (!session.value) return
    session.value.isComplete = true
  }

  function resetSession() {
    session.value = null
  }

  return {
    session,
    currentQuestion,
    currentAnswer,
    progress,
    score,
    correctCount,
    wrongCount,
    wrongQuestions,
    startMockExam,
    startSequential,
    submitAnswer,
    next,
    prev,
    goTo,
    clearAnswer,
    endSession,
    resetSession,
  }
}
