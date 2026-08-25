"""
Folder Context & Hypothesis Validator for Indexo.
Evaluates whether files inside an existing folder legitimately belong to the folder's theme,
confirming valid files with high confidence and isolating intruder files for semantic relocation.
"""

import re
from pathlib import Path
from dataclasses import dataclass
from typing import Dict, List, Any, Optional, Set, Tuple
from loguru import logger
from app.i18n.language_manager import tr, LanguageManager

# Generic/neutral folder names that do NOT represent a specialized semantic domain
GENERIC_FOLDER_NAMES: Set[str] = {
    "downloads", "download", "desktop", "area de trabalho", "área de trabalho",
    "nova pasta", "nova pasta (1)", "nova pasta (2)", "nova pasta (3)", "new folder",
    "temp", "tmp", "lixeira", "arquivos", "files", "bagunca", "bagunça", "tudo",
    "geral", "outros", "misc", "diversos", "unsorted", "documentos", "documents",
    "pasta", "meus arquivos", "my files", "indexo_files"
}

@dataclass
class FolderHypothesisResult:
    is_semantic_folder: bool
    matches_hypothesis: bool
    is_intruder: bool
    folder_status: str  # "confirmado", "intruso", "novo_agrupamento"
    origin_folder: str
    suggested_category: str
    suggested_subcategoria: str
    suggested_caminho_fisico: str
    confidence: float
    reason: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_semantic_folder": self.is_semantic_folder,
            "matches_hypothesis": self.matches_hypothesis,
            "is_intruder": self.is_intruder,
            "folder_status": self.folder_status,
            "origin_folder": self.origin_folder,
            "suggested_category": self.suggested_category,
            "suggested_subcategoria": self.suggested_subcategoria,
            "suggested_caminho_fisico": self.suggested_caminho_fisico,
            "confidence": self.confidence,
            "reason": self.reason,
        }


