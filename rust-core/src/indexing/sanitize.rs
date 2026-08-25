use std::path::{Path, PathBuf};
use unicode_normalization::UnicodeNormalization;

const RESERVED_NAMES: &[&str] = &[
    "CON", "PRN", "AUX", "NUL",
    "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9",
    "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9"
];

pub fn is_reserved_windows_name(stem: &str) -> bool {
    let upper = stem.trim().to_uppercase();
    RESERVED_NAMES.contains(&upper.as_str())
}

pub fn sanitize_filename(filename: &str) -> String {
    let nfc_str: String = filename.nfc().collect();
    
    // Separate stem and extension by last '.'
    let (raw_stem, raw_ext) = if let Some(dot_idx) = nfc_str.rfind('.') {
        if dot_idx > 0 {
            (&nfc_str[..dot_idx], &nfc_str[dot_idx..])
        } else {
            (nfc_str.as_str(), "")
        }
    } else {
        (nfc_str.as_str(), "")
    };

    let invalid_chars = ['<', '>', ':', '"', '/', '\\', '|', '?', '*', '.'];
    let mut clean_stem = String::with_capacity(raw_stem.len());
    
    for c in raw_stem.chars() {
        if invalid_chars.contains(&c) || c.is_control() {
            clean_stem.push('-');
        } else if c == ' ' {
            clean_stem.push('-');
        } else {
            clean_stem.push(c);
        }
    }

    // Collapse multiple consecutive hyphens or spaces
    let mut collapsed = String::new();
    let mut last_was_dash = false;
    for c in clean_stem.chars() {
        if c == '-' {
            if !last_was_dash {
                collapsed.push('-');
                last_was_dash = true;
            }
        } else {
            collapsed.push(c);
            last_was_dash = false;
        }
    }

    // Trim trailing dots, spaces, or hyphens
    let mut trimmed = collapsed.trim_matches(|c| c == '.' || c == ' ' || c == '-').to_string();
    if trimmed.is_empty() {
        trimmed = "unnamed".to_string();
    }

    // Handle reserved Windows names
    if is_reserved_windows_name(&trimmed) {
        trimmed = format!("_{}", trimmed);
    }

    // Truncate stem to <= 120 chars
    if trimmed.chars().count() > 120 {
        trimmed = trimmed.chars().take(120).collect();
        trimmed = trimmed.trim_end_matches(|c| c == '.' || c == ' ' || c == '-').to_string();
    }

    let clean_ext = raw_ext.to_lowercase();
    format!("{}{}", trimmed, clean_ext)
}

pub fn resolve_collision(dest_dir: &Path, desired_filename: &str) -> PathBuf {
    let sanitized = sanitize_filename(desired_filename);
    let target_path = dest_dir.join(&sanitized);

    if !dest_dir.exists() {
        return target_path;
    }

    let existing_lower_entries: Vec<String> = if let Ok(entries) = std::fs::read_dir(dest_dir) {
        entries
            .filter_map(|e| e.ok())
            .map(|e| e.file_name().to_string_lossy().nfc().collect::<String>().to_lowercase())
            .collect()
    } else {
        Vec::new()
    };

    let target_nfc: String = sanitized.nfc().collect();
    let target_lower = target_nfc.to_lowercase();

    if !existing_lower_entries.contains(&target_lower) && !target_path.exists() {
        return target_path;
    }

    let (stem, ext) = if let Some(dot_idx) = sanitized.rfind('.') {
        if dot_idx > 0 {
            (&sanitized[..dot_idx], &sanitized[dot_idx..])
        } else {
            (sanitized.as_str(), "")
        }
    } else {
        (sanitized.as_str(), "")
    };

    let mut counter = 2;
    loop {
        let candidate_name = format!("{}_{}{}", stem, counter, ext);
        let candidate_nfc: String = candidate_name.nfc().collect();
        let candidate_lower = candidate_nfc.to_lowercase();

        if !existing_lower_entries.contains(&candidate_lower) && !dest_dir.join(&candidate_name).exists() {
            return dest_dir.join(candidate_name);
        }
        counter += 1;
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_sanitize_filename() {
        assert_eq!(sanitize_filename("Conta: Luz / AES <Sul>.pdf"), "Conta-Luz-AES-Sul.pdf");
        assert_eq!(sanitize_filename("CON.txt"), "_CON.txt");
        assert_eq!(sanitize_filename("  spaces  and...dots...  .doc"), "spaces-and-dots.doc");
    }

    #[test]
    fn test_resolve_collision() {
        let temp_dir = tempfile::tempdir().unwrap();
        let p1 = resolve_collision(temp_dir.path(), "test.txt");
        std::fs::write(&p1, "data1").unwrap();

        let p2 = resolve_collision(temp_dir.path(), "test.txt");
        assert_eq!(p2.file_name().unwrap(), "test_2.txt");
        std::fs::write(&p2, "data2").unwrap();

        // Case-insensitive test
        let p3 = resolve_collision(temp_dir.path(), "TEST.txt");
        assert_eq!(p3.file_name().unwrap(), "TEST_3.txt");
    }
}
