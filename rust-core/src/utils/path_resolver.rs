use std::path::{Path, PathBuf};
use crate::utils::error_handler::{IndexoError, Result};

pub fn get_app_dir() -> PathBuf {
    if let Ok(exe_path) = std::env::current_exe() {
        if let Some(parent) = exe_path.parent() {
            return parent.to_path_buf();
        }
    }
    std::env::current_dir().unwrap_or_else(|_| PathBuf::from("."))
}

pub fn get_data_dir() -> PathBuf {
    get_app_dir().join("data")
}

pub fn get_configs_dir() -> PathBuf {
    get_app_dir().join("configs")
}

pub fn get_db_path() -> PathBuf {
    get_data_dir().join("indexo.db")
}

pub fn validate_caminho_fisico(caminho: &str) -> Result<String> {
    let trimmed = caminho.trim();
    if trimmed.is_empty() {
        return Ok(String::new());
    }

    if trimmed.contains("..") {
        return Err(IndexoError::InvalidPath("Path traversal '..' detected in caminho_fisico".into()));
    }

    let path = Path::new(trimmed);
    if path.is_absolute() || trimmed.starts_with('/') || trimmed.starts_with('\\') {
        return Err(IndexoError::InvalidPath("Absolute path detected in caminho_fisico".into()));
    }

    if trimmed.contains(':') {
        return Err(IndexoError::InvalidPath("Drive letter detected in caminho_fisico".into()));
    }

    let invalid_chars = ['<', '>', ':', '"', '|', '?', '*'];
    for c in invalid_chars {
        if trimmed.contains(c) {
            return Err(IndexoError::InvalidPath(format!("Invalid character '{}' in caminho_fisico", c)));
        }
    }

    Ok(trimmed.replace('\\', "/"))
}
