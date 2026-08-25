import re
from pathlib import Path
from typing import Dict, List, Any, Optional, Set, Tuple
from collections import Counter, defaultdict
from loguru import logger
from app.i18n.language_manager import tr, LanguageManager
from app.classification.folder_validator import GENERIC_FOLDER_NAMES

# Common stopwords to ignore when discovering name tokens
STOPWORDS = {
    "de", "do", "da", "dos", "das", "em", "no", "na", "nos", "nas",
    "por", "para", "com", "sem", "e", "ou", "a", "o", "as", "os",
    "um", "uma", "uns", "umas", "the", "a", "an", "and", "or", "of",
    "for", "with", "without", "in", "on", "at", "to", "by", "from",
    "copy", "copia", "copie", "final", "novo", "new", "v1", "v2", "v3",
    "scan", "img", "doc", "file", "arquivo", "temp", "tmp", "backup",
    "null", "undefined", "untitled", "sem_titulo", "teste", "test",
    "empresa", "pasta", "diretorio", "item", "dado", "dados", "geral"
}

# Regex to detect mechanical noise, camera/whatsapp prefixes, hex hashes, and raw numbers
MECHANICAL_NOISE_REGEX = re.compile(
    r"^(img|vid|wa\d*|dcim|screenshot|captura|pxl|dsc|sam|photo|foto\d*|scan\d*|doc\d*|temp\w*|tmp\w*|v\d+.*|x86.*|x64.*|[0-9a-f]{6,}|\d+.*)$",
    re.IGNORECASE
)

# Generic root words that represent standard categories when appearing as prefixes
ROOT_CATEGORY_MAP = {
    "fatura": "Faturas e Boletos",
    "faturas": "Faturas e Boletos",
    "boleto": "Faturas e Boletos",
    "boletos": "Faturas e Boletos",
    "conta": "Faturas e Boletos",
    "contas": "Faturas e Boletos",
    "comprovante": "Financeiro",
    "comprovantes": "Financeiro",
    "extrato": "Financeiro",
    "extratos": "Financeiro",
    "contrato": "Documentos e Contratos",
    "contratos": "Documentos e Contratos",
    "relatorio": "Trabalho e Projetos",
    "relatorios": "Trabalho e Projetos",
    "relatório": "Trabalho e Projetos",
    "relatórios": "Trabalho e Projetos",
    "recibo": "Financeiro",
    "recibos": "Financeiro",
    "documento": "Documentos Pessoais",
    "documentos": "Documentos Pessoais",
    "imposto": "Impostos e Tributos",
    "impostos": "Impostos e Tributos",
    "declaracao": "Impostos e Tributos",
    "declaracoes": "Impostos e Tributos",
    "declaração": "Impostos e Tributos",
    "declarações": "Impostos e Tributos",
    "holerite": "Financeiro",
    "holerites": "Financeiro",
    "projeto": "Trabalho e Projetos",
    "projetos": "Trabalho e Projetos",
    "project": "Trabalho e Projetos",
    "projects": "Trabalho e Projetos",
    "game": "Jogos",
    "games": "Jogos",
    "jogo": "Jogos",
    "jogos": "Jogos",
    "viagem": "Fotos e Imagens",
    "viagens": "Fotos e Imagens",
    "foto": "Fotos e Imagens",
    "fotos": "Fotos e Imagens",
    "musica": "Músicas e Áudios",
    "musicas": "Músicas e Áudios",
    "música": "Músicas e Áudios",
    "músicas": "Músicas e Áudios",
    "video": "Vídeos",
    "videos": "Vídeos",
    "vídeo": "Vídeos",
    "vídeos": "Vídeos",
    "curso": "Estudos e Cursos",
    "cursos": "Estudos e Cursos",
    "aula": "Estudos e Cursos",
    "aulas": "Estudos e Cursos",
    "trabalho": "Trabalho e Projetos",
    "pessoal": "Documentos Pessoais",
    "clientes": "Trabalho e Projetos",
    "cliente": "Trabalho e Projetos"
}

