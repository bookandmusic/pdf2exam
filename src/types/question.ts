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
  topic?: string
  chapter?: string
  section?: string
}

export interface Chapter {
  id: string
  name: string
}

export interface Subject {
  id: string
  name: string
  chapters: Chapter[]
  questions: Question[]
}

export interface FilterNode {
  id: string
  label: string
  count: number
  children?: FilterNode[]
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
