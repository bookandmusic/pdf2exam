use serde::{Deserialize, Serialize};
use std::fs;
use std::path::PathBuf;
use tauri::Manager;

const STORAGE_FILE: &str = "question_bank.json";
const SYNC_CONFIG_FILE: &str = "sync_config.json";

#[derive(Debug, Serialize, Deserialize)]
struct QuestionBank {
    questions: Vec<serde_json::Value>,
}

#[derive(Debug, Serialize, Deserialize)]
struct SyncConfig {
    #[serde(rename = "type")]
    sync_type: String,
    url: String,
    token: Option<String>,
    username: Option<String>,
    password: Option<String>,
    #[serde(rename = "accessKey")]
    access_key: Option<String>,
    #[serde(rename = "secretKey")]
    secret_key: Option<String>,
    region: Option<String>,
    bucket: Option<String>,
}

fn get_storage_path(app: &tauri::AppHandle) -> PathBuf {
    let app_dir = app.path().app_data_dir().expect("failed to get app data dir");
    if !app_dir.exists() {
        fs::create_dir_all(&app_dir).expect("failed to create app data dir");
    }
    app_dir.join(STORAGE_FILE)
}

fn get_sync_config_path(app: &tauri::AppHandle) -> PathBuf {
    let app_dir = app.path().app_data_dir().expect("failed to get app data dir");
    if !app_dir.exists() {
        fs::create_dir_all(&app_dir).expect("failed to create app data dir");
    }
    app_dir.join(SYNC_CONFIG_FILE)
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

#[tauri::command]
fn set_sync_config(app: tauri::AppHandle, config: SyncConfig) -> Result<bool, String> {
    let path = get_sync_config_path(&app);
    let content = serde_json::to_string_pretty(&config).map_err(|e| e.to_string())?;
    fs::write(&path, content).map_err(|e| e.to_string())?;
    Ok(true)
}

#[tauri::command]
fn get_sync_config(app: tauri::AppHandle) -> Option<SyncConfig> {
    let path = get_sync_config_path(&app);
    if path.exists() {
        let content = fs::read_to_string(&path).ok()?;
        serde_json::from_str(&content).ok()
    } else {
        None
    }
}

#[tauri::command]
async fn sync_from_remote(app: tauri::AppHandle) -> Result<Vec<serde_json::Value>, String> {
    let config = get_sync_config(app.clone()).ok_or("No sync config set".to_string())?;

    let client = reqwest::Client::builder()
        .build()
        .map_err(|e| e.to_string())?;

    let mut request = client.get(&config.url);

    match config.sync_type.as_str() {
        "http" => {
            if let Some(token) = &config.token {
                request = request.bearer_auth(token);
            }
        }
        "webdav" => {
            if let (Some(username), Some(password)) = (&config.username, &config.password) {
                request = request.basic_auth(username, Some(password));
            }
        }
        "s3" => {
            // S3 signature auth: for simplicity, use presigned URL or pass keys as headers
            // A full S3 implementation would use aws-sdk-s3 for proper signature generation
            if let (Some(access_key), Some(secret_key)) = (&config.access_key, &config.secret_key) {
                // For S3 compatible services that support simple auth headers
                request = request
                    .header("x-amz-access-key", access_key)
                    .header("x-amz-security-token", secret_key);
            }
            if let Some(region) = &config.region {
                request = request.header("x-amz-region", region);
            }
        }
        _ => return Err(format!("Unknown sync type: {}", config.sync_type)),
    }

    let response = request
        .send()
        .await
        .map_err(|e| format!("Failed to download: {}", e))?;

    if !response.status().is_success() {
        return Err(format!("HTTP error: {}", response.status()));
    }

    let body = response
        .text()
        .await
        .map_err(|e| format!("Failed to read response: {}", e))?;

    // Parse as JSON - support both array and object with questions field
    let parsed: serde_json::Value = serde_json::from_str(&body).map_err(|e| e.to_string())?;

    let questions = if parsed.is_array() {
        parsed.as_array().unwrap().clone()
    } else if let Some(qs) = parsed.get("questions") {
        qs.as_array().unwrap().clone()
    } else {
        return Err("Invalid JSON format: expected array or object with 'questions' field".to_string());
    };

    // Import to local storage
    let path = get_storage_path(&app);
    let mut bank = load_storage_file(&path);
    bank.questions.extend(questions.clone());
    save_storage_file(&path, &bank);

    Ok(questions)
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
            delete_question,
            set_sync_config,
            get_sync_config,
            sync_from_remote
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