def is_mechanical_token(token: str) -> bool:
    """Returns True if token is mechanical noise, camera prefix, hash, or random characters."""
    t = token.strip().lower()
    if not t or len(t) < 3:
        return True
    if MECHANICAL_NOISE_REGEX.match(t):
        return True
    # Digits mixed with letters e.g. wa0001, a1b2c3, 0012a
    if re.search(r"\d", t) and re.search(r"[a-z]", t):
        # Allow only things like "2024" or standard words, reject mixed alphanumeric hashes
        return True
    if t.isdigit() or t in STOPWORDS:
        return True
    return False

def clean_token(token: str) -> str:
    """Cleans a single token removing dates, numbers, underscores, and mechanical noise."""
    t = re.sub(r"[^\w\s-]", "", token).strip().lower()
    if is_mechanical_token(t):
        return ""
    return t

def slugify(text: str) -> str:
    """Converts a text string to a clean slug without mechanical noise."""
    slug = re.sub(r"[^\w\s-]", "", text).strip().lower()
    slug = re.sub(r"[\s_-]+", "_", slug)
    if is_mechanical_token(slug):
        return ""
    return slug

def format_title(text: str) -> str:
    """Formats text into clean Title Case, strictly ignoring numeric strings, dates, and noise."""
    words = [w for w in re.split(r"[_\-\s\.]+", text) if w and not w.isdigit() and len(w) >= 2]
    if not words:
        return ""
    # Filter out pure numbers, dates, or mechanical tokens
    valid_words = [w for w in words if not is_mechanical_token(w)]
    if not valid_words:
        return ""
    return " ".join(w.capitalize() for w in valid_words)


