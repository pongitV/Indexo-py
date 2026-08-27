# Recursos Estaticos e Internacionalizacao — Indexo

Este diretorio contem os recursos estaticos da aplicacao, incluindo as regras de classificacao padrao, definicoes de internacionalizacao e artefatos visuais.

---

## Estrutura de Arquivos

```text
resources/
├── RECURSOS.md             # Este documento
├── system_rules.json       # Regras padrao de classificacao semantica
├── icon.ico                # Icone multi-resolucao do Windows (16 a 256 px)
├── icon.png                # Icone master em formato rasterizado PNG
└── i18n/                   # Dicionarios de traducao dinamica
    ├── ptBR.json           # Portugues do Brasil (Idioma padrao)
    └── enUS.json           # Ingles (Estados Unidos)
```

---

## Especificacao dos Componentes

### `system_rules.json`
Define o conjunto de regras do sistema para categorizacao de arquivos, englobando tags, caminhos sugeridos, expressoes regulares, palavras-chave e pesos ponderados para os seguintes dominios:
- **Financeiro**: Boletos bancarios, faturas de cartao, contas de consumo (energia, saneamento, telecomunicacoes), extratos de conta corrente e comprovantes de transferencia PIX.
- **Fiscal**: Notas fiscais eletronicas (DANFE), guias de arrecadacao (DARF, IPTU, IPVA, DAS-MEI), declaracoes de IRPF e extratos de FGTS.
- **Trabalho e Juridico**: Contracheques/holerites, contratos de prestacao de servicos, contratos de locacao, curriculos e certificados.
- **Midia**: Arquivos de imagem com metadados EXIF e fotografias.

### `i18n/`
Proporciona suporte a internacionalizacao em tempo de execucao sem necessidade de recompilacao. O carregamento de strings e gerenciado por `app.i18n.language_manager`.
