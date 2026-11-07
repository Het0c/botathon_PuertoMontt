#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]
use serde::{Deserialize, Serialize};
use std::sync::Mutex;
use tauri::Manager;
use tauri_plugin_shell::{
    process::{CommandChild, CommandEvent},
    ShellExt,
};

#[derive(Clone, Serialize)]
struct Connection {
    port: u16,
    token: String,
}
#[derive(Deserialize)]
struct Ready {
    ready: bool,
    port: u16,
}
struct Backend {
    connection: Mutex<Option<Connection>>,
    child: Mutex<Option<CommandChild>>,
    error: Mutex<Option<String>>,
}

#[tauri::command]
fn get_connection(state: tauri::State<Backend>) -> Result<Connection, String> {
    if let Some(error) = state
        .error
        .lock()
        .map_err(|_| "Estado de error bloqueado")?
        .clone()
    {
        return Err(error);
    }
    state
        .connection
        .lock()
        .map_err(|_| "Estado bloqueado")?
        .clone()
        .ok_or_else(|| "Servicio iniciando".into())
}

fn main() {
    let app = tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_fs::init())
        .manage(Backend {
            connection: Mutex::new(None),
            child: Mutex::new(None),
            error: Mutex::new(None),
        })
        .invoke_handler(tauri::generate_handler![get_connection])
        .setup(|app| {
            let data_dir = app.path().app_data_dir()?;
            std::fs::create_dir_all(&data_dir)?;
            let token = uuid::Uuid::new_v4().to_string();
            let (mut rx, child) = app
                .shell()
                .sidecar("botathon-api")?
                .args([
                    "--port",
                    "0",
                    "--data-dir",
                    data_dir.to_str().ok_or("Ruta no UTF-8")?,
                ])
                .env("BOTATHON_TOKEN", &token)
                .spawn()?;
            *app.state::<Backend>()
                .child
                .lock()
                .map_err(|_| "Estado bloqueado")? = Some(child);
            let handle = app.handle().clone();
            tauri::async_runtime::spawn(async move {
                while let Some(event) = rx.recv().await {
                    match event {
                        CommandEvent::Stdout(bytes) => {
                            if let Ok(ready) = serde_json::from_slice::<Ready>(&bytes) {
                                if ready.ready {
                                    *handle.state::<Backend>().connection.lock().unwrap() =
                                        Some(Connection {
                                            port: ready.port,
                                            token: token.clone(),
                                        });
                                }
                            }
                        }
                        CommandEvent::Terminated(_) | CommandEvent::Error(_) => {
                            *handle.state::<Backend>().error.lock().unwrap() = Some(
                                "El servicio SQLite se detuvo. Reinicia la aplicación.".into(),
                            );
                            break;
                        }
                        _ => {}
                    }
                }
            });
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("No se pudo iniciar Cada hora cuenta");
    app.run(|handle, event| {
        if let tauri::RunEvent::Exit = event {
            if let Some(child) = handle.state::<Backend>().child.lock().unwrap().take() {
                let _ = child.kill();
            }
        }
    });
}