class TagDiscoveryEngine:
    """
    Intelligent dynamic category and tag synthesis engine.
    Discovers, learns, and groups Categories and Tags cleanly and naturally without noise.
    """

    def __init__(self):
        pass

    def discover_tags(
        self,
        root_dir: Path,
        entries: List[Dict[str, Any]],
        existing_tags: Optional[List[Dict[str, Any]]] = None
    ) -> List[Dict[str, Any]]:
        """
        Discovers new categories and tags dynamically from scan results.
        Returns a list of newly synthesized tag definitions ready for persistence.
        """
        if not entries:
            return []

        existing_tag_names = {t.get("nome", "").lower() for t in (existing_tags or []) if t.get("nome")}
        
        discovered_tags: Dict[str, Dict[str, Any]] = {}
        lang = LanguageManager.get_instance().current_language

        # 1. DISCOVERY FROM FOLDER TOPOLOGY (Only for non-generic semantic folders)
        self._discover_from_folder_topology(root_dir, entries, discovered_tags, existing_tag_names, lang)

        # 2. DISCOVERY FROM PREFIX / ROOT WORD CLUSTERS & RECURRING TOKENS
        self._discover_from_recurring_patterns(entries, discovered_tags, existing_tag_names, lang)

        # 3. DISCOVERY FROM TEXT CONTENT ENTITIES
        self._discover_from_text_content(entries, discovered_tags, existing_tag_names, lang)

        result = list(discovered_tags.values())
        logger.info("Discovered {} clean dynamic tags and categories from scan of {}", len(result), root_dir)
        return result

    def _discover_from_folder_topology(
        self,
        root_dir: Path,
        entries: List[Dict[str, Any]],
        discovered_tags: Dict[str, Dict[str, Any]],
        existing_tag_names: Set[str],
        lang: str
    ):
        """
        Learns categories and tags directly from directory structure:
        - ParentFolder / SubFolder / File -> Category: ParentFolder, Tag: SubFolder
        - ParentFolder / File -> Category derived from folder, Tag: ParentFolder
        Strictly ignores generic folders like 'Downloads', 'Desktop', 'Nova Pasta'.
        """
        folder_tree: Dict[str, Dict[str, List[Dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
        direct_folder_files: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

        for entry in entries:
            rel = entry.get("rel_path", "").replace("\\", "/")
            parts = rel.split("/")
            if len(parts) >= 3:
                parent_folder = parts[0]
                sub_folder = parts[1]
                folder_tree[parent_folder][sub_folder].append(entry)
            elif len(parts) == 2:
                folder_name = parts[0]
                direct_folder_files[folder_name].append(entry)

        # Case A: Nested Structure (Depth >= 2) -> Parent is Category, Sub is Tag
        for parent_folder, subs in folder_tree.items():
            clean_parent = parent_folder.strip().lower()
            if clean_parent in GENERIC_FOLDER_NAMES or is_mechanical_token(clean_parent):
                continue

            cat_name = format_title(parent_folder)
            if not cat_name:
                continue

            for sub_folder, f_list in subs.items():
                clean_sub = sub_folder.strip().lower()
                if clean_sub in GENERIC_FOLDER_NAMES or is_mechanical_token(clean_sub):
                    continue

                tag_name = format_title(sub_folder)
                if not tag_name or tag_name.lower() in existing_tag_names:
                    continue

                cat_slug = slugify(cat_name)
                tag_slug = slugify(tag_name)
                if not cat_slug or not tag_slug:
                    continue

                tag_id = f"auto_topol_{cat_slug}_{tag_slug}"
                exts = list({Path(f.get("rel_path", "")).suffix.lower() for f in f_list if Path(f.get("rel_path", "")).suffix})
                keywords = [clean_token(w) for w in tag_name.split() if clean_token(w)]

                tag_def = {
                    "id": tag_id,
                    "nome": tag_name,
                    "categoria": cat_name,
                    "categoria_key": f"custom.{cat_slug}",
                    "subcategoria": tag_name,
                    "entidade": tag_name,
                    "caminho_fisico": f"{cat_name.replace(' ', '_')}/{tag_name.replace(' ', '_')}",
                    "origem": "user",
                    "idioma": lang,
                    "sinonimos": [sub_folder.lower()],
                    "palavras_chave": keywords if keywords else [tag_name.lower()],
                    "regex": [rf"\b{re.escape(sub_folder.replace('_', ' '))}\b"],
                    "extensoes": exts,
                    "confianca_base": 0.90,
                    "usar_para_automacao": True,
                    "version": 1
                }
                discovered_tags[tag_name.lower()] = tag_def

        # Case B: Single Folder Depth
        for folder_name, f_list in direct_folder_files.items():
            clean_folder = folder_name.strip().lower()
            if clean_folder in GENERIC_FOLDER_NAMES or is_mechanical_token(clean_folder):
                continue

            tag_name = format_title(folder_name)
            if not tag_name or tag_name.lower() in existing_tag_names or tag_name.lower() in discovered_tags:
                continue

            exts = list({Path(f.get("rel_path", "")).suffix.lower() for f in f_list if Path(f.get("rel_path", "")).suffix})
            keywords = [clean_token(w) for w in tag_name.split() if clean_token(w)]

            first_word = clean_token(tag_name.split()[0])
            if first_word in ROOT_CATEGORY_MAP:
                category_name = ROOT_CATEGORY_MAP[first_word]
            else:
                file_types = [f.get("file_type", "other") for f in f_list]
                category_name = self._infer_dynamic_category(tag_name, keywords, file_types, lang)

            cat_slug = slugify(category_name)
            tag_slug = slugify(tag_name)
            if not cat_slug or not tag_slug:
                continue

            tag_def = {
                "id": f"auto_folder_{tag_slug}",
                "nome": tag_name,
                "categoria": category_name,
                "categoria_key": f"custom.{cat_slug}",
                "subcategoria": tag_name,
                "entidade": tag_name,
                "caminho_fisico": f"{category_name.replace(' ', '_')}/{tag_name.replace(' ', '_')}",
                "origem": "user",
                "idioma": lang,
                "sinonimos": [clean_folder],
                "palavras_chave": keywords if keywords else [tag_name.lower()],
                "regex": [rf"\b{re.escape(clean_folder)}\b"],
                "extensoes": exts,
                "confianca_base": 0.88,
                "usar_para_automacao": True,
                "version": 1
            }
            discovered_tags[tag_name.lower()] = tag_def

    def _discover_from_recurring_patterns(
        self,
        entries: List[Dict[str, Any]],
        discovered_tags: Dict[str, Dict[str, Any]],
        existing_tag_names: Set[str],
        lang: str
    ):
        """
        Discovers recurring prefix clusters and standalone tokens only for real semantic words:
        - Fatura_Enel, Fatura_Sabesp -> Category: Faturas e Boletos, Tags: Enel, Sabesp
        - Relatorio_Vendas, Relatorio_Custos -> Category: Trabalho e Projetos, Tags: Vendas, Custos
        """
        prefix_groups: Dict[str, Dict[str, List[Dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
        token_occurrences: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

        for entry in entries:
            stem = Path(entry.get("rel_path", "")).stem
            tokens = [t for t in re.split(r"[_\-\s\.]+", stem) if t]
            clean_tokens = [clean_token(t) for t in tokens if clean_token(t)]

            for ct in set(clean_tokens):
                if len(ct) >= 3 and not is_mechanical_token(ct):
                    token_occurrences[ct].append(entry)

            if len(clean_tokens) >= 1:
                prefix = clean_tokens[0]
                if len(prefix) >= 3 and not is_mechanical_token(prefix):
                    suffix = " ".join(clean_tokens[1:]) if len(clean_tokens) > 1 else ""
                    prefix_groups[prefix][suffix].append(entry)

        # 1. Prefix clusters
        for prefix, suffix_map in prefix_groups.items():
            if is_mechanical_token(prefix):
                continue
            total_files = sum(len(fl) for fl in suffix_map.values())
            if total_files >= 2:
                cat_name = ROOT_CATEGORY_MAP.get(prefix, format_title(prefix))
                if not cat_name or is_mechanical_token(cat_name):
                    continue

                for suffix, f_list in suffix_map.items():
                    if not suffix:
                        tag_name = format_title(prefix)
                    else:
                        tag_name = format_title(suffix)

                    if not tag_name or is_mechanical_token(tag_name):
                        continue
                    if tag_name.lower() in existing_tag_names or tag_name.lower() in discovered_tags:
                        continue

                    cat_slug = slugify(cat_name)
                    tag_slug = slugify(tag_name)
                    if not cat_slug or not tag_slug:
                        continue

                    tag_id = f"auto_cluster_{cat_slug}_{tag_slug}"
                    exts = list({Path(f.get("rel_path", "")).suffix.lower() for f in f_list if Path(f.get("rel_path", "")).suffix})
                    keywords = [clean_token(w) for w in f"{prefix} {suffix}".split() if clean_token(w)]

                    tag_def = {
                        "id": tag_id,
                        "nome": tag_name,
                        "categoria": cat_name,
                        "categoria_key": f"custom.{cat_slug}",
                        "subcategoria": tag_name,
                        "entidade": tag_name,
                        "caminho_fisico": f"{cat_name.replace(' ', '_')}/{tag_name.replace(' ', '_')}",
                        "origem": "user",
                        "idioma": lang,
                        "sinonimos": [f"{prefix} {suffix}".strip().lower()],
                        "palavras_chave": keywords,
                        "regex": [rf"\b{re.escape(tag_name.lower())}\b", rf"\b{re.escape(prefix)}\b"],
                        "extensoes": exts,
                        "confianca_base": 0.88,
                        "usar_para_automacao": True,
                        "version": 1
                    }
                    discovered_tags[tag_name.lower()] = tag_def

        # 2. Standalone recurring tokens (>= 2 files)
        for token, f_list in token_occurrences.items():
            if is_mechanical_token(token):
                continue
            if len(f_list) >= 2:
                tag_name = format_title(token)
                if not tag_name or is_mechanical_token(tag_name) or tag_name.lower() in existing_tag_names or tag_name.lower() in discovered_tags:
                    continue

                category_name = ROOT_CATEGORY_MAP.get(token, self._infer_dynamic_category(token, [token], [f.get("file_type", "other") for f in f_list], lang))
                cat_slug = slugify(category_name)
                tag_slug = slugify(tag_name)
                if not cat_slug or not tag_slug:
                    continue

                exts = list({Path(f.get("rel_path", "")).suffix.lower() for f in f_list if Path(f.get("rel_path", "")).suffix})

                tag_def = {
                    "id": f"auto_token_{tag_slug}",
                    "nome": tag_name,
                    "categoria": category_name,
                    "categoria_key": f"custom.{cat_slug}",
                    "subcategoria": tag_name,
                    "entidade": tag_name,
                    "caminho_fisico": f"{category_name.replace(' ', '_')}/{tag_name.replace(' ', '_')}",
                    "origem": "user",
                    "idioma": lang,
                    "sinonimos": [token],
                    "palavras_chave": [token],
                    "regex": [rf"\b{re.escape(token)}\b"],
                    "extensoes": exts,
                    "confianca_base": 0.85,
                    "usar_para_automacao": True,
                    "version": 1
                }
                discovered_tags[tag_name.lower()] = tag_def

    def _discover_from_text_content(
        self,
        entries: List[Dict[str, Any]],
        discovered_tags: Dict[str, Dict[str, Any]],
        existing_tag_names: Set[str],
        lang: str
    ):
        """Extracts repeated entity patterns from extracted text content."""
        entity_to_files: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

        ENTITY_PATTERNS = [
            (r"\b(nubank|banco inter|itau|itaú|bradesco|santander|caixa economica|banco do brasil|c6 bank)\b", "Financeiro"),
            (r"\b(cpfl|enel|sabesp|comgas|comgás|copel|cemig|light|neoenergia|equatorial)\b", "Faturas e Boletos"),
            (r"\b(claro|vivo|tim|oi fibra|net virtua)\b", "Faturas e Boletos"),
            (r"\b(prefeitura de [\w\s]+|receita federal|governo do estado|inss)\b", "Impostos e Tributos"),
            (r"\b(universidade [\w\s]+|faculdade [\w\s]+|escola [\w\s]+)\b", "Estudos e Cursos")
        ]

        for entry in entries:
            text = entry.get("extracted_text", "")
            if not text:
                continue

            text_lower = text.lower()
            for pattern, default_cat in ENTITY_PATTERNS:
                matches = re.findall(pattern, text_lower)
                for m in matches:
                    ent_clean = m.strip()
                    if not is_mechanical_token(ent_clean):
                        entity_to_files[(ent_clean, default_cat)].append(entry)

        for (ent_name, default_cat), f_list in entity_to_files.items():
            if len(f_list) >= 1:
                tag_name = format_title(ent_name)
                if not tag_name or is_mechanical_token(tag_name) or tag_name.lower() in existing_tag_names or tag_name.lower() in discovered_tags:
                    continue

                category_name = default_cat
                cat_slug = slugify(category_name)
                tag_slug = slugify(tag_name)
                if not cat_slug or not tag_slug:
                    continue

                exts = list({Path(f.get("rel_path", "")).suffix.lower() for f in f_list if Path(f.get("rel_path", "")).suffix})
                keywords = [k for k in ent_name.split() if not is_mechanical_token(k)]

                tag_def = {
                    "id": f"auto_entity_{tag_slug}",
                    "nome": tag_name,
                    "categoria": category_name,
                    "categoria_key": f"custom.{cat_slug}",
                    "subcategoria": tag_name,
                    "entidade": tag_name,
                    "caminho_fisico": f"{category_name.replace(' ', '_')}/{tag_name.replace(' ', '_')}",
                    "origem": "user",
                    "idioma": lang,
                    "sinonimos": [ent_name],
                    "palavras_chave": keywords,
                    "regex": [rf"\b{re.escape(ent_name)}\b"],
                    "extensoes": exts,
                    "confianca_base": 0.92,
                    "usar_para_automacao": True,
                    "version": 1
                }
                discovered_tags[tag_name.lower()] = tag_def

    def _infer_dynamic_category(self, name: str, keywords: List[str], file_types: List[str], lang: str) -> str:
        """Infers dynamic category name based on contextual tokens or format domain."""
        combined_text = f"{name} {' '.join(keywords)}".lower()
        tokens = set(re.findall(r"\w+", combined_text))

        for root_kw, cat_name in ROOT_CATEGORY_MAP.items():
            if root_kw in tokens:
                return cat_name

        if file_types:
            most_common_type = Counter(file_types).most_common(1)[0][0]
            type_names = {
                "image": "Fotos e Imagens" if lang == "ptBR" else "Photos and Images",
                "audio": "Músicas e Áudios" if lang == "ptBR" else "Music and Audio",
                "video": "Vídeos" if lang == "ptBR" else "Videos",
                "document": "Documentos Pessoais" if lang == "ptBR" else "Personal Documents",
                "text": "Textos e Notas" if lang == "ptBR" else "Texts and Notes",
                "archive": "Arquivos Compactados" if lang == "ptBR" else "Archives",
                "binary": "Aplicativos e Programas" if lang == "ptBR" else "Applications"
            }
            return type_names.get(most_common_type, "Outros" if lang == "ptBR" else "Other")

        return "Geral" if lang == "ptBR" else "General"
