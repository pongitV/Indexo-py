import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Any, Optional, Set, Tuple
from loguru import logger
from app.i18n.language_manager import tr, LanguageManager
from app.classification.tag_discovery import TagDiscoveryEngine, is_mechanical_token
from app.classification.folder_validator import FolderContextValidator, FolderHypothesisResult

GAME_EXTENSIONS = {
    ".exe", ".pak", ".pck", ".vpk", ".unity3d", ".wad", ".sav", ".dat",
    ".rom", ".iso", ".nds", ".gba", ".nsp", ".xci", ".cso", ".mod",
    ".bsp", ".vmf", ".gma", ".esp", ".esm", ".ba2", ".bsa"
}

GAME_INDICATOR_FILENAMES = {
    "steam_api.dll", "steam_api64.dll", "steam_appid.txt",
    "unityplayer.dll", "unitycrashhandler64.exe", "unitycrashhandler32.exe",
    "gamestate.bin", "savedata.bin", "dxgi.dll", "d3d11.dll", "d3d9.dll",
    "xinput1_3.dll", "xinput1_4.dll", "openvr_api.dll", "galaxy.dll",
    "galaxy64.dll", "fmod.dll", "fmodstudio.dll", "binkw32.dll", "binkw64.dll"
}

GAME_FOLDER_KEYWORDS = {
    "game", "games", "jogo", "jogos", "steam", "steamapps", "epic", "gog",
    "roms", "emulator", "saves", "mods", "binaries", "content", "shaders"
}

CODE_PROJECT_INDICATORS = {
    "package.json", "cargo.toml", "pyproject.toml", "cmakelists.txt",
    "makefile", "pom.xml", "build.gradle", ".git", "requirements.txt",
    "go.mod", "solution.sln", ".csproj", ".vcxproj"
}

@dataclass
class CohesiveBundle:
    folder_rel: str
    folder_name: str
    abs_path: str
    category: str
    category_key: str
    bundle_type: str  # "game", "application", "project", "media_album", "homogeneous_group"
    primary_executable: Optional[str] = None
    file_count: int = 0
    total_size: int = 0
    action: str = "move_parent"  # "move_parent", "keep", "disassemble"
    confidence: float = 0.95
    reason: str = ""
    file_rel_paths: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "folder_rel": self.folder_rel,
            "folder_name": self.folder_name,
            "abs_path": self.abs_path,
            "category": self.category,
            "category_key": self.category_key,
            "bundle_type": self.bundle_type,
            "primary_executable": self.primary_executable,
            "file_count": self.file_count,
            "total_size": self.total_size,
            "action": self.action,
            "confidence": self.confidence,
            "reason": self.reason,
            "file_rel_paths": self.file_rel_paths,
        }


def sanitize_caminho_fisico(caminho: str, fallback_category: str = "Geral") -> str:
    """
    Ensures a physical destination folder path is ALWAYS clean, human-readable,
    and NEVER consists of raw dates, random digits, messy symbols, or mechanical noise tokens.
    """
    if not caminho or not caminho.strip():
        return fallback_category.replace(" ", "_")
    
    parts = [p.strip() for p in caminho.replace("\\", "/").split("/") if p.strip()]
    clean_parts = []
    
    for p in parts:
        # Ignore raw dates (e.g. 2024-05-12, 2024_05), pure numbers, or pure hex hashes
        if re.match(r"^(\d{4}[-_]\d{2}([-_]\d{2})?|\d+|[0-9a-f]{6,})$", p, re.IGNORECASE):
            continue
        # Remove unwanted punctuation and leading numbers/hashes
        clean_p = re.sub(r"^\d+[-_]*", "", p)
        clean_p = re.sub(r"[^\w\s-]", "", clean_p).strip().replace(" ", "_")
        clean_p = re.sub(r"^_+|_+$", "", clean_p)
        if clean_p and len(clean_p) >= 2 and not clean_p.isdigit():
            # Discard explicit camera/whatsapp/temporary/mechanical noise tokens
            if re.match(r"^(wa\d*|dcim|pxl\d*|img\d*|scan\d*|vid\d*|temp\w*|tmp\w*|null|undefined|[0-9a-f]{6,})$", clean_p, re.IGNORECASE):
                continue
            clean_parts.append(clean_p)
            
    if not clean_parts:
        return fallback_category.replace(" ", "_")
    
    return "/".join(clean_parts[:2])


