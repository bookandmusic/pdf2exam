/// <reference types="vite/client" />

interface TauriCore {
  invoke: (command: string, args?: Record<string, unknown>) => Promise<unknown>
}

interface TauriDialog {
  open: (options?: Record<string, unknown>) => Promise<string | { path: string } | null>
}

interface TauriFs {
  readTextFile: (path: string) => Promise<string>
  writeTextFile: (path: string, content: string) => Promise<void>
}

interface TauriAPI {
  core: TauriCore
  dialog: TauriDialog
  fs: TauriFs
}

declare global {
  interface Window {
    __TAURI__: TauriAPI
  }
}
