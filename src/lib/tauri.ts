import type { Question, SyncConfig } from '../types/question'

// Mock mode: when running in browser without Tauri runtime (e.g. npm run dev on remote server)
const isMock = !window.__TAURI__

const STORAGE_KEY = 'pdf2exam_mock_bank'
const SYNC_CONFIG_KEY = 'pdf2exam_mock_sync'

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
    case 'set_sync_config': {
      localStorage.setItem(SYNC_CONFIG_KEY, JSON.stringify(args?.config))
      return Promise.resolve(true)
    }
    case 'get_sync_config': {
      const raw = localStorage.getItem(SYNC_CONFIG_KEY)
      return Promise.resolve(raw ? JSON.parse(raw) : null)
    }
    case 'sync_from_remote': {
      const raw = localStorage.getItem(SYNC_CONFIG_KEY)
      if (!raw) return Promise.reject(new Error('No sync config set'))
      const config: SyncConfig = JSON.parse(raw)
      // In mock mode, try a simple fetch
      return fetch(config.url).then(async (r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`)
        const data = await r.json()
        const questions: Question[] = Array.isArray(data) ? data : data.questions || []
        localStorage.setItem(STORAGE_KEY, JSON.stringify(questions))
        return questions
      })
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

export async function setSyncConfig(config: SyncConfig): Promise<boolean> {
  return invoke('set_sync_config', { config }) as Promise<boolean>
}

export async function getSyncConfig(): Promise<SyncConfig | null> {
  return invoke('get_sync_config') as Promise<SyncConfig | null>
}

export async function syncFromRemote(): Promise<Question[]> {
  return invoke('sync_from_remote') as Promise<Question[]>
}