class SimilarityEngine:
    """
    Hierarchical Similarity & Cohesive Structure Engine.
    Evaluates similarities strictly in order:
    1. Cohesive Bundle Context (Games, Projects, App directories preserved intact)
    2. Parent Folder Hypothesis (Confirm valid files in-place, detect and isolate intruders)
    3. Dynamic Discovered / User Tag Match (Clean semantic clusters & entities)
    4. Content / Metadata (Text signatures, EXIF, tags, keywords)
    5. Type / Format fallback
    """

    def __init__(self):
        self.tag_discovery = TagDiscoveryEngine()
        self.folder_validator = FolderContextValidator()

    def analyze_scan_results(
        self,
        root_dir: Path,
        entries: List[Dict[str, Any]],
        existing_tags: Optional[List[Dict[str, Any]]] = None
    ) -> Tuple[List[CohesiveBundle], Dict[str, CohesiveBundle], List[Dict[str, Any]]]:
        """
        Analyzes all scanned files in the target directory, detecting cohesive bundles,
        mapping file relative paths to their parent bundle, and synthesizing clean semantic tags.
        """
        bundles: List[CohesiveBundle] = []
        file_to_bundle: Dict[str, CohesiveBundle] = {}
        discovered_tags: List[Dict[str, Any]] = []

        if not entries or not root_dir.exists():
            return bundles, file_to_bundle, discovered_tags

        # Group entries by top-level subfolders
        folder_groups: Dict[str, List[Dict[str, Any]]] = {}
        for entry in entries:
            rel = entry.get("rel_path", "").replace("\\", "/")
            parts = rel.split("/")
            if len(parts) > 1:
                top_folder = parts[0]
                if top_folder not in folder_groups:
                    folder_groups[top_folder] = []
                folder_groups[top_folder].append(entry)

        lang = LanguageManager.get_instance().current_language

        for folder_name, f_list in folder_groups.items():
            folder_abs = str(root_dir / folder_name).replace("\\", "/")
            bundle = self._evaluate_folder_cohesion(folder_name, folder_abs, f_list, lang)
            if bundle:
                bundles.append(bundle)
                for f in f_list:
                    rel_p = f.get("rel_path", "").replace("\\", "/")
                    file_to_bundle[rel_p] = bundle

        # Dynamic clean tag discovery from non-generic folder structures and recurring patterns
        discovered_tags = self.tag_discovery.discover_tags(root_dir, entries, existing_tags)

        logger.info("Detected {} cohesive bundles and {} discovered tags in {}", len(bundles), len(discovered_tags), root_dir)
        return bundles, file_to_bundle, discovered_tags

    def _evaluate_folder_cohesion(
        self,
        folder_name: str,
        folder_abs: str,
        files: List[Dict[str, Any]],
        lang: str
    ) -> Optional[CohesiveBundle]:
        """
        Detects if a directory is a cohesive unit (e.g. Game, Code Project, Software Installation).
        """
        if not files or len(files) < 2:
            return None

        total_files = len(files)
        total_size = sum(f.get("size", 0) for f in files)
        file_rels = [f.get("rel_path", "") for f in files]
        file_names_lower = {Path(f.get("rel_path", "")).name.lower() for f in files}
        extensions_lower = {Path(f.get("rel_path", "")).suffix.lower() for f in files}
        folder_lower = folder_name.lower()

        # 1. Code Projects
        has_code_indicator = any(ind in file_names_lower for ind in CODE_PROJECT_INDICATORS)
        code_exts = {".py", ".rs", ".js", ".ts", ".cpp", ".c", ".h", ".cs", ".go", ".java", ".html", ".css"}
        has_code_files = len(extensions_lower.intersection(code_exts)) >= 2
        if has_code_indicator or has_code_files:
            cat_name = "Projetos de Código" if lang == "ptBR" else "Code Projects"
            cat_key = "cat.projetos_codigo"
            return CohesiveBundle(
                folder_rel=folder_name,
                folder_name=folder_name,
                abs_path=folder_abs,
                category=cat_name,
                category_key=cat_key,
                bundle_type="project",
                primary_executable=None,
                file_count=total_files,
                total_size=total_size,
                action="move_parent",
                confidence=0.98,
                reason="Projeto de desenvolvimento coeso",
                file_rel_paths=file_rels,
            )

        # 2. Games & Game Packages
        has_game_indicator = any(ind in file_names_lower for ind in GAME_INDICATOR_FILENAMES)
        has_game_folder = any(kw in folder_lower for kw in GAME_FOLDER_KEYWORDS)
        has_game_exts = any(ext in GAME_EXTENSIONS for ext in extensions_lower)

        executables = [Path(f.get("rel_path", "")).name for f in files if Path(f.get("rel_path", "")).suffix.lower() == ".exe"]
        main_exe = None
        for exe in executables:
            stem = Path(exe).stem.lower()
            if stem == folder_lower or stem in folder_lower or folder_lower in stem:
                main_exe = exe
                break
        if not main_exe and executables:
            main_exe = executables[0]

        if has_game_indicator or (has_game_exts and has_game_folder) or (main_exe and has_game_exts):
            cat_name = "Jogos" if lang == "ptBR" else "Games"
            cat_key = "cat.jogos"
            return CohesiveBundle(
                folder_rel=folder_name,
                folder_name=folder_name,
                abs_path=folder_abs,
                category=cat_name,
                category_key=cat_key,
                bundle_type="game",
                primary_executable=main_exe or "Game Package",
                file_count=total_files,
                total_size=total_size,
                action="move_parent",
                confidence=0.95,
                reason="Pacote de jogo identificado",
                file_rel_paths=file_rels,
            )

        # 3. Software / Application Installation
        if main_exe and len(files) >= 3 and any(ext in {".dll", ".ini", ".dat", ".cfg"} for ext in extensions_lower):
            cat_name = "Aplicativos e Programas" if lang == "ptBR" else "Applications"
            cat_key = "cat.aplicativos"
            return CohesiveBundle(
                folder_rel=folder_name,
                folder_name=folder_name,
                abs_path=folder_abs,
                category=cat_name,
                category_key=cat_key,
                bundle_type="application",
                primary_executable=main_exe,
                file_count=total_files,
                total_size=total_size,
                action="move_parent",
                confidence=0.92,
                reason="Instalação de software / aplicativo",
                file_rel_paths=file_rels,
            )

        return None

    def classify_by_hierarchy(
        self,
        rel_path: str,
        abs_path: str,
        file_type: str,
        extracted_text: str,
        candidate: Optional[Dict[str, Any]],
        parent_bundle: Optional[CohesiveBundle] = None,
        matching_tag: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Classifies an individual file using strict hierarchy:
        1. Cohesive parent bundle match (e.g. PEAK/PEAK.exe, PEAK/data.pak)
        2. Parent folder hypothesis testing (Confirm in-place or detect intruder)
        3. Dynamic Discovered / User Tag Match
        4. Content / Metadata (Text/rules match)
        5. Type / Format fallback
        """
        path_obj = Path(abs_path)
        ext = path_obj.suffix.lower()
        stem = path_obj.stem
        lang = LanguageManager.get_instance().current_language

        # Extract parent folder name
        rel_clean = rel_path.replace("\\", "/")
        parts = rel_clean.split("/")
        parent_folder = parts[0] if len(parts) > 1 else "."

        # 1. If file belongs to a cohesive parent bundle
        if parent_bundle:
            return {
                "category": parent_bundle.category,
                "category_key": parent_bundle.category_key,
                "tag_name": parent_bundle.folder_name,
                "caminho_fisico": sanitize_caminho_fisico(f"{parent_bundle.category}/{parent_bundle.folder_name}"),
                "confidence": parent_bundle.confidence,
                "status": "identificado",
                "is_in_bundle": True,
                "bundle_folder": parent_bundle.folder_rel,
                "bundle_type": parent_bundle.bundle_type,
                "is_intruder": False,
                "folder_status": "confirmado",
                "origin_folder": parent_bundle.folder_rel,
                "hierarchy_source": "name_folder_bundle"
            }

        # 2. Evaluate Parent Folder Hypothesis
        folder_eval: FolderHypothesisResult = self.folder_validator.evaluate_folder_and_file(
            folder_rel=parent_folder,
            rel_path=rel_path,
            abs_path=abs_path,
            ext=ext,
            extracted_text=extracted_text,
            file_type=file_type
        )

        is_intruder = folder_eval.is_intruder
        origin_folder = folder_eval.origin_folder

        # If file matches parent folder hypothesis -> Confirm in-place with high confidence!
        if folder_eval.matches_hypothesis:
            return {
                "category": folder_eval.suggested_category,
                "category_key": f"folder_hypothesis.{folder_eval.suggested_category}",
                "tag_name": folder_eval.suggested_subcategoria or folder_eval.suggested_category,
                "caminho_fisico": sanitize_caminho_fisico(folder_eval.suggested_caminho_fisico),
                "confidence": folder_eval.confidence,
                "status": "identificado",
                "is_in_bundle": False,
                "bundle_folder": None,
                "bundle_type": None,
                "is_intruder": False,
                "folder_status": "confirmado",
                "origin_folder": origin_folder,
                "hierarchy_source": "folder_hypothesis_confirmed"
            }

        # 3. If matched a dynamically synthesized or user tag (by Name / Cluster / Entity)
        if matching_tag:
            return {
                "category": matching_tag.get("categoria", tr(f"type.{file_type}")),
                "category_key": matching_tag.get("categoria_key"),
                "tag_name": matching_tag.get("nome", tr(f"type.{file_type}")),
                "caminho_fisico": sanitize_caminho_fisico(matching_tag.get("caminho_fisico", tr(f"type.{file_type}"))),
                "confidence": float(matching_tag.get("confianca_base", 0.88)),
                "status": "identificado",
                "is_in_bundle": False,
                "bundle_folder": None,
                "bundle_type": None,
                "is_intruder": is_intruder,
                "folder_status": "intruso" if is_intruder else "novo_agrupamento",
                "origin_folder": origin_folder,
                "hierarchy_source": "dynamic_discovered_tag"
            }

        # 4. Rule candidate match (Content / Specific Regex)
        if candidate and candidate.get("confianca", 0.0) >= 0.65:
            scores = candidate.get("scores", {})
            score_conteudo = scores.get("conteudo", 0.0)
            if score_conteudo > 0.0 or candidate.get("origem") == "user":
                return {
                    "category": candidate.get("categoria", tr(f"type.{file_type}")),
                    "category_key": candidate.get("categoria_key"),
                    "tag_name": candidate.get("nome", tr(f"type.{file_type}")),
                    "caminho_fisico": sanitize_caminho_fisico(candidate.get("caminho_fisico", tr(f"type.{file_type}"))),
                    "confidence": candidate.get("confianca", 0.0),
                    "status": "identificado",
                    "is_in_bundle": False,
                    "bundle_folder": None,
                    "bundle_type": None,
                    "is_intruder": is_intruder,
                    "folder_status": "intruso" if is_intruder else "novo_agrupamento",
                    "origin_folder": origin_folder,
                    "hierarchy_source": "content_rule"
                }

        # 5. Name-based Game / Executable / Media detection
        if ext in GAME_EXTENSIONS:
            cat_name = "Jogos" if lang == "ptBR" else "Games"
            cat_key = "cat.jogos"
            return {
                "category": cat_name,
                "category_key": cat_key,
                "tag_name": stem,
                "caminho_fisico": sanitize_caminho_fisico(cat_name),
                "confidence": 0.88,
                "status": "identificado",
                "is_in_bundle": False,
                "bundle_folder": None,
                "bundle_type": "game",
                "is_intruder": is_intruder,
                "folder_status": "intruso" if is_intruder else "novo_agrupamento",
                "origin_folder": origin_folder,
                "hierarchy_source": "name_game_extension"
            }

        # 6. Type / Format re-routing (Media & Documents automatically organized)
        if file_type == "image":
            cat_name = "Fotos e Imagens" if lang == "ptBR" else "Photos and Images"
            return {
                "category": cat_name,
                "category_key": "cat.midia_imagem",
                "tag_name": cat_name,
                "caminho_fisico": sanitize_caminho_fisico(cat_name),
                "confidence": 0.88,
                "status": "identificado",
                "is_in_bundle": False,
                "bundle_folder": None,
                "bundle_type": None,
                "is_intruder": is_intruder,
                "folder_status": "intruso" if is_intruder else "novo_agrupamento",
                "origin_folder": origin_folder,
                "hierarchy_source": "format_media_image"
            }
        elif file_type == "audio":
            cat_name = "Músicas e Áudios" if lang == "ptBR" else "Music and Audio"
            return {
                "category": cat_name,
                "category_key": "cat.midia_audio",
                "tag_name": cat_name,
                "caminho_fisico": sanitize_caminho_fisico(cat_name),
                "confidence": 0.88,
                "status": "identificado",
                "is_in_bundle": False,
                "bundle_folder": None,
                "bundle_type": None,
                "is_intruder": is_intruder,
                "folder_status": "intruso" if is_intruder else "novo_agrupamento",
                "origin_folder": origin_folder,
                "hierarchy_source": "format_media_audio"
            }
        elif file_type == "video":
            cat_name = "Vídeos" if lang == "ptBR" else "Videos"
            return {
                "category": cat_name,
                "category_key": "cat.midia_video",
                "tag_name": cat_name,
                "caminho_fisico": sanitize_caminho_fisico(cat_name),
                "confidence": 0.88,
                "status": "identificado",
                "is_in_bundle": False,
                "bundle_folder": None,
                "bundle_type": None,
                "is_intruder": is_intruder,
                "folder_status": "intruso" if is_intruder else "novo_agrupamento",
                "origin_folder": origin_folder,
                "hierarchy_source": "format_media_video"
            }

        # 7. Final fallback for unresolved documents/others
        type_cat = tr(f"type.{file_type}")
        return {
            "category": type_cat,
            "category_key": f"type.{file_type}",
            "tag_name": type_cat,
            "caminho_fisico": sanitize_caminho_fisico(type_cat),
            "confidence": 0.50,
            "status": "pendente",
            "is_in_bundle": False,
            "bundle_folder": None,
            "bundle_type": None,
            "is_intruder": is_intruder,
            "folder_status": "intruso" if is_intruder else "novo_agrupamento",
            "origin_folder": origin_folder,
            "hierarchy_source": "type_fallback"
        }
