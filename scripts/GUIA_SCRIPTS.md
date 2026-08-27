# Manual de Scripts de Automacao — Indexo

Este diretorio contem scripts utilitarios em Python voltados para desenvolvimento local, verificacao de qualidade, construcao de binarios portateis e geracao de conjuntos de dados de teste.

---

## Descricao dos Scripts

### 1. `dev_run.py`
Executa o Indexo diretamente em ambiente de desenvolvimento local a partir do codigo-fonte.

```powershell
python scripts/dev_run.py
```

### 2. `check.py`
Script de diagnostico e verificacao unificada de qualidade:
1. Valida a integridade do arquivo `resources/system_rules.json` e compila todas as expressoes regulares.
2. Valida a paridade completa entre as chaves de traducao `ptBR.json` e `enUS.json`.
3. Executa a suite de testes unitarios em Rust (`cargo test`).
4. Executa a suite de testes em Python e integracao (`pytest`).
5. Emite relatorio consolidado de conformidade com tempo de execucao.

```powershell
python scripts/check.py
```

### 3. `build.py`
Executa o pipeline completo de compilacao e empacotamento:
1. Gera os icones multi-resolucao do Windows (`icon.ico`).
2. Compila a extensao nativa em Rust utilizando `maturin` em modo release e instala o binario wheel gerado.
3. Injeta os metadados de versao PE do Windows (`VS_VERSION_INFO`) no binario.
4. Empacota a aplicacao com `PyInstaller` em executavel unico 100% autonomo e portatil (`Portable-EXE/Indexo.exe` via `--onefile`) com todos os recursos e modelos embutidos.
5. Notifica o Windows Explorer para atualizar o cache de icones imediatamente via chamada Win32.

```powershell
python scripts/build.py
```

### 4. `generate_test_dataset.py`
Gera uma base de testes sintetica e diversificada para avaliacao de regras semanticas:
- Documentos PDF pesquisaveis (boletos bancarios com linha digitavel, faturas de concessionarias, faturas de cartao, guias tributarias DARF/IPTU/IPVA/DAS-MEI, notas fiscais DANFE, contracheques, contratos e curriculos).
- Arquivos de texto TXT com termos-chave (comprovantes PIX, declaracoes, comprovantes cadastrais).
- Imagens JPEG contendo metadados EXIF reais (modelos de camera, datas de captura e dimensoes variadas).
- Duplicatas exatas para validacao do detector de integridade SHA-256.
- Estrutura hierarquica mista para testes de varredura recursiva.

```powershell
# Geracao padrao em pasta_testes_indexo/
python scripts/generate_test_dataset.py

# Geracao em caminho customizado:
python scripts/generate_test_dataset.py --output "C:\caminho\para\pasta_destino"
```

### 5. `clean.py`
Executa a limpeza automatizada de arquivos temporários, caches e resíduos de compilação:
- Remove todos os diretórios `__pycache__` e arquivos compilados `.pyc`/`.pyo`.
- Remove diretórios de cache de testes (`.pytest_cache`, `.coverage`, `htmlcov`).
- Remove pastas temporárias de build (`build_dist`, `build`, `dist`, `*.egg-info`).
- Limpa arquivos temporários de backup e logs de teste em `data/` e `Portable-EXE/`.

```powershell
python scripts/clean.py
```

