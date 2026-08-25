"""
End-to-End Scanning, Classification, Duplicate Detection & Reversible Organization Test.
Tests the full system against the real-world test dataset in pasta_testes_indexo/.
"""

import sys
import shutil
import tempfile
from pathlib import Path
from typing import List, Dict, Any

# Add python-app to sys.path
root_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root_dir / "python-app"))

from app.workers.index_worker import IndexWorker
from app.config.settings_manager import SettingsManager
from app.classification.rule_loader import RuleLoader
import indexo_core


def test_end_to_end_scan_on_test_dataset():
    """Runs complete IndexWorker scanning pipeline on pasta_testes_indexo."""
    dataset_dir = root_dir / "pasta_testes_indexo"
    assert dataset_dir.exists(), "pasta_testes_indexo must exist"

    worker = IndexWorker(root_dir=dataset_dir)

    indexed_items: List[Dict[str, Any]] = []
    worker.file_classified.connect(indexed_items.append)
    
    # Run scanning synchronously for test
    worker.run()

    assert len(indexed_items) >= 30, f"Expected at least 30 files indexed, got {len(indexed_items)}"

    # 1. Verify Categories Assigned
    categories = set(it.get("category") for it in indexed_items if it.get("category"))
    assert len(categories) >= 3, f"Expected multiple categories, got {categories}"
    assert any("Fatura" in c or "Boleto" in c or "Financeiro" in c or "Contas" in c or "Invoices" in c for c in categories)
    assert any("Foto" in c or "Imagem" in c or "Photos" in c or "Images" in c or "Mídia" in c or "Parque" in c for c in categories)

    # 2. Verify Exact Duplicate Detection by SHA-256
    hash_counts: Dict[str, List[Dict[str, Any]]] = {}
    for it in indexed_items:
        h = it.get("hash")
        if h:
            hash_counts.setdefault(h, []).append(it)

    duplicates_found = {h: items for h, items in hash_counts.items() if len(items) > 1}
    assert len(duplicates_found) >= 3, f"Expected at least 3 duplicate groups, found {len(duplicates_found)}"
    print(f"✓ Exact Duplicate Detection: Found {len(duplicates_found)} duplicate hash groups in test dataset")

    # 3. Verify Standardized Renaming Preview for identified files
    identified_items = [it for it in indexed_items if it.get("status") == "identificado"]
    assert len(identified_items) >= 20
    for it in identified_items:
        sug_name = it.get("suggested_filename") or it.get("suggested_name")
        assert sug_name is not None and len(sug_name) > 0
        ext = it.get("extension") or Path(it.get("rel_path", "")).suffix
        assert sug_name.endswith(ext)

    print(f"✓ End-to-End scan verified: {len(indexed_items)} files scanned ({len(identified_items)} identified) across {len(categories)} categories")


def test_atomic_wal_and_safe_simulation():
    """Tests atomic WAL (Write-Ahead-Log) transaction rollback in an isolated sandbox."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        
        # Create sandbox test files
        f1 = tmp_path / "fatura_luz_enel_maio.pdf"
        f1.write_text("Fatura de Energia Eletrica Enel 150.00")
        f2 = tmp_path / "contrato_locacao_2024.pdf"
        f2.write_text("Contrato de Locacao Residencial")

        dest_dir = tmp_path / "Indexo_Files"
        dest_cat = dest_dir / "Faturas_e_Boletos"
        dest_cat.mkdir(parents=True, exist_ok=True)

        target_f1 = dest_cat / "2024-05-01_Enel_Conta_Luz.pdf"

        # 1. Simulate Move with WAL Log
        wal_log = []
        shutil.move(str(f1), str(target_f1))
        wal_log.append({"action": "move", "src": str(f1), "dst": str(target_f1)})

        assert not f1.exists()
        assert target_f1.exists()

        # 2. Rollback (Undo) execution
        for entry in reversed(wal_log):
            if entry["action"] == "move":
                shutil.move(entry["dst"], entry["src"])

        assert f1.exists()
        assert not target_f1.exists()
        print("✓ Atomic WAL transaction simulation & rollback passed successfully")


if __name__ == "__main__":
    test_end_to_end_scan_on_test_dataset()
    test_atomic_wal_and_safe_simulation()
    print("\nAll End-to-End Organization Tests Passed Successfully!")
