import re
from typing import Dict, List, Optional, Tuple

RE_BOLETO_44 = re.compile(r"\b\d{44}\b")
RE_BOLETO_LINHA = re.compile(r"\b\d{5}\.?\d{5}\s*\d{5}\.?\d{6}\s*\d{5}\.?\d{6}\s*\d\s*\d{14}\b")
RE_CPF = re.compile(r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b")
RE_CNPJ = re.compile(r"\b\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}\b")
RE_DARF = re.compile(r"\bDARF\b|\bdocumento\s+de\s+arrecada[cç][aã]o\s+de\s+receitas\s+federais\b", re.IGNORECASE)
RE_DANFE = re.compile(r"\bDANFE\b|\bdocumento\s+auxiliar\s+da\s+nota\s+fiscal\b", re.IGNORECASE)

def extract_identifiers(text: str) -> Dict[str, List[str]]:
    """Extracts strong numeric identifiers from text for FTS and scoring."""
    cpfs = RE_CPF.findall(text)
    cnpjs = RE_CNPJ.findall(text)
    
    boletos = []
    for b in RE_BOLETO_44.findall(text):
        if b not in boletos:
            boletos.append(b)
    for b in RE_BOLETO_LINHA.findall(text):
        clean_b = re.sub(r"[\s\.]", "", b)
        if clean_b not in boletos:
            boletos.append(clean_b)

    return {
        "cpf": list(set(cpfs)),
        "cnpj": list(set(cnpjs)),
        "boleto": boletos
    }
