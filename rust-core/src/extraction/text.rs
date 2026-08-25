use std::fs::File;
use std::io::Read;
use std::path::Path;
use encoding_rs::WINDOWS_1252;
use crate::utils::error_handler::Result;

pub const MAX_TEXT_FILE_SIZE: u64 = 10 * 1024 * 1024; // 10 MB

pub fn read_text_file(path: &Path) -> Result<String> {
    let meta = std::fs::metadata(path)?;
    if meta.len() > MAX_TEXT_FILE_SIZE {
        return Ok(String::new());
    }

    let mut file = File::open(path)?;
    let mut buffer = Vec::with_capacity(meta.len() as usize);
    file.read_to_end(&mut buffer)?;

    // Try UTF-8 first
    if let Ok(s) = std::str::from_utf8(&buffer) {
        return Ok(s.to_string());
    }

    // Fallback to Windows-1252 (Latin-1 superset common in Brazil)
    let (cow, _encoding_used, _had_errors) = WINDOWS_1252.decode(&buffer);
    Ok(cow.into_owned())
}
