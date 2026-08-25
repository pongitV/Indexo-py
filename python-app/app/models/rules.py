from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict, Any

@dataclass
class RuleDefinition:
    id: str
    nome: str
    categoria: str
    subcategoria: Optional[str] = None
    entidade: Optional[str] = None
    caminho_fisico: str = ""
    origem: str = "user"  # "system" or "user"
    categoria_key: Optional[str] = None
    palavras_chave: List[str] = field(default_factory=list)
    regex: List[str] = field(default_factory=list)
    extensoes: List[str] = field(default_factory=list)
    confianca_base: float = 1.0
    usar_para_automacao: bool = True
    idioma: Optional[str] = "ptBR"
    sinonimos: List[str] = field(default_factory=list)
    version: int = 1

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RuleDefinition":
        return cls(
            id=str(data.get("id", "")),
            nome=str(data.get("nome", "")),
            categoria=str(data.get("categoria", "Outros")),
            subcategoria=data.get("subcategoria"),
            entidade=data.get("entidade"),
            caminho_fisico=str(data.get("caminho_fisico", "")),
            origem=str(data.get("origem", "user")),
            categoria_key=data.get("categoria_key"),
            palavras_chave=list(data.get("palavras_chave", [])),
            regex=list(data.get("regex", [])),
            extensoes=list(data.get("extensoes", [])),
            confianca_base=float(data.get("confianca_base", 1.0)),
            usar_para_automacao=bool(data.get("usar_para_automacao", True)),
            idioma=data.get("idioma", "ptBR"),
            sinonimos=list(data.get("sinonimos", [])),
            version=int(data.get("version", 1))
        )
