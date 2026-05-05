import type { Question } from '../types/question'

// Mock mode: when running in browser without Tauri runtime (e.g. npm run dev on remote server)
const isMock = !window.__TAURI__

const STORAGE_KEY = 'pdf2exam_mock_bank'
function mockInvoke(command: string, args?: Record<string, unknown>): Promise<unknown> {
  switch (command) {
    case 'load_question_bank': {
      const raw = localStorage.getItem(STORAGE_KEY)
      return Promise.resolve(raw ? JSON.parse(raw) : [])
    }
    case 'import_questions': {
      const raw = localStorage.getItem(STORAGE_KEY)
      const bank = raw ? JSON.parse(raw) : []
      bank.push(...(args?.questions as unknown[]))
      localStorage.setItem(STORAGE_KEY, JSON.stringify(bank))
      return Promise.resolve(true)
    }
    case 'clear_question_bank': {
      localStorage.removeItem(STORAGE_KEY)
      return Promise.resolve(true)
    }
    case 'delete_question': {
      const raw = localStorage.getItem(STORAGE_KEY)
      if (!raw) return Promise.resolve(true)
      const bank: Question[] = JSON.parse(raw)
      const filtered = bank.filter((q: Question) => q.id !== args?.questionId)
      localStorage.setItem(STORAGE_KEY, JSON.stringify(filtered))
      return Promise.resolve(true)
    }
    default:
      return Promise.reject(new Error(`Unknown command: ${command}`))
  }
}

const invoke = isMock ? mockInvoke : window.__TAURI__!.core.invoke

export async function loadQuestionBank(): Promise<Question[]> {
  return invoke('load_question_bank') as Promise<Question[]>
}

export async function importQuestions(questions: Question[]): Promise<boolean> {
  return invoke('import_questions', { questions }) as Promise<boolean>
}

export async function clearQuestionBank(): Promise<boolean> {
  return invoke('clear_question_bank') as Promise<boolean>
}

export async function deleteQuestion(questionId: string): Promise<boolean> {
  return invoke('delete_question', { questionId }) as Promise<boolean>
}
