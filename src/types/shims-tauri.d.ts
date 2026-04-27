interface TauriDialog {
  open(options: {
    multiple?: boolean
    filters?: { name: string; extensions: string[] }[]
  }): Promise<string | { path: string } | null>
}

interface TauriFs {
  readTextFile(path: string): Promise<string>
}

interface TauriCore {
  invoke(command: string, args?: Record<string, unknown>): Promise<unknown>
}

interface TauriAPI {
  core: TauriCore
  dialog: TauriDialog
  fs: TauriFs
}

interface Window {
  __TAURI__?: TauriAPI
}
