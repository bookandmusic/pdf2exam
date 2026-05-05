import { ref, computed } from 'vue'
import type { Question, Subject, FilterNode } from '../types/question'
import { loadQuestionBank, importQuestions, clearQuestionBank, deleteQuestion } from '../lib/tauri'

const questions = ref<Question[]>([])
const isLoading = ref(false)
const error = ref<string | null>(null)

const subjects = ref<Subject[]>([])
const currentSubjectIds = ref<string[]>([])
const currentSectionIds = ref<string[]>([])

const STORAGE_SUBJECT_KEY = 'pdf2exam_subjects'
const STORAGE_SECTION_KEY = 'pdf2exam_sections'

try {
  const saved = localStorage.getItem(STORAGE_SUBJECT_KEY)
  if (saved) currentSubjectIds.value = JSON.parse(saved)
} catch {
  /* ignore */
}
try {
  const saved = localStorage.getItem(STORAGE_SECTION_KEY)
  if (saved) currentSectionIds.value = JSON.parse(saved)
} catch {
  /* ignore */
}

const filterTree = computed<FilterNode[]>(() => {
  const target =
    currentSubjectIds.value.length > 0
      ? subjects.value.filter((s) => currentSubjectIds.value.includes(s.id))
      : subjects.value
  const tree: FilterNode[] = []

  for (const s of target) {
    for (const ch of s.chapters) {
      const topicNode: FilterNode = { id: ch.id, label: ch.name, count: 0 }
      const chapterMap = new Map<string, FilterNode>()
      const sectionMap = new Map<string, number>()

      for (const q of s.questions) {
        if (q.chapterId !== ch.id) continue
        topicNode.count++

        if (q.chapter) {
          const chId = `${ch.id}||${q.chapter}`
          if (!chapterMap.has(chId)) {
            chapterMap.set(chId, { id: chId, label: q.chapter, count: 0 })
          }
          chapterMap.get(chId)!.count++

          if (q.section) {
            const secId = `${ch.id}||${q.chapter}||${q.section}`
            sectionMap.set(secId, (sectionMap.get(secId) || 0) + 1)
            const chNode = chapterMap.get(chId)!
            if (!chNode.children) chNode.children = []
            const existing = chNode.children.find((n) => n.id === secId)
            if (!existing) {
              chNode.children.push({ id: secId, label: q.section, count: 0 })
            }
            chNode.children.find((n) => n.id === secId)!.count++
          }
        }
      }

      if (chapterMap.size > 0) {
        topicNode.children = Array.from(chapterMap.values())
        for (const c of topicNode.children) {
          if (c.children) {
            const seen = new Map<string, FilterNode>()
            for (const sec of c.children) {
              seen.set(sec.id, sec)
            }
            c.children = Array.from(seen.values())
          }
        }
      }

      tree.push(topicNode)
    }
  }

  return tree
})

const filteredQuestions = computed<Question[]>(() => {
  if (subjects.value.length > 0) {
    const target =
      currentSubjectIds.value.length > 0
        ? subjects.value.filter((s) => currentSubjectIds.value.includes(s.id))
        : subjects.value
    let qs = target.flatMap((s) => s.questions)

    if (currentSectionIds.value.length > 0) {
      const l3 = new Set(currentSectionIds.value.filter((id) => id.split('||').length === 3))
      const l2 = new Set(currentSectionIds.value.filter((id) => id.split('||').length === 2))
      const l1 = new Set(currentSectionIds.value.filter((id) => id.split('||').length === 1))
      qs = qs.filter((q) => {
        if (l3.size > 0) {
          const key = `${q.chapterId || ''}||${q.chapter || ''}||${q.section || ''}`
          if (l3.has(key)) return true
        }
        if (l2.size > 0) {
          const key = `${q.chapterId || ''}||${q.chapter || ''}`
          if (l2.has(key)) return true
        }
        if (l1.size > 0) {
          if (q.chapterId && l1.has(q.chapterId)) return true
        }
        return false
      })
    }

    return qs
  }
  return questions.value
})

function saveSelection() {
  localStorage.setItem(STORAGE_SUBJECT_KEY, JSON.stringify(currentSubjectIds.value))
  localStorage.setItem(STORAGE_SECTION_KEY, JSON.stringify(currentSectionIds.value))
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
      const subjectFiles = [
        { id: 'patent-law', file: '专利法.json' },
        { id: 'related-law', file: '相关法.json' },
      ]
      const loaded: Subject[] = []
      for (const entry of subjectFiles) {
        const r = await fetch(`/subjects/${entry.file}`)
        if (!r.ok) continue
        const data = await r.json()
        data.id = entry.id
        if (data.questions) {
          for (const q of data.questions) {
            if (!q.chapterId) q.chapterId = 'default'
            q.chapterId = `${entry.id}-${q.chapterId}`
          }
        }
        if (data.chapters) {
          for (const ch of data.chapters) {
            ch.id = `${entry.id}-${ch.id}`
          }
        }
        loaded.push(data)
      }
      subjects.value = loaded
      currentSubjectIds.value = currentSubjectIds.value.filter((id) =>
        loaded.some((s) => s.id === id)
      )
      if (currentSubjectIds.value.length === 0 && loaded.length > 0) {
        currentSubjectIds.value = [loaded[0].id]
      }
      const allSectionIds = new Set<string>()
      for (const s of subjects.value) {
        for (const ch of s.chapters) allSectionIds.add(ch.id)
        for (const q of s.questions) {
          if (q.chapter) allSectionIds.add(`${q.chapterId}||${q.chapter}`)
          if (q.section) allSectionIds.add(`${q.chapterId}||${q.chapter}||${q.section}`)
        }
      }
      currentSectionIds.value = currentSectionIds.value.filter((id) => allSectionIds.has(id))
      saveSelection()
    } catch (e: unknown) {
      error.value = e instanceof Error ? e.message : String(e)
    } finally {
      isLoading.value = false
    }
  }

  function selectSubject(id: string) {
    currentSubjectIds.value = [id]
    currentSectionIds.value = currentSectionIds.value.filter((sid) =>
      subjects.value
        .find((s) => s.id === id)
        ?.questions.some((q) => sid.startsWith(q.chapterId || '') || sid === q.chapterId)
    )
    saveSelection()
  }

  function toggleSection(id: string) {
    const idx = currentSectionIds.value.indexOf(id)
    if (idx >= 0) {
      currentSectionIds.value.splice(idx, 1)
    } else {
      currentSectionIds.value.push(id)
    }
    saveSelection()
  }

  function clearFilters() {
    currentSectionIds.value = []
    saveSelection()
  }

  function resetFilters() {
    if (subjects.value.length > 0) {
      currentSubjectIds.value = [subjects.value[0].id]
    }
    currentSectionIds.value = []
    saveSelection()
  }

  return {
    questions,
    subjects,
    currentSubjectIds,
    currentSectionIds,
    filterTree,
    filteredQuestions,
    count,
    isLoading,
    error,
    load,
    importJson,
    clear,
    remove,
    loadBuiltinSubjects,
    selectSubject,
    toggleSection,
    clearFilters,
    resetFilters,
  }
}
