import { ref, computed } from 'vue'
import type { Question, Subject, SubjectMeta } from '../types/question'
import {
  loadQuestionBank,
  importQuestions,
  clearQuestionBank,
  deleteQuestion,
  syncFromRemote,
} from '../lib/tauri'

const questions = ref<Question[]>([])
const isLoading = ref(false)
const error = ref<string | null>(null)

const subjects = ref<Subject[]>([])
const currentSubjectIds = ref<string[]>([])
const currentChapterIds = ref<string[]>([])

const STORAGE_SUBJECT_KEY = 'pdf2exam_subjects'
const STORAGE_CHAPTER_KEY = 'pdf2exam_chapters'

// Restore last selection
try {
  const saved = localStorage.getItem(STORAGE_SUBJECT_KEY)
  if (saved) currentSubjectIds.value = JSON.parse(saved)
} catch {
  /* ignore */
}
try {
  const saved = localStorage.getItem(STORAGE_CHAPTER_KEY)
  if (saved) currentChapterIds.value = JSON.parse(saved)
} catch {
  /* ignore */
}

/** Chapters from currently selected subjects (or all subjects if none selected) */
const chapters = computed(() => {
  const target =
    currentSubjectIds.value.length > 0
      ? subjects.value.filter((s) => currentSubjectIds.value.includes(s.id))
      : subjects.value
  const map = new Map<string, { id: string; name: string; subjectName: string }>()
  for (const s of target) {
    for (const ch of s.chapters) {
      if (!map.has(ch.id)) {
        map.set(ch.id, { id: ch.id, name: ch.name, subjectName: s.name })
      }
    }
  }
  return Array.from(map.values())
})

const filteredQuestions = computed<Question[]>(() => {
  if (subjects.value.length > 0) {
    // Built-in subjects mode
    const target =
      currentSubjectIds.value.length > 0
        ? subjects.value.filter((s) => currentSubjectIds.value.includes(s.id))
        : subjects.value
    let qs = target.flatMap((s) => s.questions)
    if (currentChapterIds.value.length > 0) {
      qs = qs.filter((q) => q.chapterId && currentChapterIds.value.includes(q.chapterId))
    }
    return qs
  }
  // Fallback to Tauri questions
  return questions.value
})

function saveSelection() {
  localStorage.setItem(STORAGE_SUBJECT_KEY, JSON.stringify(currentSubjectIds.value))
  localStorage.setItem(STORAGE_CHAPTER_KEY, JSON.stringify(currentChapterIds.value))
}

export function useQuestionBank() {
  const count = computed(() => filteredQuestions.value.length)

  async function load() {
    isLoading.value = true
    error.value = null
    try {
      const data = await loadQuestionBank()
      questions.value = data
    } catch (e: unknown) {
      error.value = e instanceof Error ? e.message : String(e)
    } finally {
      isLoading.value = false
    }
  }

  async function importJson(jsonQuestions: Question[]) {
    await importQuestions(jsonQuestions)
    await load()
  }

  async function syncRemote() {
    isLoading.value = true
    error.value = null
    try {
      const data = await syncFromRemote()
      questions.value = data
    } catch (e: unknown) {
      error.value = e instanceof Error ? e.message : String(e)
      throw e
    } finally {
      isLoading.value = false
    }
  }

  async function clear() {
    await clearQuestionBank()
    questions.value = []
  }

  async function remove(questionId: string) {
    await deleteQuestion(questionId)
    questions.value = questions.value.filter((q) => q.id !== questionId)
  }

  async function loadBuiltinSubjects() {
    isLoading.value = true
    error.value = null
    try {
      const resp = await fetch('/subjects/index.json')
      if (!resp.ok) return
      const manifest: SubjectMeta[] = await resp.json()
      const loaded: Subject[] = []
      for (const m of manifest) {
        const r = await fetch(`/subjects/${m.file}`)
        if (!r.ok) continue
        const data = await r.json()
        data.questions?.forEach((q: Question) => {
          if (!q.chapterId) q.chapterId = 'default'
        })
        loaded.push(data)
      }
      subjects.value = loaded
      // Filter out saved subject IDs that no longer exist
      currentSubjectIds.value = currentSubjectIds.value.filter((id) =>
        loaded.some((s) => s.id === id)
      )
      // If none selected, select the first subject
      if (currentSubjectIds.value.length === 0 && loaded.length > 0) {
        currentSubjectIds.value = [loaded[0].id]
      }
      // Remove chapter IDs not in available chapters
      const allChapterIds = new Set(chapters.value.map((c) => c.id))
      currentChapterIds.value = currentChapterIds.value.filter((id) => allChapterIds.has(id))
      saveSelection()
    } catch (e: unknown) {
      error.value = e instanceof Error ? e.message : String(e)
    } finally {
      isLoading.value = false
    }
  }

  /** Toggle a subject on/off */
  function toggleSubject(id: string) {
    const idx = currentSubjectIds.value.indexOf(id)
    if (idx >= 0) {
      currentSubjectIds.value.splice(idx, 1)
      // Remove chapters that belonged only to this subject
      const subj = subjects.value.find((s) => s.id === id)
      if (subj) {
        const chIds = new Set(subj.chapters.map((c) => c.id))
        currentChapterIds.value = currentChapterIds.value.filter((cid) => !chIds.has(cid))
      }
    } else {
      currentSubjectIds.value.push(id)
    }
    saveSelection()
  }

  /** Toggle a chapter on/off */
  function toggleChapter(id: string) {
    const idx = currentChapterIds.value.indexOf(id)
    if (idx >= 0) {
      currentChapterIds.value.splice(idx, 1)
    } else {
      currentChapterIds.value.push(id)
    }
    saveSelection()
  }

  /** Clear all chapter filters */
  function clearChapters() {
    currentChapterIds.value = []
    saveSelection()
  }

  /** Reset all filters (select first subject, clear chapters) */
  function resetFilters() {
    if (subjects.value.length > 0) {
      currentSubjectIds.value = [subjects.value[0].id]
    }
    currentChapterIds.value = []
    saveSelection()
  }

  return {
    questions,
    subjects,
    currentSubjectIds,
    currentChapterIds,
    chapters,
    filteredQuestions,
    count,
    isLoading,
    error,
    load,
    importJson,
    syncRemote,
    clear,
    remove,
    loadBuiltinSubjects,
    toggleSubject,
    toggleChapter,
    clearChapters,
    resetFilters,
  }
}
