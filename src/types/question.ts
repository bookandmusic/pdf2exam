export type QuestionType = 'single' | 'multiple'

export interface Question {
  id: string
  question: string
  options: Record<string, string>
  answer: string
  answers?: string[]
  type?: QuestionType
  knowledge?: string
  difficulty?: number
  chapterId?: string
}

export interface Chapter {
  id: string
  name: string
}

export interface SubjectMeta {
  id: string
  name: string
  file: string
  questionCount: number
}

export interface Subject {
  id: string
  name: string
  chapters: Chapter[]
  questions: Question[]
}

export interface ExamPaper {
  id: string
  name: string
  questions: Question[]
  createdAt: string
}

export interface UserAnswer {
  questionId: string
  selected: string | string[]
  correct: string | string[]
  isCorrect: boolean
}

export type StudyMode = 'mock' | 'sequential'

export interface ExamSession {
  mode: StudyMode
  questions: Question[]
  answers: Array<UserAnswer | null>
  currentIndex: number
  isComplete: boolean
  pointsPerQuestion: number
}

export type SyncType = 'http' | 'webdav' | 's3'

export interface SyncConfig {
  type: SyncType
  url: string
  token?: string
  username?: string
  password?: string
  accessKey?: string
  secretKey?: string
  region?: string
  bucket?: string
}
