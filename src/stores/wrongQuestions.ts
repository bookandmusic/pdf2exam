import { ref, computed, watch } from 'vue'
import { useQuestionBank } from './questionBank'

interface WrongEntry {
  id: string
  consecutiveCorrect: number
}

const wrongIds = ref<WrongEntry[]>([])
const { currentSubjectIds } = useQuestionBank()

function storageKey(): string {
  const id = currentSubjectIds.value[0] || 'default'
  return `pdf2exam_wrong_questions_${id}`
}

function load() {
  try {
    const raw = localStorage.getItem(storageKey())
    wrongIds.value = raw ? JSON.parse(raw) : []
  } catch {
    wrongIds.value = []
  }
}

function save() {
  localStorage.setItem(storageKey(), JSON.stringify(wrongIds.value))
}

load()

watch(currentSubjectIds, () => {
  load()
})

export function useWrongQuestions() {
  const count = computed(() => wrongIds.value.length)

  function add(id: string) {
    if (wrongIds.value.some((e) => e.id === id)) return
    wrongIds.value.push({ id, consecutiveCorrect: 0 })
    save()
  }

  function remove(id: string) {
    wrongIds.value = wrongIds.value.filter((e) => e.id !== id)
    save()
  }

  function recordCorrect(id: string) {
    const entry = wrongIds.value.find((e) => e.id === id)
    if (entry) {
      entry.consecutiveCorrect++
      save()
    }
  }

  function resetCorrect(id: string) {
    const entry = wrongIds.value.find((e) => e.id === id)
    if (entry) {
      entry.consecutiveCorrect = 0
      save()
    }
  }

  function clear() {
    wrongIds.value = []
    save()
  }

  return { wrongIds, count, add, remove, recordCorrect, resetCorrect, clear }
}
