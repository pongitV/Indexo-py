use std::path::Path;
use serde::{Deserialize, Serialize};
use crate::utils::error_handler::Result;

#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct AudioMetadata {
    pub title: Option<String>,
    pub artist: Option<String>,
    pub album: Option<String>,
    pub year: Option<i32>,
}

pub fn extract_audio_meta(path: &Path) -> Result<AudioMetadata> {
    let mut meta = AudioMetadata::default();
    if let Some(stem) = path.file_stem() {
        meta.title = Some(stem.to_string_lossy().to_string());
    }
    Ok(meta)
}
