use serde::{Deserialize, Serialize};
use std::fs;
use std::path::PathBuf;
use tauri::Manager;

const STORAGE_FILE: &str = "question_bank.json";

#[derive(Debug, Serialize, Deserialize)]
struct QuestionBank {
    questions: Vec<serde_json::Value>,
}

fn get_storage_path(app: &tauri::AppHandle) -> PathBuf {
    let app_dir = app.path().app_data_dir().expect("failed to get app data dir");
    if !app_dir.exists() {
        fs::create_dir_all(&app_dir).expect("failed to create app data dir");
    }
    app_dir.join(STORAGE_FILE)
}

fn load_storage_file(path: &PathBuf) -> QuestionBank {
    if path.exists() {
        let content = fs::read_to_string(path).expect("failed to read storage file");
        serde_json::from_str(&content).expect("failed to parse storage file")
    } else {
        QuestionBank {
            questions: Vec::new(),
        }
    }
}

fn save_storage_file(path: &PathBuf, bank: &QuestionBank) {
    let content = serde_json::to_string_pretty(bank).expect("failed to serialize storage");
    fs::write(path, content).expect("failed to write storage file");
}

#[tauri::command]
fn import_questions(app: tauri::AppHandle, questions: Vec<serde_json::Value>) -> bool {
    let path = get_storage_path(&app);
    let mut bank = load_storage_file(&path);
    bank.questions.extend(questions);
    save_storage_file(&path, &bank);
    true
}

#[tauri::command]
fn load_question_bank(app: tauri::AppHandle) -> Vec<serde_json::Value> {
    let path = get_storage_path(&app);
    let bank = load_storage_file(&path);
    bank.questions
}

#[tauri::command]
fn clear_question_bank(app: tauri::AppHandle) -> bool {
    let path = get_storage_path(&app);
    let bank = QuestionBank {
        questions: Vec::new(),
    };
    save_storage_file(&path, &bank);
    true
}

#[tauri::command]
fn delete_question(app: tauri::AppHandle, question_id: String) -> bool {
    let path = get_storage_path(&app);
    let mut bank = load_storage_file(&path);
    bank.questions.retain(|q| {
        q.get("id").and_then(|v| v.as_str()) != Some(&question_id)
    });
    save_storage_file(&path, &bank);
    true
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_fs::init())
        .plugin(tauri_plugin_dialog::init())
        .invoke_handler(tauri::generate_handler![
            import_questions,
            load_question_bank,
            clear_question_bank,
            delete_question
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
