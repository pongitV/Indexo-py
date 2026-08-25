import os
import time
import re
from pathlib import Path
from typing import Dict, List, Any, Optional
from PySide6.QtCore import QThread, Signal
from loguru import logger
import indexo_core

from app.config.settings_manager import SettingsManager, get_db_path
from app.i18n.language_manager import tr
from app.classification.rule_loader import RuleLoader
from app.classification.entity_regex import (
    extract_primary_date, extract_amount, extract_due_date, generate_standard_filename
)
from app.classification.regex_rules import extract_identifiers
from app.extraction.pdf_extractor import extract_pdf_text_and_meta
from app.extraction.doc_extractor import extract_document_text
from app.extraction.ocr_engine import ocr_scanned_pdf
from app.classification.similarity_engine import SimilarityEngine, CohesiveBundle

BATCH_COMMIT_SIZE = 500

class IndexWorker(QThread):
    # Signals
    progress_changed = Signal(int, int, str)  # current, total, current_file
    file_classified = Signal(dict)           # stream classification result
    scan_finished = Signal(dict)             # summary stats
    error_occurred = Signal(str)

    def __init__(self, root_dir: Path, parent=None):
        super().__init__(parent)
        self.root_dir = root_dir
        self.is_cancelled = False
        self.settings_mgr = SettingsManager()
        self.rule_loader = RuleLoader()
        self.similarity_engine = SimilarityEngine()

    def cancel(self):
        self.is_cancelled = True

    def run(self):
        try:
            logger.info("Starting scan and classification on {}", self.root_dir)
            start_time = time.time()

            # 1. Initialize Rust DB and Kernel
            db_path = str(get_db_path())
            db = indexo_core.PyIndexoDatabase.open(db_path)
            
            root_abs = str(self.root_dir).replace("\\", "/")
            root_rel = self.root_dir.name
            root_id = db.get_or_create_root(root_abs, root_rel)

            kernel_json = self.rule_loader.build_kernel_json()
            kernel = indexo_core.PyClassificationKernel.from_rules_json(kernel_json)

            include_hidden = bool(self.settings_mgr.get("include_hidden", False))
            index_content = bool(self.settings_mgr.get("index_content", True))
            confidence_threshold = float(self.settings_mgr.get("confidence_threshold", 0.65))

            # 2. Phase 1: Scan directory
            self.progress_changed.emit(0, 0, "Scanning files...")
            entries = indexo_core.py_scan_directory(str(self.root_dir), include_hidden)
            total_files = len(entries)

            if self.is_cancelled:
                return

            logger.info("Scan discovered {} files in {:.2f}s", total_files, time.time() - start_time)

            # Phase 1.5: Hierarchical Analysis, Cohesive Bundle Detection & Dynamic Tag Discovery
            existing_user_tags = self.settings_mgr.get_user_tags()
            cohesive_bundles, file_to_bundle, discovered_tags = self.similarity_engine.analyze_scan_results(
                self.root_dir, entries, existing_user_tags
            )

            # Persist newly discovered tags with high confidence for future sessions
            for new_tag in discovered_tags:
                if float(new_tag.get("confianca_base", 0.0)) >= 0.85:
                    self.settings_mgr.add_user_tag(new_tag)

            all_tags = self.settings_mgr.get_user_tags()

            identified_count = 0
            pending_count = 0
            intruders_count = 0
            confirmed_count = 0
            results_stream = []

            # 3. Stream classification and extraction
            for idx, entry in enumerate(entries):
                if self.is_cancelled:
                    logger.info("Index worker cancelled by user at file {}/{}", idx, total_files)
                    return

                rel_path = entry["rel_path"]
                abs_path = entry["abs_path"]
                size = entry["size"]
                mtime = entry["mtime"]
                file_type = entry["file_type"]
                path_obj = Path(abs_path)
                ext = path_obj.suffix.lower()

                self.progress_changed.emit(idx + 1, total_files, rel_path)

                # Extract content based on file type ("type first")
                extracted_text = ""
                exif_data = {}
                is_scanned_pdf = False

                if file_type == "document":
                    if ext == ".pdf":
                        pdf_text, pdf_meta, is_scanned_pdf = extract_pdf_text_and_meta(path_obj)
                        if is_scanned_pdf and size < 50 * 1024 * 1024:
                            extracted_text = ocr_scanned_pdf(path_obj)
                        else:
                            extracted_text = pdf_text
                    elif ext in [".docx", ".odt"]:
                        extracted_text = extract_document_text(path_obj)
                elif file_type == "text":
                    try:
                        extracted_text = indexo_core.py_read_text_file(abs_path)
                    except Exception:
                        pass
                elif file_type == "image":
                    try:
                        exif_data = indexo_core.py_extract_image_exif(abs_path)
                        extracted_text = " ".join([
                            exif_data.get("description") or "",
                            " ".join(exif_data.get("keywords") or [])
                        ]).strip()
                    except Exception:
                        pass

                # Classification via Rust Kernel
                candidate = kernel.classify(extracted_text, ext, 0.0)

                # Check if this file belongs to a cohesive bundle
                parent_bundle = file_to_bundle.get(rel_path.replace("\\", "/"))

                # Match against active user & discovered tags
                matching_tag = None
                rel_parts = rel_path.replace("\\", "/").split("/")
                folder_parts = [p.lower() for p in rel_parts[:-1]]
                stem_lower = path_obj.stem.lower()

                for t in all_tags:
                    t_name = t.get("nome", "").lower()
                    t_kws = [k.lower() for k in t.get("palavras_chave", []) if k]
                    t_regexes = t.get("regex", [])

                    # Folder match
                    if folder_parts and any(
                        fp == t_name or fp.replace("_", " ") == t_name or fp in t.get("sinonimos", [])
                        for fp in folder_parts
                    ):
                        matching_tag = t
                        break

                    # Regex match
                    matched_re = False
                    for r in t_regexes:
                        try:
                            if re.search(r, stem_lower, re.IGNORECASE):
                                matched_re = True
                                break
                        except Exception:
                            pass
                    if matched_re:
                        matching_tag = t
                        break

                    # Keywords match
                    if t_kws and any(k in stem_lower for k in t_kws):
                        matching_tag = t
                        break
                    if extracted_text and t_kws and all(k in extracted_text.lower() for k in t_kws[:2]):
                        matching_tag = t
                        break

                # Hierarchical classification: Bundle -> Folder Hypothesis -> Discovered Tag -> Rule -> Media/Type
                hier_info = self.similarity_engine.classify_by_hierarchy(
                    rel_path, abs_path, file_type, extracted_text, candidate, parent_bundle, matching_tag
                )

                category = hier_info["category"]
                tag_name = hier_info["tag_name"]
                caminho_fisico = hier_info["caminho_fisico"]
                confidence = hier_info["confidence"]
                status = hier_info["status"]
                is_in_bundle = hier_info["is_in_bundle"]
                bundle_folder = hier_info["bundle_folder"]
                bundle_type = hier_info.get("bundle_type")
                is_intruder = hier_info.get("is_intruder", False)
                folder_status = hier_info.get("folder_status", "novo_agrupamento")
                origin_folder = hier_info.get("origin_folder", "")
                hierarchy_source = hier_info.get("hierarchy_source", "")

                # Calculate SHA-256 hash (incrementally / sized)
                file_hash = None
                try:
                    if size < 500 * 1024 * 1024:
                        file_hash = indexo_core.py_calculate_sha256(abs_path)
                except Exception:
                    pass

                type_translated = tr(f"type.{file_type}")

                # Primary date, amount and target filename
                primary_date = extract_primary_date(extracted_text, mtime)
                amount = extract_amount(extracted_text)
                due_date = extract_due_date(extracted_text)
                entity = candidate.get("entidade") if candidate else None

                rename_cfg = self.settings_mgr.data.get("configs", {})
                if is_in_bundle:
                    suggested_filename = path_obj.name
                else:
                    suggested_filename = generate_standard_filename(
                        primary_date,
                        entity,
                        tag_name or type_translated,
                        ext,
                        path_obj.stem,
                        rename_cfg,
                        amount=amount
                    )

                scores = candidate.get("scores", {"conteudo": 0.0, "tipo": 0.0, "origem": 0.0}) if candidate else {"conteudo": 0.0, "tipo": 0.0, "origem": 0.0}

                if status == "identificado":
                    identified_count += 1
                else:
                    pending_count += 1

                if is_intruder:
                    intruders_count += 1
                elif folder_status == "confirmado":
                    confirmed_count += 1

                # Upsert file into SQLite
                file_id = db.upsert_file(root_id, rel_path, abs_path, size, mtime, file_hash, status)

                # Update FTS5 if content indexing enabled
                if index_content and extracted_text:
                    ids = extract_identifiers(extracted_text)
                    snippet = extracted_text[:600]
                    cpf_str = " ".join(ids["cpf"])
                    cnpj_str = " ".join(ids["cnpj"])
                    boleto_str = " ".join(ids["boleto"])
                    kw_str = " ".join(candidate.get("palavras_chave", [])) if candidate else ""
                    db.update_fts_content(
                        rel_path,
                        f"{category} {tag_name}".strip(),
                        entity or "",
                        f"{kw_str} {suggested_filename} {category} {tag_name} {amount or ''}",
                        snippet,
                        cpf_str,
                        cnpj_str,
                        boleto_str,
                    )

                result_item = {
                    "file_id": file_id,
                    "rel_path": rel_path,
                    "abs_path": abs_path,
                    "size": size,
                    "mtime": mtime,
                    "hash": file_hash,
                    "file_type": file_type,
                    "status": status,
                    "candidate": candidate,
                    "confidence": confidence,
                    "scores": scores,
                    "suggested_filename": suggested_filename,
                    "primary_date": primary_date,
                    "amount": amount,
                    "due_date": due_date,
                    "entity": entity,
                    "category": category,
                    "caminho_fisico": caminho_fisico,
                    "tag_id": candidate.get("tag_id") if candidate else None,
                    "tag_name": tag_name,
                    "is_in_bundle": is_in_bundle,
                    "bundle_folder": bundle_folder,
                    "bundle_type": bundle_type,
                    "is_intruder": is_intruder,
                    "folder_status": folder_status,
                    "origin_folder": origin_folder,
                    "hierarchy_source": hierarchy_source,
                }

                results_stream.append(result_item)
                self.file_classified.emit(result_item)

            # 4. Find duplicates
            duplicates_raw = db.find_duplicates(root_id)
            duplicates_count = sum(len(group) for group in duplicates_raw)

            elapsed = time.time() - start_time
            stats = {
                "total_files": total_files,
                "identified": identified_count,
                "pending": pending_count,
                "intruders": intruders_count,
                "confirmed": confirmed_count,
                "duplicates_count": duplicates_count,
                "elapsed": elapsed,
                "items": results_stream,
                "cohesive_bundles": [b.to_dict() for b in cohesive_bundles],
                "discovered_tags": discovered_tags,
            }

            logger.info("Scan completed in {:.2f}s: {} identified ({} confirmed in folder, {} intruders), {} pending", elapsed, identified_count, confirmed_count, intruders_count, pending_count)
            self.scan_finished.emit(stats)

        except Exception as e:
            logger.error("Error during index worker execution: {}", e)
            self.error_occurred.emit(str(e))
