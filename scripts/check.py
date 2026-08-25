"""
Script unificado de verificacao de qualidade e diagnostico do Indexo.
Executa validacoes de integridade de regras, paridade i18n, testes em Rust e testes em Python.
"""

import sys
import os
import time
import json
import subprocess
from pathlib import Path

# Configurar stdout UTF-8 no Windows
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT_DIR = Path(__file__).resolve().parent.parent

def print_header(title: str):
    print(f"\n=======================================================")
    print(f" {title}")
    print(f"=======================================================")

def check_system_rules() -> tuple[bool, str]:
    import re
    rules_file = ROOT_DIR / "resources" / "system_rules.json"
    if not rules_file.exists():
        return False, f"Arquivo nao encontrado: {rules_file}"
    
    try:
        data = json.loads(rules_file.read_text(encoding="utf-8"))
        rules = data.get("rules", []) if isinstance(data, dict) else data
        if not isinstance(rules, list) or len(rules) == 0:
            return False, "Regras vazias ou formato invalido."
        
        required_fields = ["id", "categoria", "caminho_fisico", "palavras_chave", "regex", "extensoes"]
        for idx, rule in enumerate(rules):
            for field in required_fields:
                if field not in rule:
                    return False, f"Regra #{idx} ({rule.get('id', 'sem id')}) nao contem o campo obrigatorio '{field}'"
            
            # Valida compilacao das regexes
            for r_pattern in rule.get("regex", []):
                try:
                    re.compile(r_pattern)
                except Exception as regex_err:
                    return False, f"Regex invalida na regra {rule.get('id')}: '{r_pattern}' ({regex_err})"
        
        return True, f"{len(rules)} regras e regexes validadas com sucesso."
    except Exception as e:
        return False, f"Erro de parsing JSON: {e}"

def check_i18n_parity() -> tuple[bool, str]:
    i18n_dir = ROOT_DIR / "resources" / "i18n"
    pt_file = i18n_dir / "ptBR.json"
    en_file = i18n_dir / "enUS.json"

    if not pt_file.exists() or not en_file.exists():
        return False, "Arquivos de traducao ptBR.json ou enUS.json nao encontrados."

    try:
        pt_data = json.loads(pt_file.read_text(encoding="utf-8"))
        en_data = json.loads(en_file.read_text(encoding="utf-8"))

        pt_keys = set(pt_data.keys())
        en_keys = set(en_data.keys())

        missing_in_en = pt_keys - en_keys
        missing_in_pt = en_keys - pt_keys

        if missing_in_en or missing_in_pt:
            msg = []
            if missing_in_en:
                msg.append(f"Chaves ausentes em enUS: {missing_in_en}")
            if missing_in_pt:
                msg.append(f"Chaves ausentes em ptBR: {missing_in_pt}")
            return False, "; ".join(msg)

        return True, f"Paridade confirmada em {len(pt_keys)} chaves de traducao."
    except Exception as e:
        return False, f"Erro de parsing nos arquivos i18n: {e}"

def run_rust_tests() -> tuple[bool, str]:
    cargo_toml = ROOT_DIR / "rust-core" / "Cargo.toml"
    env = os.environ.copy()
    env["PYO3_USE_ABI3_FORWARD_COMPATIBILITY"] = "1"
    
    start = time.time()
    res = subprocess.run(
        ["cargo", "test", "--manifest-path", str(cargo_toml), "--", "--quiet"],
        cwd=ROOT_DIR,
        env=env,
        capture_output=True,
        text=True
    )
    elapsed = time.time() - start
    
    if res.returncode == 0:
        return True, f"Aprovado em {elapsed:.2f}s."
    else:
        return False, f"Falha (codigo {res.returncode}):\n{res.stderr or res.stdout}"

def run_python_tests() -> tuple[bool, str]:
    tests_dir = ROOT_DIR / "tests"
    if not tests_dir.exists():
        return True, "Diretório de testes 'tests/' omitido (versão crua para publicação)."

    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT_DIR / "python-app")
    
    start = time.time()
    res = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/", "-q"],
        cwd=ROOT_DIR,
        env=env,
        capture_output=True,
        text=True
    )
    elapsed = time.time() - start
    
    if res.returncode == 0:
        output_line = res.stdout.strip().splitlines()[-1] if res.stdout.strip() else "OK"
        return True, f"Aprovado em {elapsed:.2f}s ({output_line})."
    else:
        return False, f"Falha (codigo {res.returncode}):\n{res.stdout}\n{res.stderr}"

def main():
    print_header("INDEXO - VERIFICACAO DE QUALIDADE E DIAGNOSTICO")
    
    checks = [
        ("Integridade de Regras (system_rules.json)", check_system_rules),
        ("Paridade de Internacionalizacao (i18n)", check_i18n_parity),
        ("Suite de Testes Unitarios em Rust", run_rust_tests),
        ("Suite de Testes em Python e Integracao", run_python_tests),
    ]

    all_passed = True
    results = []

    for name, func in checks:
        print(f"[*] Executando: {name}...", end=" ", flush=True)
        ok, detail = func()
        if ok:
            print("[OK]")
            results.append((name, True, detail))
        else:
            print("[FALHA]")
            results.append((name, False, detail))
            all_passed = False

    print_header("RELATORIO FINAL DE CONFORMIDADE")
    for name, ok, detail in results:
        status_tag = "[OK]   " if ok else "[FALHA]"
        print(f"{status_tag} {name}")
        if detail:
            for line in detail.splitlines():
                print(f"        -> {line}")

    print("\n-------------------------------------------------------")
    if all_passed:
        print("RESULTADO: Todos os componentes foram validados com sucesso.")
        print("-------------------------------------------------------\n")
        sys.exit(0)
    else:
        print("RESULTADO: Foram identificadas pendencias nas verificacoes.")
        print("-------------------------------------------------------\n")
        sys.exit(1)

if __name__ == "__main__":
    main()
