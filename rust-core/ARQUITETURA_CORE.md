# Motor de Processamento Nativo — Rust Core (`indexo_core`)

O `rust-core` e o motor de indexacao, extracao e classificacao do Indexo. Desenvolvido em Rust para maxima velocidade e seguranca de memoria, ele e disponibilizado para a camada Python por meio de bindings PyO3 compilados com Maturin.

---

## Modulos do Sistema

```text
rust-core/
├── Cargo.toml                  # Definicao do pacote e dependencias Rust
├── ARQUITETURA_CORE.md         # Este documento
└── src/
    ├── lib.rs                  # Ponto de entrada e exportacao de funcoes PyO3
    │
    ├── indexing/               # Varredura concorrente e persistencia
    │   ├── scanner.rs          # Varredura paralela de diretorios via Rayon
    │   ├── database.rs         # Interface SQLite FTS5 em modo WAL com cache
    │   ├── hashing.rs          # Calculo de hash SHA-256 e deteccao de duplicatas
    │   ├── sanitize.rs         # Validacao e sanitizacao de nomes de arquivo no Windows
    │   ├── migrations.rs       # Versionamento e migracoes do esquema SQLite
    │   └── mod.rs              # Modulo de indexacao e integracao
    │
    ├── extraction/             # Extracao de metadados e conteudo textual
    │   ├── text.rs             # Leitura rapida de arquivos TXT/CSV/LOG
    │   ├── image.rs            # Extracao de campos EXIF e dimensoes em imagens
    │   ├── audio.rs            # Leitura de metadados de audio (tags ID3)
    │   └── mod.rs              # Modulo de extracao de metadados
    │
    ├── classification/         # Mecanismo de pontuacao semantica
    │   ├── engine.rs           # Motor central de classificacao deterministica
    │   ├── matcher.rs          # Algoritmos Aho-Corasick e RegexSet linear
    │   ├── scoring.rs          # Motor de scoring ponderado e normalizacao
    │   └── mod.rs              # Modulo de classificacao nativa
    │
    └── utils/                  # Tratamento de caminhos e verificacoes de seguranca
        ├── path_resolver.rs    # Normalizacao e prevencao de Directory Traversal
        ├── error_handler.rs    # Tratamento e conversao de erros nativos para PyErr
        └── mod.rs              # Modulo de utilitarios de baixo nivel
```

---

## Procedimento de Compilacao

Para compilar a extensao nativa em modo de desenvolvimento:

```powershell
maturin develop --release
```

Para executar o conjunto de testes unitarios em Rust:

```powershell
$env:PYO3_USE_ABI3_FORWARD_COMPATIBILITY="1"; cargo test --manifest-path rust-core/Cargo.toml
```
