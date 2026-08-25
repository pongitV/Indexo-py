"""
Limpeza Automatizada de Arquivos Temporários, Caches e Resíduos de Build do Indexo.
"""

import os
import shutil
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent


def clean_project():
    print("=" * 55)
    print(" INDEXO - LIMPEZA DE ARQUIVOS TEMPORARIOS & CACHES")
    print("=" * 55)

    removed_files = 0
    removed_dirs = 0
    bytes_freed = 0

    def remove_file(p: Path):
        nonlocal removed_files, bytes_freed
        try:
            sz = p.stat().st_size
            p.unlink()
            removed_files += 1
            bytes_freed += sz
            print(f"[-] Removido arquivo: {p.relative_to(ROOT_DIR)}")
        except Exception as e:
            print(f"[!] Erro ao remover {p}: {e}")

    def remove_dir(p: Path):
        nonlocal removed_dirs, bytes_freed
        try:
            for root, dirs, files in os.walk(p):
                for f in files:
                    bytes_freed += (Path(root) / f).stat().st_size
            shutil.rmtree(p, ignore_errors=True)
            removed_dirs += 1
            print(f"[-] Removido diretorio: {p.relative_to(ROOT_DIR)}")
        except Exception as e:
            print(f"[!] Erro ao remover {p}: {e}")

    # 1. Limpar diretórios de cache Python
    for pycache in ROOT_DIR.rglob("__pycache__"):
        if ".git" not in str(pycache):
            remove_dir(pycache)

    # 2. Limpar arquivos compilados .pyc, .pyo, .pyd soltos fora do site-packages
    for ext in ["*.pyc", "*.pyo", "*.bak", "*.tmp"]:
        for f in ROOT_DIR.rglob(ext):
            if ".git" not in str(f) and "venv" not in str(f):
                remove_file(f)

    # 3. Limpar caches de teste (.pytest_cache, .coverage, htmlcov)
    for cache_name in [".pytest_cache", ".coverage", "htmlcov", ".mypy_cache", ".ruff_cache"]:
        for c in ROOT_DIR.rglob(cache_name):
            if ".git" not in str(c):
                if c.is_dir():
                    remove_dir(c)
                elif c.is_file():
                    remove_file(c)

    # 4. Limpar diretórios temporários de build (build_dist, build, dist, *.egg-info)
    for build_name in ["build_dist", "build", "dist"]:
        b_path = ROOT_DIR / build_name
        if b_path.exists():
            remove_dir(b_path)

    for egg in ROOT_DIR.rglob("*.egg-info"):
        if ".git" not in str(egg):
            remove_dir(egg)

    # 5. Limpar arquivos .bak, .bak.json e logs em Portable-EXE, configs e data
    for ext in ["*.log", "*.bak*", "*.tmp"]:
        for p in ROOT_DIR.rglob(ext):
            if ".git" not in str(p) and "venv" not in str(p):
                remove_file(p)

    for p in (ROOT_DIR / "configs").glob("*.bak*"):
        remove_file(p)

    for p in (ROOT_DIR / "Portable-EXE" / "configs").glob("*.bak*"):
        remove_file(p)

    print("=" * 55)
    print(f"RESULTADO: {removed_files} arquivos e {removed_dirs} pastas removidas.")
    print(f"Espaco liberado: {bytes_freed / 1024 / 1024:.2f} MB")
    print("=" * 55)


if __name__ == "__main__":
    clean_project()
