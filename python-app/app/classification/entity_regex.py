import re
from datetime import datetime
from typing import Optional, List, Tuple, Dict, Any, Set

RE_DATE_BR = re.compile(r"\b(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})\b")
RE_DATE_ISO = re.compile(r"\b(\d{4})[/.-](\d{1,2})[/.-](\d{1,2})\b")
RE_VALUE_BRL = re.compile(r"(?:R\$\s*|VALOR(?:\s+A\s+PAGAR|\s+TOTAL)?[:\s]*R?\$?\s*)(\d{1,3}(?:\.\d{3})*,\d{2})", re.IGNORECASE)
RE_DUE_DATE = re.compile(r"(?:VENCIMENTO|VENC\.?|DUE\s+DATE)[:\s]*(\d{1,2}[/.-]\d{1,2}[/.-]\d{4})", re.IGNORECASE)
RE_CNPJ = re.compile(r"\b\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}\b")
RE_CPF = re.compile(r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b")

STOPWORDS: Set[str] = {
    "a", "o", "as", "os", "de", "da", "do", "das", "dos", "em", "no", "na", "nos", "nas",
    "por", "para", "com", "sem", "sob", "sobre", "e", "ou", "se", "que", "como", "um", "uma",
    "uns", "umas", "ao", "aos", "pelo", "pela", "pelos", "pelas", "este", "esta", "isto",
    "esse", "essa", "isso", "aquele", "aquela", "aquilo", "seu", "sua", "seus", "suas",
    "meu", "minha", "nosso", "nossa", "nossos", "nossas", "foi", "sao", "ser", "ter",
    "documento", "arquivo", "pagina", "folha", "via", "pdf", "docx", "txt", "png", "jpg"
}

def extract_primary_date(text: str, file_mtime: int = 0) -> str:
    """Extracts the most relevant date from text in standard ISO format YYYY-MM-DD, or falls back to mtime."""
    # 1. Prefer explicit due date if found
    due_match = RE_DUE_DATE.search(text)
    if due_match:
        raw_due = due_match.group(1)
        d_m_y = re.split(r"[/.-]", raw_due)
        if len(d_m_y) == 3:
            try:
                day, month, year = int(d_m_y[0]), int(d_m_y[1]), int(d_m_y[2])
                if 1970 <= year <= 2050 and 1 <= month <= 12 and 1 <= day <= 31:
                    return f"{year:04d}-{month:02d}-{day:02d}"
            except Exception:
                pass

    # 2. Look for ISO dates
    for y, m, d in RE_DATE_ISO.findall(text):
        try:
            year, month, day = int(y), int(m), int(d)
            if 1970 <= year <= 2050 and 1 <= month <= 12 and 1 <= day <= 31:
                return f"{year:04d}-{month:02d}-{day:02d}"
        except Exception:
            continue

    # 3. Look for BR dates
    for d, m, y in RE_DATE_BR.findall(text):
        try:
            year, month, day = int(y), int(m), int(d)
            if 1970 <= year <= 2050 and 1 <= month <= 12 and 1 <= day <= 31:
                return f"{year:04d}-{month:02d}-{day:02d}"
        except Exception:
            continue

    # Fallback to mtime
    if file_mtime > 0:
        try:
            dt = datetime.fromtimestamp(file_mtime)
            return dt.strftime("%Y-%m-%d")
        except Exception:
            pass

    return datetime.now().strftime("%Y-%m-%d")

def extract_amount(text: str) -> Optional[str]:
    """Extracts financial amounts like R$ 150,00 from document text."""
    matches = RE_VALUE_BRL.findall(text)
    if matches:
        # Return first valid monetary value formatted
        return f"R${matches[0]}"
    return None

def extract_due_date(text: str) -> Optional[str]:
    """Extracts explicit due date string (e.g. 15/05/2024)."""
    match = RE_DUE_DATE.search(text)
    if match:
        return match.group(1)
    return None

def extract_keywords_from_text(text: str, filename: str) -> List[str]:
    """Extracts salient tokens for user tag auto-learning from reclassified documents."""
    tokens = re.split(r"[^\w]+", f"{filename} {text}".lower())
    freq: Dict[str, int] = {}
    for t in tokens:
        if len(t) >= 4 and not t.isdigit() and t not in STOPWORDS:
            freq[t] = freq.get(t, 0) + 1

    sorted_keywords = sorted(freq.items(), key=lambda kv: kv[1], reverse=True)
    return [kw for kw, count in sorted_keywords[:6]]

def format_custom_date(iso_date: str, date_format: str = "YYYY-MM-DD") -> str:
    """Formats an ISO date (YYYY-MM-DD) into user selected format."""
    if not iso_date:
        return ""
    try:
        parts = iso_date.split("-")
        if len(parts) == 3:
            year, month, day = parts[0], parts[1], parts[2]
            if date_format == "YYYY-MM-DD":
                return f"{year}-{month}-{day}"
            elif date_format == "YYYY_MM_DD":
                return f"{year}_{month}_{day}"
            elif date_format == "YYYYMMDD":
                return f"{year}{month}{day}"
            elif date_format == "DD-MM-YYYY":
                return f"{day}-{month}-{year}"
            elif date_format == "DD_MM_YYYY":
                return f"{day}_{month}_{year}"
            elif date_format == "DDMMYYYY":
                return f"{day}{month}{year}"
            elif date_format == "MM-DD-YYYY":
                return f"{month}-{day}-{year}"
    except Exception:
        pass
    return iso_date

def apply_casing(text: str, casing: str = "title") -> str:
    if not text:
        return ""
    if casing == "lower":
        return text.lower()
    elif casing == "upper":
        return text.upper()
    elif casing == "title":
        words = re.split(r"([_\s-]+)", text)
        return "".join(w.capitalize() if not re.match(r"^[_\s-]+$", w) else w for w in words)
    return text

def generate_standard_filename(
    date_str: str,
    entity: Optional[str],
    category_or_tag: str,
    original_ext: str,
    original_stem: str = "",
    config: Optional[Dict[str, Any]] = None,
    amount: Optional[str] = None
) -> str:
    """Generates standardized filename with fully customizable pattern, position, date format, casing, and separator."""
    cfg = config or {}
    sep = cfg.get("rename_separator", " - ")
    date_pos = cfg.get("rename_date_position", "suffix")
    date_fmt = cfg.get("rename_date_format", "DD-MM-YYYY")
    casing = cfg.get("rename_casing", "title")

    formatted_date = format_custom_date(date_str, date_fmt) if date_str else ""
    
    parts = []
    def clean_item(s: str) -> str:
        s = s.strip()
        if sep in [" - ", " "]:
            s = s.replace("_", " ")
        elif sep == "_":
            s = s.replace(" ", "_").replace("-", "_")
        elif sep == "-":
            s = s.replace(" ", "-").replace("_", "-")
        elif sep == ".":
            s = s.replace(" ", ".").replace("_", ".")
        return apply_casing(s, casing)

    if entity and entity.strip():
        parts.append(clean_item(entity))
    if category_or_tag and category_or_tag.strip():
        parts.append(clean_item(category_or_tag))
    if amount and amount.strip():
        parts.append(clean_item(amount))

    if not parts:
        if original_stem:
            parts.append(clean_item(original_stem))
        else:
            parts.append("File" if casing == "original" else apply_casing("File", casing))

    # Assemble with date position
    if date_pos == "prefix" and formatted_date:
        final_parts = [formatted_date] + parts
    elif date_pos == "suffix" and formatted_date:
        final_parts = parts + [formatted_date]
    else:
        final_parts = parts

    base = sep.join(final_parts)
    ext = original_ext if original_ext.startswith(".") else f".{original_ext}" if original_ext else ""
    return f"{base}{ext}"
