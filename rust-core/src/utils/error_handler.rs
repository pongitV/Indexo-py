use pyo3::exceptions::PyRuntimeError;
use pyo3::PyErr;
use std::fmt;

#[derive(Debug)]
pub enum IndexoError {
    Io(std::io::Error),
    Database(rusqlite::Error),
    Json(serde_json::Error),
    InvalidPath(String),
    Cancelled,
    Other(String),
}

impl fmt::Display for IndexoError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            IndexoError::Io(e) => write!(f, "IO error: {}", e),
            IndexoError::Database(e) => write!(f, "Database error: {}", e),
            IndexoError::Json(e) => write!(f, "JSON error: {}", e),
            IndexoError::InvalidPath(msg) => write!(f, "Invalid path: {}", msg),
            IndexoError::Cancelled => write!(f, "Operation cancelled by user"),
            IndexoError::Other(msg) => write!(f, "{}", msg),
        }
    }
}

impl std::error::Error for IndexoError {}

impl From<std::io::Error> for IndexoError {
    fn from(err: std::io::Error) -> Self {
        IndexoError::Io(err)
    }
}

impl From<rusqlite::Error> for IndexoError {
    fn from(err: rusqlite::Error) -> Self {
        IndexoError::Database(err)
    }
}

impl From<serde_json::Error> for IndexoError {
    fn from(err: serde_json::Error) -> Self {
        IndexoError::Json(err)
    }
}

impl From<IndexoError> for PyErr {
    fn from(err: IndexoError) -> Self {
        PyRuntimeError::new_err(err.to_string())
    }
}

pub type Result<T> = std::result::Result<T, IndexoError>;
