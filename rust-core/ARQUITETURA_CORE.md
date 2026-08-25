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
    │   ├── hasher.rs           # Calculo de hash SHA-256 e deteccao de duplicatas
    │   ├── db.rs               # Interface SQLite FTS5 em modo WAL com cache
    │   └── sanitizer.rs        # Validacao e sanitizacao de nomes de arquivo no Windows
    │
    ├── extraction/             # Extracao de metadados e conteudo textual
    │   ├── text.rs             # Leitura rapida de arquivos TXT/CSV/LOG
    │   ├── exif.rs             # Extracao de campos EXIF em imagens JPEG/TIFF
    │   └── audio.rs            # Leitura de metadados de audio (tags ID3)
    │
    ├── classification/         # Mecanismo de pontuacao semantica
    │   ├── matcher.rs          # Algoritmos Aho-Corasick e RegexSet linear
    │   └── scorer.rs           # Motor de scoring ponderado 70/20/10
    │
    └── utils/                  # Tratamento de caminhos e verificacoes de seguranca
        ├── paths.rs            # Normalizacao e caminhos portateis
        └── safety.rs           # Politicas de protecao do sistema operacional
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
