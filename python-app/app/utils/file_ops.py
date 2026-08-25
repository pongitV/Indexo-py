import json
import os
import shutil
import stat
import unicodedata
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from loguru import logger
import send2trash

RESTORE_MAX_ENTRIES = 2000

def normalize_nfc(text: str) -> str:
    return unicodedata.normalize("NFC", text)

def get_restore_path(root_dir: Path) -> Path:
    return root_dir / ".indexo_restore.json"

def get_file_attributes(path: Path) -> int:
    try:
        return os.stat(path).st_file_attributes
    except Exception:
        return 0

def set_file_attributes(path: Path, attrs: int):
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        kernel32.SetFileAttributesW(str(path), attrs)
    except Exception:
        pass

def clear_readonly(path: Path):
    try:
        mode = os.stat(path).st_mode
        os.chmod(path, mode | stat.S_IWRITE)
    except Exception:
        pass

def append_restore_wal(root_dir: Path, src_rel: str, dest_rel: str, original_filename: str):
    """WAL-style incremental logging before moving files."""
    restore_file = get_restore_path(root_dir)
    data = []
    if restore_file.exists():
        try:
            with open(restore_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            logger.warning("Corrupted .indexo_restore.json detected: {}. Starting fresh.", e)
            data = []

    # Rotation if > 2000 entries
    if len(data) >= RESTORE_MAX_ENTRIES:
        old_file = root_dir / ".indexo_restore.old.json"
        try:
            shutil.copy2(restore_file, old_file)
            data = data[-(RESTORE_MAX_ENTRIES // 2):]
            logger.info("Rotated .indexo_restore.json to old archive.")
        except Exception:
            pass

    data.append({
        "src_rel": src_rel,
        "dest_rel": dest_rel,
        "original_name": original_filename,
        "timestamp": os.path.getmtime(root_dir) if root_dir.exists() else 0
    })

    try:
        with open(restore_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error("Failed to write to .indexo_restore.json: {}", e)

def move_file_safe(src: Path, dest: Path, root_dir: Path) -> bool:
    """Performs atomic move on same volume with attributes preservation and post-move verification."""
    if not src.exists():
        logger.error("Source file does not exist: {}", src)
        return False

    # Block cross-volume moves
    if src.drive != dest.drive:
        logger.error("Cross-volume move blocked: {} -> {}", src, dest)
        return False

    dest.parent.mkdir(parents=True, exist_ok=True)
    
    src_stat = src.stat()
    src_attrs = get_file_attributes(src)

    # Log WAL before moving
    try:
        src_rel = str(src.relative_to(root_dir)).replace("\\", "/")
    except ValueError:
        src_rel = str(src).replace("\\", "/")
    
    try:
        dest_rel = str(dest.relative_to(root_dir)).replace("\\", "/")
    except ValueError:
        dest_rel = str(dest).replace("\\", "/")

    append_restore_wal(root_dir, src_rel, dest_rel, src.name)

    # Execute move
    try:
        os.replace(src, dest)
    except Exception as e:
        logger.error("Failed to move file {} -> {}: {}", src, dest, e)
        return False

    # Post-move verification (auditoria)
    if not dest.exists():
        logger.critical("Post-move verification failed! Destination does not exist: {}", dest)
        return False

    dest_stat = dest.stat()
    if dest_stat.st_size != src_stat.st_size:
        logger.critical("Post-move size mismatch on {} (expected {}, got {})", dest, src_stat.st_size, dest_stat.st_size)
        return False

    # Re-apply attributes
    set_file_attributes(dest, src_attrs)
    logger.info("Moved successfully: {} -> {}", src_rel, dest_rel)
    return True

def move_folder_safe(src_dir: Path, dest_dir: Path, root_dir: Path) -> bool:
    """Performs atomic move of an entire folder (e.g. cohesive game/app bundle) with WAL logging for every internal file."""
    if not src_dir.exists() or not src_dir.is_dir():
        logger.error("Source directory does not exist: {}", src_dir)
        return False

    if src_dir.drive != dest_dir.drive:
        logger.error("Cross-volume move blocked: {} -> {}", src_dir, dest_dir)
        return False

    # 1. Log WAL for all files in this folder prior to moving
    for f in src_dir.rglob("*"):
        if f.is_file():
            try:
                src_file_rel = str(f.relative_to(root_dir)).replace("\\", "/")
            except ValueError:
                src_file_rel = str(f).replace("\\", "/")
            
            sub_rel = f.relative_to(src_dir)
            target_f = dest_dir / sub_rel
            try:
                dest_file_rel = str(target_f.relative_to(root_dir)).replace("\\", "/")
            except ValueError:
                dest_file_rel = str(target_f).replace("\\", "/")

            append_restore_wal(root_dir, src_file_rel, dest_file_rel, f.name)

    dest_dir.parent.mkdir(parents=True, exist_ok=True)

    # 2. Execute move
    try:
        if dest_dir.exists():
            # If target directory exists, merge files
            for f in src_dir.rglob("*"):
                if f.is_file():
                    sub_rel = f.relative_to(src_dir)
                    target = dest_dir / sub_rel
                    target.parent.mkdir(parents=True, exist_ok=True)
                    os.replace(f, target)
            shutil.rmtree(src_dir, ignore_errors=True)
        else:
            os.replace(src_dir, dest_dir)
    except Exception as e:
        logger.error("Failed to move folder {} -> {}: {}", src_dir, dest_dir, e)
        return False

    if not dest_dir.exists():
        logger.critical("Post-move verification failed! Destination folder does not exist: {}", dest_dir)
        return False

    logger.info("Folder moved successfully: {} -> {}", src_dir, dest_dir)
    return True

def restore_session(root_dir: Path) -> Tuple[int, List[str]]:
    """Restores files from .indexo_restore.json in reverse order."""
    restore_file = get_restore_path(root_dir)
    if not restore_file.exists():
        return (0, [])

    try:
        with open(restore_file, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        logger.error("Error reading restore file: {}", e)
        return (0, [f"Corrupted restore file: {e}"])

    restored_count = 0
    errors = []

    for entry in reversed(data):
        dest_rel = entry.get("dest_rel", "")
        src_rel = entry.get("src_rel", "")
        if not dest_rel or not src_rel:
            continue

        dest_full = root_dir / dest_rel
        src_full = root_dir / src_rel

        if not dest_full.exists():
            errors.append(f"File not found at destination: {dest_rel}")
            continue

        src_full.parent.mkdir(parents=True, exist_ok=True)
        try:
            os.replace(dest_full, src_full)
            restored_count += 1
            logger.info("Restored: {} -> {}", dest_rel, src_rel)
        except Exception as e:
            errors.append(f"Failed to restore {dest_rel}: {e}")

    try:
        restore_file.unlink(missing_ok=True)
    except Exception:
        pass

    # Clean up empty leftover directories in Indexo_Files bottom-up
    indexo_files_dir = root_dir / "Indexo_Files"
    if indexo_files_dir.exists():
        for dirpath, dirnames, filenames in os.walk(str(indexo_files_dir), topdown=False):
            p = Path(dirpath)
            try:
                if not os.listdir(p):
                    p.rmdir()
            except Exception:
                pass
        try:
            if not os.listdir(indexo_files_dir):
                indexo_files_dir.rmdir()
        except Exception:
            pass

    return (restored_count, errors)

def send_file_to_recycle_bin(path: Path) -> bool:
    """Sends file to Windows Recycle Bin via send2trash (FOF_ALLOWUNDO)."""
    if not path.exists():
        return False
    clear_readonly(path)
    try:
        send2trash.send2trash(str(path))
        logger.info("Sent to Recycle Bin: {}", path)
        return True
    except Exception as e:
        logger.error("Failed to send {} to Recycle Bin: {}", path, e)
        return False

def delete_file_permanently(path: Path) -> bool:
    """Permanently deletes a file from disk."""
    if not path.exists():
        return False
    clear_readonly(path)
    try:
        path.unlink(missing_ok=True)
        logger.info("Permanently deleted: {}", path)
        return True
    except Exception as e:
        logger.error("Failed to delete permanently {}: {}", path, e)
        return False
