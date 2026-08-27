# Indexo Portable — Guia de Distribuição Portátil

<p align="center">
  <b>Indexo — Organizador Semântico e Indexador Inteligente de Arquivos para Windows</b><br>
  <i>Versão 100% Autônoma e Portátil (Zero Instalação · Zero Poluição do Sistema)</i>
</p>

---

## Como Funciona a Versão Portátil

O **Indexo Portable** foi projetado para operar com isolamento total do sistema operacional Windows:
* **Sem Instaladores**: Não requer privilégios de administrador para rodar.
* **Sem Gravação no `%APPDATA%` ou Registro**: Todas as configurações, regras de usuário e banco de dados SQLite ficam armazenados exclusivamente na pasta onde o executável se encontra.
* **Pronto para Pen-Drive**: Você pode colocar o `Indexo.exe` em um pen drive ou HD externo e usá-lo em qualquer computador Windows 10 / 11 (x64) mantendo todo o seu histórico e regras.

---

## Estrutura de Pastas Gerada Automaticamente

Ao executar o `Indexo.exe` pela primeira vez, ele inicializa a seguinte estrutura local:

```text
Portable-EXE/
├── Indexo.exe                      # Executável principal autônomo (PySide6 + Rust Core)
├── README.md                       # Este guia de uso e referência
│
├── configs/                        # Configurações do usuário
│   ├── settings.json               # Preferências de tema, idioma, fontes e limites
│   └── user_rules.json             # Regras semânticas personalizadas criadas pelo usuário
│
├── data/                           # Banco de dados e modelos locais
│   ├── indexo.db                   # Banco SQLite com índice FTS5 e metadados
│   └── models/                     # Modelos de IA locais baixados sob demanda (ONNX / GGUF)
│
└── logs/                           # Diagnósticos locais
    └── indexo.log                  # Registro de atividades e diagnósticos
```

---

## Recursos de IA Integrados

* **Busca Semântica no `Ctrl+K`**: Indexação vetorial ultraleve (ONNX Multilingual MiniLM ~60 MB) para encontrar arquivos por conceito e sinônimos.
* **Classificação com IA Local**: Suporte ao modelo **Qwen 2.5 (1.5B / 0.5B / 3B)** para raciocínio profundo de pastas e tags estruturadas em JSON sem sair do computador.
* **Download Sob Demanda**: Os modelos de IA podem ser baixados em 1 clique diretamente nas Configurações (`Ctrl+,`) do aplicativo.

---

## Como Recompilar a Versão Portátil

Para gerar um novo executável portátil após modificar o código-fonte:

```powershell
python scripts/build.py
```

O script compilará o núcleo nativo em Rust (`rust-core`) com otimizações `--release`, empacotará o executável standalone com PyInstaller e atualizará este diretório.
