import { ref, computed, watch } from 'vue'
import type { Question, UserAnswer } from '../types/question'
import { useExam } from './useExam'

export function usePractice() {
  const exam = useExam()
  const { session, currentQuestion, currentAnswer, submitAnswer, next, prev, goTo, clearAnswer } =
    exam

  const pendingSelected = ref<string | string[]>('')
  const isEditingAnswered = ref(false)

  const selected = computed(() => {
    if (isEditingAnswered.value) return pendingSelected.value
    if (currentAnswer.value) return currentAnswer.value.selected
    return pendingSelected.value
  })

  const isAnswered = computed(() => !!currentAnswer.value)
  const showAnsweredState = computed(() => isAnswered.value && !isEditingAnswered.value)
  const isFirst = computed(() => (session.value?.currentIndex ?? 0) === 0)
  const isLast = computed(() => {
    if (!session.value) return true
    return session.value.currentIndex >= session.value.questions.length - 1
  })
  const currentIndex = computed(() => session.value?.currentIndex ?? 0)
  const totalQuestions = computed(() => session.value?.questions.length ?? 0)

  const nextButtonText = computed(() => {
    if (!showAnsweredState.value) return '确认答案'
    return isLast.value ? '完成' : '下一题'
  })

  watch(currentQuestion, () => {
    resetPendingSelection()
  })

  watch(currentAnswer, (newVal) => {
    if (newVal) {
      pendingSelected.value = Array.isArray(newVal.selected)
        ? [...newVal.selected]
        : newVal.selected
      isEditingAnswered.value = false
    }
  })

  function resetPendingSelection() {
    const q = currentQuestion.value
    if (currentAnswer.value) {
      pendingSelected.value = Array.isArray(currentAnswer.value.selected)
        ? [...currentAnswer.value.selected]
        : currentAnswer.value.selected
      isEditingAnswered.value = false
      return
    }
    isEditingAnswered.value = false
    pendingSelected.value = q?.type === 'multiple' ? [] : ''
  }

  function handleSelect(key: string) {
    const q = currentQuestion.value
    if (!q) return

    if ((q.type || 'single') === 'multiple') {
      const arr = Array.isArray(pendingSelected.value) ? [...pendingSelected.value] : []
      const idx = arr.indexOf(key)
      if (idx >= 0) arr.splice(idx, 1)
      else arr.push(key)
      pendingSelected.value = arr
    } else {
      pendingSelected.value = key
    }
  }

  function handleConfirm(): boolean {
    if (!session.value || !currentQuestion.value) return false
    const q = currentQuestion.value
    const type = q.type || 'single'

    if (type === 'multiple') {
      const arr = Array.isArray(pendingSelected.value) ? pendingSelected.value : []
      if (arr.length === 0) return false
      submitAnswer(arr)
    } else {
      if (!pendingSelected.value) return false
      submitAnswer(pendingSelected.value)
    }
    isEditingAnswered.value = false
    return true
  }

  function handleNext() {
    if (!session.value || !currentQuestion.value) return
    if (!showAnsweredState.value) {
      handleConfirm()
    } else if (!isLast.value) {
      next()
    }
  }

  function handlePrev() {
    prev()
  }

  function enableEditing() {
    if (!currentAnswer.value) return
    pendingSelected.value = Array.isArray(currentAnswer.value.selected)
      ? [...currentAnswer.value.selected]
      : currentAnswer.value.selected
    isEditingAnswered.value = true
  }

  function resetCurrentAnswer() {
    if (!session.value) return
    clearAnswer(session.value.currentIndex)
    resetPendingSelection()
  }

  function startSession(questions: Question[], startIndex = 0, answers?: Array<UserAnswer | null>) {
    exam.startSequential(questions, startIndex, answers)
    resetPendingSelection()
  }

  return {
    session,
    currentQuestion,
    currentAnswer,
    currentIndex,
    pendingSelected,
    selected,
    isAnswered,
    showAnsweredState,
    isEditingAnswered,
    isFirst,
    isLast,
    nextButtonText,
    totalQuestions,
    handleSelect,
    handleConfirm,
    handleNext,
    handlePrev,
    handleGoTo: goTo,
    next,
    prev,
    enableEditing,
    resetCurrentAnswer,
    startSession,
    resetSession: exam.resetSession,
    endSession: exam.endSession,
    submitAnswer: exam.submitAnswer,
  }
}
