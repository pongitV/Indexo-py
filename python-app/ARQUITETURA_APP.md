# Arquitetura da Aplicação Desktop (PySide6 / Qt) — Indexo

Este documento detalha a organização do pacote `python-app/app`, responsável pela interface visual, gerenciamento de estado, controladores de fluxo, subsistema de IA híbrida em cascata (3 Tiers) e integração com o motor nativo em Rust.

---

## Estrutura Modular do Pacote `app`

```text
python-app/
├── main.py                     # Ponto de entrada, Single-Instance Lock e inicialização do Onboarding
├── ARQUITETURA_APP.md          # Este documento descritivo
└── app/
    ├── main_window.py          # Janela principal com Root Stack (Menu, Workspace, Settings, Tags, Guia)
    │
    ├── ai/                     # Subsistema de Inteligência Artificial Híbrida (3 Tiers)
    │   ├── hardware_specs.py   # Diagnóstico Win32 de CPU/RAM com auto-profiling e recomendação de SLM
    │   ├── model_manager.py    # Gerenciador de catálogo e downloads no Hugging Face (data/models/)
    │   ├── vector_engine.py    # Motor ONNX Runtime para busca semântica vetorial (embeddings 384d)
    │   ├── llm_engine.py       # Inferência local de SLMs (Qwen 2.5) via llama.cpp com gramática GBNF
    │   ├── semantic_classifier.py # Classificador híbrido em cascata (Tier 1: Rust -> Tier 2: ONNX -> Tier 3: SLM)
    │   └── ai_tester.py        # Diagnóstico e teste de IA em tempo real com medição de latência em ms
    │
    ├── classification/         # Motores de similaridade, descoberta de tags, regras e validação
    │   ├── similarity_engine.py# Detecção de pacotes coesos (jogos, software, código, álbuns)
    │   ├── tag_discovery.py    # Síntese adaptativa de tags e categorias baseada na topologia real
    │   ├── folder_validator.py # Validação de coerência de pastas e detecção de arquivos intrusos
    │   ├── rule_loader.py      # Carregador e mesclador de regras do sistema e do usuário
    │   ├── confidence.py       # Algoritmos de cálculo de pontuação e limiares de confiança
    │   └── entity_regex.py     # Reconhecimento de entidades e padronização de nomenclatura de arquivos
    │
    ├── config/                 # Gerenciamento de configurações e persistência local
    │   ├── constants.py        # Constantes, extensões suportadas e limites operacionais
    │   └── settings_manager.py # Leitura e escrita atômica de preferências e user_rules.json
    │
    ├── extraction/             # Extratores de texto e metadados
    │   ├── pdf_extractor.py    # Extração de texto de documentos PDF via PyMuPDF
    │   ├── doc_extractor.py    # Extração de documentos DOCX, DOC e ODT
    │   └── ocr_engine.py       # Extração OCR local para imagens digitalizadas via Tesseract/OpenCV
    │
    ├── i18n/                   # Módulo de internacionalização dinâmica (ptBR / enUS)
    │   └── language_manager.py # Tradução reativa e troca instantânea de idioma em tempo real
    │
    ├── models/                 # Modelos de dados e Data Transfer Objects
    │   ├── file_item.py        # Dataclass do item de classificação e metadados
    │   └── rules.py            # Definições formais de esquemas de regras e tags
    │
    ├── onboarding/             # Assistente de primeiro uso
    │   └── onboarding_wizard.py# Wizard interativo de 2 etapas com diagnóstico e setup automático
    │
    ├── utils/                  # Utilitários de sistema, formatação e reversão WAL
    │   ├── file_ops.py         # Operações seguras de movimentação, colisão e WAL (.indexo_restore.json)
    │   ├── formatters.py       # Formatação amigável de bytes, datas e durações
    │   ├── logger_setup.py     # Configuração do Loguru para rotação e persistência de logs locais
    │   └── theme_manager.py    # Gerenciamento de temas claro/escuro/sistema e folhas de estilo QSS
    │
    ├── widgets/                # Componentes visuais PySide6 reutilizáveis e telas
    │   ├── organization_view.py# Árvore Antes x Depois, pacotes coesos e painel de execução/WAL
    │   ├── pending_list.py     # Fila Virtual de Revisão com botão "Classificar com IA"
    │   ├── duplicate_view.py   # Visualizador de duplicatas por SHA-256 e tamanho com métricas
    │   ├── stats_view.py       # Dashboard visual com gráficos estatísticos de volumetria
    │   ├── trash_view.py       # Lixeira de segurança interna da sessão
    │   ├── ai_live_inspector_view.py # Stream de raciocínio da IA em tempo real com passos detalhados
    │   ├── settings_view.py    # Painel completo de configurações, temas, fontes e AI Playground
    │   ├── tag_manager_view.py # Gerenciador dinâmico de tags, categorias, regex e palavras-chave
    │   ├── guide_view.py       # Guia interativo em 7 tópicos com badges de teclas e conceitos
    │   ├── palette.py          # Paleta de busca rápida Ctrl+K (FTS5 + Busca Vetorial)
    │   ├── preview_panel.py    # Painel lateral retrátil de visualização de arquivos e metadados
    │   ├── shortcuts_dialog.py # Diálogo modal com catálogo de atalhos de teclado
    │   ├── folder_review.py    # Painel de revisão e coerência de pastas
    │   ├── file_context_menu.py# Menu de contexto para ações rápidas nos itens
    │   ├── dry_run_tree.py     # Árvore de simulação pré-execução
    │   ├── lite_mode.py        # Modo de visualização compacto
    │   ├── tree_view.py        # Árvore virtual de navegação
    │   └── smooth_scroll.py    # Área de rolagem cinemática e suave
    │
    └── workers/                # QThreads para processamento assíncrono em segundo plano
        ├── index_worker.py     # Varredura multithreaded, extração e streaming de arquivos
        └── ai_worker.py        # Download de modelos e inferência de IA sem travar a interface
```

---

## Padrões de Implementação

* **Assincronismo Total**: Todo I/O pesado (varredura recursiva, OCR, parsing de PDF, embeddings ONNX e inferência de SLM) roda estritamente em `QThread` dedicada (`IndexWorker`, `AIWorker`), mantendo a interface gráfica permanentemente fluida e responsiva.
* **Gramática Formal Estrita (GBNF)**: A inferência de SLM (Qwen 2.5) utiliza GBNF para garantir 100% de conformidade com o esquema JSON esperado, eliminando totalmente alucinações de formato.
* **Isolamento e Portabilidade Absoluta**: Nenhuma chave de registro do Windows ou pasta do sistema (`%APPDATA%`) é alterada. Todos os dados e configurações residem nas pastas relativas `data/` e `configs/`.