class FolderContextValidator:
    """
    Validates files against the hypothesis of their parent folder name.
    Preserves and confirms legitimate files, while flagging out-of-context intruder files.
    """

    # Semantic domains with keywords, allowed extensions, content indicators, and canonical paths
    DOMAIN_DEFINITIONS: List[Dict[str, Any]] = [
        {
            "id": "boletos_faturas",
            "category": "Faturas e Boletos",
            "subcategoria": "Boletos e Faturas",
            "caminho_fisico": "Faturas_e_Boletos/Boletos",
            "folder_keywords": ["boleto", "boletos", "fatura", "faturas", "conta", "contas", "luz", "agua", "água", "gas", "gás", "energia", "internet", "telefone", "celular", "cartao", "cartão"],
            "allowed_extensions": {".pdf", ".png", ".jpg", ".jpeg"},
            "content_keywords": ["linha digitavel", "vencimento", "beneficiario", "cedente", "sacado", "valor a pagar", "kwh", "consumo", "enel", "cpfl", "sabesp", "comgas", "claro", "vivo", "tim", "nubank", "itau", "bradesco", "santander", "caixa"],
            "regex": [r"\b\d{5}\.?\d{5}\b", r"\bR\$\s*\d+", r"\b(vencimento|pagavel|fatura)\b"],
        },
        {
            "id": "comprovantes",
            "category": "Financeiro",
            "subcategoria": "Comprovantes e Recibos",
            "caminho_fisico": "Financeiro/Comprovantes",
            "folder_keywords": ["comprovante", "comprovantes", "recibo", "recibos", "pix", "transferencia", "transferência", "pagamento", "pagamentos"],
            "allowed_extensions": {".pdf", ".png", ".jpg", ".jpeg"},
            "content_keywords": ["comprovante de transferencia", "comprovante de pagamento", "comprovante pix", "autenticacao mecanica", "valor recebido", "recibo de pagamento"],
            "regex": [r"\bcomprovante\b", r"\bpix\b", r"\brecibo\b"],
        },
        {
            "id": "extratos_banco",
            "category": "Financeiro",
            "subcategoria": "Extratos Bancários",
            "caminho_fisico": "Financeiro/Extratos",
            "folder_keywords": ["extrato", "extratos", "banco", "bancos", "rendimento", "rendimentos", "investimento", "investimentos", "financeiro"],
            "allowed_extensions": {".pdf", ".ofx", ".csv", ".xlsx", ".xls"},
            "content_keywords": ["extrato de conta", "saldo anterior", "saldo atual", "lancamentos", "lançamentos", "movimentacao", "movimentação", "rentabilidade"],
            "regex": [r"\bextrato\b", r"\bsaldo\b", r"\bconta corrente\b"],
        },
        {
            "id": "impostos_tributos",
            "category": "Impostos e Tributos",
            "subcategoria": "Declarações e Guias",
            "caminho_fisico": "Impostos_e_Tributos",
            "folder_keywords": ["imposto", "impostos", "tributo", "tributos", "darf", "das", "irpf", "receita federal", "declaracao", "declaração", "iptu", "ipva", "gps", "inss"],
            "allowed_extensions": {".pdf", ".pfx", ".xml"},
            "content_keywords": ["receita federal", "ministerio da fazenda", "darf", "das", "apuracao", "exercicio", "imposto sobre a renda", "iptu", "ipva"],
            "regex": [r"\bdarf\b", r"\birpf\b", r"\breceita federal\b", r"\biptu\b", r"\bipva\b"],
        },
        {
            "id": "contratos_juridico",
            "category": "Documentos e Contratos",
            "subcategoria": "Contratos e Acordos",
            "caminho_fisico": "Documentos_e_Contratos/Contratos",
            "folder_keywords": ["contrato", "contratos", "aluguel", "locacao", "locação", "acordo", "acordos", "termo", "termos", "juridico", "jurídico", "procuracao", "procuração", "escritura"],
            "allowed_extensions": {".pdf", ".docx", ".doc", ".odt"},
            "content_keywords": ["contrato de", "locador", "locatario", "clausula", "cláusula", "foro da comarca", "partes acordam", "termo de compromisso", "testemunhas"],
            "regex": [r"\bcontrato\b", r"\bclausula\b", r"\blocador\b", r"\blocatario\b"],
        },
        {
            "id": "relatorios_trabalho",
            "category": "Trabalho e Projetos",
            "subcategoria": "Relatórios e Propostas",
            "caminho_fisico": "Trabalho_e_Projetos/Relatorios",
            "folder_keywords": ["relatorio", "relatorios", "relatório", "relatórios", "proposta", "propostas", "orcamento", "orçamento", "orcamentos", "orçamentos", "vendas", "clientes", "projeto", "projetos", "apresentacao", "apresentação"],
            "allowed_extensions": {".pdf", ".docx", ".xlsx", ".pptx", ".odt", ".ods", ".odp"},
            "content_keywords": ["relatorio", "proposta comercial", "orcamento", "escopo", "cronograma", "resumo executivo", "kpi", "faturamento"],
            "regex": [r"\brelatorio\b", r"\bproposta\b", r"\borcamento\b"],
        },
        {
            "id": "documentos_pessoais",
            "category": "Documentos Pessoais",
            "subcategoria": "Identificação e Registro",
            "caminho_fisico": "Documentos_Pessoais",
            "folder_keywords": ["documentos pessoais", "pessoal", "rg", "cnh", "cpf", "identidade", "passaporte", "certidao", "certidão", "curriculo", "currículo", "cv", "saude", "saúde", "exames", "receitas"],
            "allowed_extensions": {".pdf", ".png", ".jpg", ".jpeg", ".docx"},
            "content_keywords": ["republica federativa", "registro geral", "carteira nacional de habilitacao", "certidao de nascimento", "certidao de casamento", "curriculum vitae", "historico escolar", "exame de sangue", "atestado medico"],
            "regex": [r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b", r"\b(cnh|rg|cpf|certidao|curriculo|passaporte)\b"],
        },
        {
            "id": "estudos_cursos",
            "category": "Estudos e Cursos",
            "subcategoria": "Apostilas e Livros",
            "caminho_fisico": "Estudos_e_Cursos",
            "folder_keywords": ["curso", "cursos", "aula", "aulas", "estudo", "estudos", "apostila", "apostilas", "livro", "livros", "ebook", "ebooks", "faculdade", "universidade", "escola", "materia", "matéria", "certificado", "certificados"],
            "allowed_extensions": {".pdf", ".epub", ".mobi", ".docx", ".pptx", ".mp4", ".zip"},
            "content_keywords": ["capitulo", "capítulo", "sumario", "sumário", "bibliografia", "modulo", "módulo", "exercicios", "exercícios", "certificamos que", "conclusao de curso"],
            "regex": [r"\b(apostila|livro|capitulo|certificado|modulo|aula)\b"],
        },
        {
            "id": "fotos_viagens",
            "category": "Fotos e Imagens",
            "subcategoria": "Viagens e Eventos",
            "caminho_fisico": "Fotos_e_Imagens",
            "folder_keywords": ["foto", "fotos", "imagem", "imagens", "picture", "pictures", "photo", "photos", "viagem", "viagens", "ferias", "férias", "praia", "natal", "aniversario", "aniversário", "casamento", "viagem 20", "trip"],
            "allowed_extensions": {".jpg", ".jpeg", ".png", ".webp", ".heic", ".raw", ".cr2", ".nef", ".arw", ".gif"},
            "content_keywords": ["camera", "nikon", "canon", "sony", "samsung", "apple", "exif", "dcim"],
            "regex": [r"\b(foto|imagem|viagem|praia|ferias|trip)\b"],
        },
        {
            "id": "musicas_audios",
            "category": "Músicas e Áudios",
            "subcategoria": "Álbum e Músicas",
            "caminho_fisico": "Musicas_e_Audios",
            "folder_keywords": ["musica", "musicas", "música", "músicas", "audio", "audios", "áudio", "áudios", "mp3", "album", "álbum", "discografia", "soundtrack", "ost", "podcast"],
            "allowed_extensions": {".mp3", ".flac", ".wav", ".aac", ".ogg", ".m4a", ".wma"},
            "content_keywords": ["artist", "album", "track", "genre", "bitrate", "id3"],
            "regex": [r"\b(mp3|flac|album|musica|podcast)\b"],
        },
        {
            "id": "videos_filmes",
            "category": "Vídeos",
            "subcategoria": "Filmes e Gravações",
            "caminho_fisico": "Videos",
            "folder_keywords": ["video", "videos", "vídeo", "vídeos", "filme", "filmes", "serie", "series", "série", "séries", "gravacao", "gravação", "gravacoes", "gravações", "movie", "movies"],
            "allowed_extensions": {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm"},
            "content_keywords": ["1080p", "720p", "4k", "h264", "hevc", "bluray", "web-dl"],
            "regex": [r"\b(mp4|mkv|1080p|720p|bluray|filme|serie)\b"],
        },
        {
            "id": "jogos_games",
            "category": "Jogos",
            "subcategoria": "Jogos e Pacotes",
            "caminho_fisico": "Jogos",
            "folder_keywords": ["jogo", "jogos", "game", "games", "roms", "emulador", "steam", "mods", "saves"],
            "allowed_extensions": {".exe", ".pak", ".wad", ".unity3d", ".iso", ".rom", ".sav", ".dat"},
            "content_keywords": ["unity", "unreal", "steam", "directx", "savedata", "gamestate"],
            "regex": [r"\b(game|jogo|unity|steam)\b"],
        },
        {
            "id": "codigo_projetos",
            "category": "Projetos de Código",
            "subcategoria": "Desenvolvimento",
            "caminho_fisico": "Projetos_de_Codigo",
            "folder_keywords": ["codigo", "código", "code", "dev", "desenvolvimento", "projeto", "projetos", "scripts", "src", "app"],
            "allowed_extensions": {".py", ".rs", ".js", ".ts", ".html", ".css", ".cpp", ".c", ".java", ".go", ".json", ".toml", ".yaml"},
            "content_keywords": ["function", "import", "def ", "class ", "pub fn", "fn main", "package.json", "cargo.toml"],
            "regex": [r"\b(import|def|class|function|cargo\.toml|package\.json)\b"],
        }
    ]

    def __init__(self):
        pass

    def evaluate_folder_and_file(
        self,
        folder_rel: str,
        rel_path: str,
        abs_path: str,
        ext: str,
        extracted_text: str = "",
        file_type: str = "other"
    ) -> FolderHypothesisResult:
        """
        Evaluates an individual file within its parent folder context.
        """
        clean_folder = folder_rel.strip().replace("\\", "/").split("/")[0].lower() if folder_rel else "."
        clean_folder_normalized = re.sub(r"[^\w\s]", " ", clean_folder).strip()

        # 1. Check if folder is generic or neutral (e.g. "Downloads", "Desktop", "Nova Pasta")
        if clean_folder_normalized in GENERIC_FOLDER_NAMES or clean_folder in GENERIC_FOLDER_NAMES or clean_folder == ".":
            return FolderHypothesisResult(
                is_semantic_folder=False,
                matches_hypothesis=False,
                is_intruder=False,
                folder_status="novo_agrupamento",
                origin_folder=clean_folder,
                suggested_category="Geral",
                suggested_subcategoria="",
                suggested_caminho_fisico="Geral",
                confidence=0.50,
                reason="Pasta de origem genérica; sujeito a classificação semântica global."
            )

        # 2. Match folder name against known semantic domains
        matched_domain: Optional[Dict[str, Any]] = None
        for domain in self.DOMAIN_DEFINITIONS:
            for kw in domain["folder_keywords"]:
                if kw in clean_folder_normalized or clean_folder_normalized.startswith(kw):
                    matched_domain = domain
                    break
            if matched_domain:
                break

        # If the folder name doesn't match predefined domains, treat it as a custom semantic folder
        stem = Path(rel_path).stem.lower()
        text_lower = extracted_text.lower() if extracted_text else ""

        if not matched_domain:
            # Custom semantic folder hypothesis:
            # Check if file stem or text shares tokens with the folder name
            folder_tokens = [t for t in clean_folder_normalized.split() if len(t) >= 3]
            shares_token = any(t in stem or t in text_lower for t in folder_tokens)

            cat_title = clean_folder_normalized.title()
            if shares_token or len(folder_tokens) == 0:
                return FolderHypothesisResult(
                    is_semantic_folder=True,
                    matches_hypothesis=True,
                    is_intruder=False,
                    folder_status="confirmado",
                    origin_folder=clean_folder,
                    suggested_category=cat_title,
                    suggested_subcategoria=cat_title,
                    suggested_caminho_fisico=cat_title.replace(" ", "_"),
                    confidence=0.90,
                    reason=f"Arquivo condiz com o tema da pasta personalizada '{clean_folder}'."
                )
            else:
                return FolderHypothesisResult(
                    is_semantic_folder=True,
                    matches_hypothesis=False,
                    is_intruder=True,
                    folder_status="intruso",
                    origin_folder=clean_folder,
                    suggested_category="Geral",
                    suggested_subcategoria="",
                    suggested_caminho_fisico="Geral",
                    confidence=0.40,
                    reason=f"Arquivo sem relação aparente com a pasta personalizada '{clean_folder}'."
                )

        # 3. Test hypothesis against the matched domain
        allowed_exts: Set[str] = matched_domain["allowed_extensions"]
        content_kws: List[str] = matched_domain["content_keywords"]
        regex_list: List[str] = matched_domain.get("regex", [])

        # Check extension compatibility
        ext_match = ext.lower() in allowed_exts

        # Check content / stem indicators
        stem_match = any(kw in stem for kw in matched_domain["folder_keywords"])
        content_match = any(ck in text_lower for ck in content_kws) if text_lower else False
        regex_match = False
        if text_lower and regex_list:
            for r in regex_list:
                if re.search(r, text_lower, re.IGNORECASE):
                    regex_match = True
                    break

        # Decision matrix:
        # High confidence match:
        # A) Content/Regex match confirms it strongly, regardless of extension (if text extracted)
        # B) Compatible extension AND (stem match OR content match)
        # C) For Media/Photos/Videos: extension matches the media folder (e.g. .jpg inside "Viagens")
        is_media_domain = matched_domain["id"] in ["fotos_viagens", "musicas_audios", "videos_filmes"]

        if regex_match or content_match:
            is_valid = True
        elif ext_match and (stem_match or is_media_domain):
            is_valid = True
        elif ext_match and not text_lower and not stem_match and not is_media_domain:
            # Ambiguous (e.g. generic doc inside Boletos without text)
            is_valid = False
        else:
            is_valid = False

        if is_valid:
            return FolderHypothesisResult(
                is_semantic_folder=True,
                matches_hypothesis=True,
                is_intruder=False,
                folder_status="confirmado",
                origin_folder=clean_folder,
                suggested_category=matched_domain["category"],
                suggested_subcategoria=matched_domain["subcategoria"],
                suggested_caminho_fisico=matched_domain["caminho_fisico"],
                confidence=0.96,
                reason=f"Confirmado na pasta '{clean_folder}': conteúdo e formato correspondem ao tema {matched_domain['category']}."
            )
        else:
            return FolderHypothesisResult(
                is_semantic_folder=True,
                matches_hypothesis=False,
                is_intruder=True,
                folder_status="intruso",
                origin_folder=clean_folder,
                suggested_category=matched_domain["category"],
                suggested_subcategoria="",
                suggested_caminho_fisico=matched_domain["caminho_fisico"],
                confidence=0.35,
                reason=f"Intruso detectado na pasta '{clean_folder}': arquivo de tipo/conteúdo diferente do tema esperado."
            )
