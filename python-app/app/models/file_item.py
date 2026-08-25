from dataclasses import dataclass, field, asdict
from typing import Optional, Dict, Any

@dataclass
class ClassificationItem:
    abs_path: str
    rel_path: str
    size: int = 0
    mtime: int = 0
    file_type: str = "other"
    category: str = "Outros"
    tag_name: str = ""
    confidence: float = 0.0
    status: str = "identificado"  # "identificado", "pendente", "duplicata", "lixeira"
    suggested_filename: Optional[str] = None
    destination_rel_path: Optional[str] = None
    is_duplicate: bool = False
    sha256_hash: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ClassificationItem":
        return cls(
            abs_path=str(data.get("abs_path", "")),
            rel_path=str(data.get("rel_path", "")),
            size=int(data.get("size", 0)),
            mtime=int(data.get("mtime", 0)),
            file_type=str(data.get("file_type", "other")),
            category=str(data.get("category", "Outros")),
            tag_name=str(data.get("tag_name", "")),
            confidence=float(data.get("confidence", 0.0)),
            status=str(data.get("status", "identificado")),
            suggested_filename=data.get("suggested_filename"),
            destination_rel_path=data.get("destination_rel_path"),
            is_duplicate=bool(data.get("is_duplicate", False)),
            sha256_hash=data.get("sha256_hash")
        )
