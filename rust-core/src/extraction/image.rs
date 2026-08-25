use std::fs::File;
use std::io::BufReader;
use std::path::Path;
use serde::{Deserialize, Serialize};
use exif::{Reader, Tag, In};
use crate::utils::error_handler::Result;

#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct ImageMetadata {
    pub date_time_original: Option<String>,
    pub description: Option<String>,
    pub gps_latitude: Option<f64>,
    pub gps_longitude: Option<f64>,
    pub keywords: Vec<String>,
}

pub fn extract_image_exif(path: &Path) -> Result<ImageMetadata> {
    let mut meta = ImageMetadata::default();
    let file = match File::open(path) {
        Ok(f) => f,
        Err(_) => return Ok(meta),
    };

    let mut bufreader = BufReader::new(file);
    let exifreader = Reader::new();
    let exif_data = match exifreader.read_from_container(&mut bufreader) {
        Ok(e) => e,
        Err(_) => return Ok(meta),
    };

    if let Some(field) = exif_data.get_field(Tag::DateTimeOriginal, In::PRIMARY) {
        meta.date_time_original = Some(field.display_value().to_string());
    } else if let Some(field) = exif_data.get_field(Tag::DateTime, In::PRIMARY) {
        meta.date_time_original = Some(field.display_value().to_string());
    }

    if let Some(field) = exif_data.get_field(Tag::ImageDescription, In::PRIMARY) {
        meta.description = Some(field.display_value().to_string());
    }

    if let Some(field) = exif_data.get_field(Tag::UserComment, In::PRIMARY) {
        let comment = field.display_value().to_string();
        if !comment.is_empty() {
            meta.keywords.push(comment);
        }
    }

    Ok(meta)
}
