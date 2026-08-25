use std::path::Path;
use std::sync::atomic::{AtomicBool, Ordering};
use serde::{Deserialize, Serialize};
use walkdir::WalkDir;
use crate::utils::error_handler::{IndexoError, Result};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ScanEntry {
    pub rel_path: String,
    pub abs_path: String,
    pub size: u64,
    pub mtime: i64,
    pub file_type: String,
    pub mime: String,
    pub is_cloud_placeholder: bool,
    pub is_hidden: bool,
}

pub fn detect_file_type(path: &Path) -> (String, String) {
    let ext = path
        .extension()
        .map(|e| e.to_string_lossy().to_lowercase())
        .unwrap_or_default();

    let mime = match ext.as_str() {
        "pdf" => "application/pdf".to_string(),
        "txt" | "log" | "ini" | "cfg" => "text/plain".to_string(),
        "md" => "text/markdown".to_string(),
        "csv" => "text/csv".to_string(),
        "json" => "application/json".to_string(),
        "html" | "htm" => "text/html".to_string(),
        "docx" => "application/vnd.openxmlformats-officedocument.wordprocessingml.document".to_string(),
        "doc" => "application/msword".to_string(),
        "odt" => "application/vnd.oasis.opendocument.text".to_string(),
        "xlsx" => "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet".to_string(),
        "xls" => "application/vnd.ms-excel".to_string(),
        "jpg" | "jpeg" => "image/jpeg".to_string(),
        "png" => "image/png".to_string(),
        "gif" => "image/gif".to_string(),
        "bmp" => "image/bmp".to_string(),
        "webp" => "image/webp".to_string(),
        "mp3" => "audio/mpeg".to_string(),
        "wav" => "audio/wav".to_string(),
        "ogg" => "audio/ogg".to_string(),
        "flac" => "audio/flac".to_string(),
        "mp4" => "video/mp4".to_string(),
        "mkv" => "video/x-matroska".to_string(),
        "avi" => "video/x-msvideo".to_string(),
        "mov" => "video/quicktime".to_string(),
        "zip" => "application/zip".to_string(),
        "rar" => "application/x-rar-compressed".to_string(),
        "7z" => "application/x-7z-compressed".to_string(),
        "exe" => "application/x-msdownload".to_string(),
        "dll" => "application/x-msdownload".to_string(),
        _ => {
            if let Ok(Some(kind)) = infer::get_from_path(path) {
                kind.mime_type().to_string()
            } else {
                "application/octet-stream".to_string()
            }
        }
    };

    let cat = match ext.as_str() {
        "pdf" | "docx" | "doc" | "odt" | "xlsx" | "xls" | "pptx" | "ppt" => "document",
        "txt" | "md" | "csv" | "log" | "json" | "html" | "htm" | "xml" | "py" | "rs" | "js" | "ts" => "text",
        "jpg" | "jpeg" | "png" | "gif" | "bmp" | "webp" | "svg" | "tiff" => "image",
        "mp3" | "wav" | "ogg" | "flac" | "aac" | "m4a" => "audio",
        "mp4" | "mkv" | "avi" | "mov" | "wmv" | "flv" | "webm" => "video",
        "exe" | "dll" | "msi" | "sys" | "bin" | "dat" => "binary",
        _ => {
            if mime.starts_with("image/") {
                "image"
            } else if mime.starts_with("audio/") {
                "audio"
            } else if mime.starts_with("video/") {
                "video"
            } else if mime.starts_with("text/") {
                "text"
            } else {
                "other"
            }
        }
    };

    (cat.to_string(), mime)
}

pub fn is_hidden_file(path: &Path) -> bool {
    if let Some(file_name) = path.file_name() {
        let name_str = file_name.to_string_lossy();
        if name_str.starts_with('.') || name_str.starts_with('$') {
            return true;
        }
    }

    #[cfg(windows)]
    {
        use std::os::windows::fs::MetadataExt;
        if let Ok(meta) = path.metadata() {
            const FILE_ATTRIBUTE_HIDDEN: u32 = 0x2;
            const FILE_ATTRIBUTE_SYSTEM: u32 = 0x4;
            let attrs = meta.file_attributes();
            if (attrs & FILE_ATTRIBUTE_HIDDEN != 0) || (attrs & FILE_ATTRIBUTE_SYSTEM != 0) {
                return true;
            }
        }
    }

    false
}

pub fn is_cloud_placeholder(path: &Path) -> bool {
    #[cfg(windows)]
    {
        use std::os::windows::fs::MetadataExt;
        if let Ok(meta) = path.metadata() {
            const FILE_ATTRIBUTE_REPARSE_POINT: u32 = 0x400;
            const FILE_ATTRIBUTE_RECALL_ON_DATA_ACCESS: u32 = 0x00400000;
            let attrs = meta.file_attributes();
            if (attrs & FILE_ATTRIBUTE_RECALL_ON_DATA_ACCESS != 0) || (attrs & FILE_ATTRIBUTE_REPARSE_POINT != 0) {
                return true;
            }
        }
    }
    let _ = path;
    false
}

pub fn scan_directory(
    root: &Path,
    include_hidden: bool,
    cancel_flag: Option<&AtomicBool>,
) -> Result<Vec<ScanEntry>> {
    let mut entries = Vec::new();
    let root_buf = root.to_path_buf();

    for entry_result in WalkDir::new(root)
        .follow_links(false)
        .into_iter()
        .filter_entry(|e| {
            let path = e.path();
            let name = e.file_name().to_string_lossy();

            // Never scan Indexo_Files, data, configs, $Recycle.Bin, System Volume Information
            if name == "Indexo_Files" || name == "$Recycle.Bin" || name == "System Volume Information" {
                return false;
            }

            if !include_hidden && is_hidden_file(path) && path != root {
                return false;
            }

            true
        })
    {
        if let Some(flag) = cancel_flag {
            if flag.load(Ordering::Relaxed) {
                return Err(IndexoError::Cancelled);
            }
        }

        let entry = match entry_result {
            Ok(e) => e,
            Err(_) => continue, // Skip unreadable entries gracefully (Access Denied)
        };

        if !entry.file_type().is_file() {
            continue;
        }

        let path = entry.path();
        let meta = match entry.metadata() {
            Ok(m) => m,
            Err(_) => continue,
        };

        let size = meta.len();
        let mtime = meta
            .modified()
            .ok()
            .and_then(|t| t.duration_since(std::time::UNIX_EPOCH).ok())
            .map(|d| d.as_secs() as i64)
            .unwrap_or(0);

        let rel_path = path
            .strip_prefix(&root_buf)
            .map(|p| p.to_string_lossy().replace('\\', "/"))
            .unwrap_or_else(|_| path.to_string_lossy().replace('\\', "/"));

        let abs_path = path.to_string_lossy().to_string();
        let (file_type, mime) = detect_file_type(path);
        let cloud = is_cloud_placeholder(path);
        let hidden = is_hidden_file(path);

        entries.push(ScanEntry {
            rel_path,
            abs_path,
            size,
            mtime,
            file_type,
            mime,
            is_cloud_placeholder: cloud,
            is_hidden: hidden,
        });
    }

    Ok(entries)
}
