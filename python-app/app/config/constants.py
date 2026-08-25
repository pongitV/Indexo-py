"""
Centralized Application Constants for Indexo.
Single Source of Truth for extensions, directories, buffer sizes, and limits.
"""

from typing import Set, Tuple

# Supported Extensions by Category
DOCUMENT_EXTENSIONS: Tuple[str, ...] = (
    ".pdf", ".docx", ".doc", ".odt", ".rtf", ".txt",
    ".xlsx", ".xls", ".ods", ".csv",
    ".pptx", ".ppt", ".odp"
)

IMAGE_EXTENSIONS: Tuple[str, ...] = (
    ".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif",
    ".tiff", ".tif", ".svg", ".ico", ".heic", ".heif"
)

TEXT_EXTENSIONS: Tuple[str, ...] = (
    ".txt", ".log", ".csv", ".json", ".md", ".py",
    ".rs", ".js", ".ts", ".html", ".css", ".xml",
    ".ini", ".cfg", ".yaml", ".yml", ".toml", ".sql"
)

AUDIO_EXTENSIONS: Tuple[str, ...] = (
    ".mp3", ".wav", ".flac", ".m4a", ".aac", ".ogg", ".wma"
)

VIDEO_EXTENSIONS: Tuple[str, ...] = (
    ".mp4", ".mkv", ".avi", ".mov", ".wmv", ".webm", ".flv"
)

ALL_KNOWN_EXTENSIONS: Set[str] = set(
    DOCUMENT_EXTENSIONS + IMAGE_EXTENSIONS + TEXT_EXTENSIONS + AUDIO_EXTENSIONS + VIDEO_EXTENSIONS
)

# Reserved Directories & Files
RESERVED_FOLDER_NAME: str = "Indexo_Files"
SYSTEM_IGNORE_FILES: Set[str] = {
    "desktop.ini", "thumbs.db", ".ds_store",
    "indexo.db", "indexo.db-wal", "indexo.db-shm", "indexo.log"
}

# Buffer & Preview Limits
MAX_PREVIEW_TEXT_BYTES: int = 8192
MAX_PREVIEW_PDF_DPI: int = 150
DEFAULT_CONFIDENCE_THRESHOLD: float = 0.40
HIGH_CONFIDENCE_THRESHOLD: float = 0.75
