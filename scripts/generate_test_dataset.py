"""
Script para geração de base de testes rica e diversificada para o Indexo.
Cria arquivos PDF reais com texto pesquisável, imagens JPG com EXIF e metadados,
arquivos TXT com palavras-chave de regras brasileiras, duplicatas exatas para testar SHA-256
e estrutura de pastas mista.
"""

import os
import shutil
import pymupdf  # PyMuPDF
from PIL import Image, ImageDraw, ImageFont
import piexif
import argparse

DEFAULT_OUTPUT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "pasta_testes_indexo",
)

def create_pdf(filepath: str, title: str, content_lines: list[str]):
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842) # A4
    
    # Header
    page.insert_text((50, 60), title, fontsize=18, fontname="helv", color=(0.1, 0.2, 0.5))
    page.draw_line((50, 75), (545, 75), color=(0.7, 0.7, 0.7), width=1)
    
    # Content
    y = 105
    for line in content_lines:
        if line.startswith("## "):
            y += 10
            page.insert_text((50, y), line[3:], fontsize=13, fontname="helv", color=(0.2, 0.3, 0.4))
            y += 20
        else:
            page.insert_text((50, y), line, fontsize=10, fontname="helv", color=(0.1, 0.1, 0.1))
            y += 16
            
    doc.save(filepath)
    doc.close()

def create_jpg_with_exif(filepath: str, width: int = 800, height: int = 600, color=(100, 150, 200), text: str = "", date_str: str = "2024:05:15 14:30:00", make: str = "Canon", model: str = "EOS Rebel T7"):
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    img = Image.new("RGB", (width, height), color=color)
    draw = ImageDraw.Draw(img)
    
    # Draw simple gradient/rectangles to make it look like a photo
    draw.rectangle([20, 20, width - 20, height - 20], outline=(255, 255, 255), width=3)
    draw.text((40, 40), text if text else "Indexo Test Image", fill=(255, 255, 255))
    
    # EXIF data
    zeroth_ifd = {
        piexif.ImageIFD.Make: make.encode("utf-8"),
        piexif.ImageIFD.Model: model.encode("utf-8"),
        piexif.ImageIFD.Software: b"Indexo Test Generator",
        piexif.ImageIFD.DateTime: date_str.encode("utf-8"),
    }
    exif_ifd = {
        piexif.ExifIFD.DateTimeOriginal: date_str.encode("utf-8"),
        piexif.ExifIFD.DateTimeDigitized: date_str.encode("utf-8"),
        piexif.ExifIFD.ISOSpeedRatings: 200,
    }
    exif_dict = {"0th": zeroth_ifd, "Exif": exif_ifd, "GPS": {}, "1st": {}, "thumbnail": None}
    exif_bytes = piexif.dump(exif_dict)
    
    img.save(filepath, "JPEG", exif=exif_bytes, quality=90)

def create_txt(filepath: str, content: str):
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

def generate_dataset(output_dir: str = DEFAULT_OUTPUT_DIR):
    if os.path.exists(output_dir):
        print(f"Limpando pasta de testes existente: {output_dir}")
        shutil.rmtree(output_dir)
        
    os.makedirs(output_dir, exist_ok=True)
    
    print(f"Gerando arquivos de teste em: {output_dir}\n")
    
    # 1. PDFs - Boletos e Faturas
    create_pdf(
        os.path.join(output_dir, "Boleto_Bancario_Banco_do_Brasil.pdf"),
        "BANCO DO BRASIL - COMPROVANTE DE COBRANÇA",
        [
            "Linha Digitável: 00190.00009 01234.567890 12345.678901 5 91230000025000",
            "Vencimento: 25/08/2024",
            "Beneficiário: Prestadora de Serviços LTDA - CNPJ: 12.345.678/0001-90",
            "Pagável em qualquer banco até o vencimento.",
            "Cedente: Banco do Brasil S.A. | Sacado: Fulano de Tal",
            "Nosso Número: 12345678901234567",
            "Valor do Documento: R$ 250,00",
            "Instruções: Não receber após o vencimento sem juros."
        ]
    )
    
    create_pdf(
        os.path.join(output_dir, "Fatura_Conta_Luz_Enel_Maio2024.pdf"),
        "ENEL DISTRIBUIÇÃO - CONTA DE ENERGIA ELÉTRICA",
        [
            "Distribuidora de Energia: ENEL SP S.A.",
            "Conta de Luz - Mês de Referência: 05/2024",
            "Consumo Ativo: 285 kWh",
            "Bandeira Tarifária: Verde",
            "CIP Ilum Pub: R$ 14,50",
            "Total a Pagar: R$ 198,40",
            "Data de Vencimento: 15/06/2024"
        ]
    )
    
    create_pdf(
        os.path.join(output_dir, "Conta_Agua_Sabesp_Junho2024.pdf"),
        "SABESP - COMPANHIA DE SANEAMENTO BÁSICO",
        [
            "Água e Esgoto - Conta de Água",
            "Sabesp - Fornecimento e Tratamento",
            "Hidrômetro: A23B9876",
            "Leitura Anterior: 1042 m3 | Leitura Atual: 1058 m3",
            "Volume Faturado: 16 m3",
            "Tarifa de Água: R$ 54,20 | Tarifa de Esgoto: R$ 54,20",
            "Total da Fatura: R$ 108,40"
        ]
    )
    
    create_pdf(
        os.path.join(output_dir, "Fatura_Vivo_Fibra_Internet.pdf"),
        "VIVO FIBRA - TELEFÔNICA BRASIL S.A.",
        [
            "Fatura Mensal de Telecomunicações",
            "Plano: Vivo Fibra 500 Mega + Minutos de Voz Ilimitados",
            "Banda Larga Residencial e Franquia de Internet ilimitada",
            "Telefônica Brasil S.A. - CNPJ: 02.558.157/0001-62",
            "Combo Multi - Período de Apuração: 01/06/2024 a 30/06/2024",
            "Valor Total: R$ 149,99"
        ]
    )

    create_pdf(
        os.path.join(output_dir, "Fatura_Cartao_Nubank_Julho2024.pdf"),
        "NUBANK - FATURA DO CARTÃO DE CRÉDITO",
        [
            "Nu Pagamentos S.A. - Mastercard Gold",
            "Fatura do Cartão de Crédito - Vencimento: 10/07/2024",
            "Total da Fatura: R$ 1.450,80",
            "Pagamento Mínimo: R$ 210,00",
            "Limite Total: R$ 8.000,00 | Limite Disponível: R$ 6.549,20",
            "Resumo de Gastos: Mercado R$ 650,00, Combustível R$ 300,00, Farmácia R$ 120,00"
        ]
    )

    # 2. PDFs - Impostos, Documentos e Contratos
    create_pdf(
        os.path.join(output_dir, "Documento_DARF_Receita_Federal.pdf"),
        "MINISTÉRIO DA FAZENDA - SECRETARIA DA RECEITA FEDERAL",
        [
            "DARF - Documento de Arrecadação de Receitas Federais",
            "Código da Receita: 0190",
            "Período de Apuração: 31/05/2024",
            "Número de Referência: 020492819",
            "Data de Vencimento: 28/06/2024",
            "Valor Principal: R$ 412,50"
        ]
    )
    
    create_pdf(
        os.path.join(output_dir, "Guia_IPTU_Exercicio_2024.pdf"),
        "PREFEITURA MUNICIPAL - SECRETARIA MUNICIPAL DA FAZENDA",
        [
            "IPTU - Imposto Predial e Territorial Urbano",
            "Exercício: 2024",
            "Inscrição Imobiliária: 192.048.1092-1",
            "Valor Venal do Imóvel: R$ 380.000,00",
            "Cota Única com Desconto ou 10 parcelas mensais",
            "Vencimento Cota Única: 10/02/2024"
        ]
    )
    
    create_pdf(
        os.path.join(output_dir, "Licenciamento_IPVA_2024_SP.pdf"),
        "SECRETARIA DA FAZENDA E PLANEJAMENTO - DETRAN",
        [
            "IPVA - Imposto sobre a Propriedade de Veículos Automotores",
            "RENAVAM: 00987654321",
            "Placa do Veículo: ABC1D23",
            "Taxa de Licenciamento Anual e Seguro DPVAT",
            "Exercício: 2024 - Quitado integralmente"
        ]
    )

    create_pdf(
        os.path.join(output_dir, "DAS_MEI_Simples_Nacional_2024.pdf"),
        "SIMPLES NACIONAL - PGMEI",
        [
            "Documento de Arrecadação do Simples Nacional - DAS MEI",
            "Microempreendedor Individual",
            "Contribuição Previdenciária - INSS MEI",
            "ICMS / ISSQN",
            "Período de Apuração: 05/2024 - Valor: R$ 75,00"
        ]
    )
    
    create_pdf(
        os.path.join(output_dir, "DANFE_Nota_Fiscal_Eletronica_10492.pdf"),
        "DANFE - DOCUMENTO AUXILIAR DA NOTA FISCAL ELETRÔNICA",
        [
            "Chave de Acesso: 3524 0512 3456 7800 0190 5500 1000 0104 9212 3456 7890",
            "Nota Fiscal Eletrônica - NFe Nº 000.010.492 - Série 1",
            "Protocolo de Autorização de Uso: 135240098765432",
            "Inscrição Estadual: 110.234.567.890",
            "Natureza da Operação: Venda de Mercadoria",
            "Destinatário/Remetente: Consumidor Final",
            "Dados dos Produtos/Serviços: Notebook Dell Inspiron 15",
            "Valor Total da Nota: R$ 4.299,00"
        ]
    )
    
    create_pdf(
        os.path.join(output_dir, "Holerite_Mensal_Contracheque_Junho.pdf"),
        "DEMONSTRATIVO DE PAGAMENTO DE SALÁRIO",
        [
            "Recibo de Pagamento de Salário - Holerite / Contracheque",
            "Mês de Referência: 06/2024",
            "Salário Base: R$ 7.500,00",
            "Proventos: Salário R$ 7.500,00, Adicional Noturno R$ 300,00",
            "Descontos: INSS R$ 850,00, IRRF R$ 620,00, Vale Transporte R$ 150,00",
            "FGTS do Mês: R$ 624,00",
            "Salário Líquido: R$ 6.180,00",
            "Total de Vencimentos: R$ 7.800,00"
        ]
    )
    
    create_pdf(
        os.path.join(output_dir, "Extrato_FGTS_Caixa_Economica.pdf"),
        "CAIXA ECONÔMICA FEDERAL - FGTS",
        [
            "Extrato do FGTS - Fundo de Garantia do Tempo de Serviço",
            "PIS/PASEP: 120.49281.90-2",
            "Conta Vinculada: 00928371-0",
            "Depósito FGTS referente à competência 05/2024",
            "Saldo Atual Disponível: R$ 24.530,90"
        ]
    )

    create_pdf(
        os.path.join(output_dir, "Extrato_Bancario_Conta_Corrente.pdf"),
        "EXTRATO DE CONTA CORRENTE - BANCO ITAÚ",
        [
            "Extrato Mensal de Lançamentos",
            "Agência: 1234 | Conta: 56789-0",
            "Saldo Anterior: R$ 3.200,00",
            "PIX Recebido - Cliente A: +R$ 1.500,00",
            "PIX Enviado - Fornecedor B: -R$ 450,00",
            "TED Transferência: -R$ 1.200,00",
            "Saldo Disponível Atual: R$ 3.050,00"
        ]
    )
    
    create_pdf(
        os.path.join(output_dir, "Declaracao_IRPF_Ajuste_Anual.pdf"),
        "RECEITA FEDERAL DO BRASIL - IRPF",
        [
            "Declaração de Ajuste Anual do Imposto sobre a Renda da Pessoa Física",
            "Recibo de Entrega da Declaração IRPF",
            "Exercício: 2024 - Ano-Calendário: 2023",
            "Rendimentos Tributáveis: R$ 92.400,00",
            "Imposto Pago: R$ 12.300,00",
            "Imposto a Restituir: R$ 1.450,20"
        ]
    )
    
    create_pdf(
        os.path.join(output_dir, "Contrato_Prestacao_Servicos_Software.pdf"),
        "INSTRUMENTO PARTICULAR DE CONTRATO DE PRESTAÇÃO DE SERVIÇOS",
        [
            "Contrato de Prestação de Serviços de Desenvolvimento de Software",
            "Contratante: Tech Solutions LTDA",
            "Contratada: Dev Soluções Digitais EIRELI",
            "Cláusula Primeira: Do Objeto da Prestação de Serviços.",
            "Cláusula Segunda: Dos Prazos e Entregas dos Módulos.",
            "Cláusula Terceira: Do Pagamento e Honorários.",
            "Foro da Comarca de São Paulo/SP para dirimir controvérsias.",
            "Testemunhas e Assinatura das Partes."
        ]
    )

    create_pdf(
        os.path.join(output_dir, "Curriculum_Vitae_Lucas_Silva.pdf"),
        "CURRICULUM VITAE - LUCAS SILVA",
        [
            "Currículo Profissional - Engenheiro de Software Sênior",
            "Contato: lucas.silva@email.com | LinkedIn: /in/lucassilva",
            "## Resumo Profissional",
            "Especialista em Rust, Python e arquiteturas de alta performance.",
            "## Experiência Profissional",
            "- Tech Lead na Empresa Alpha (2021 - Atual): Liderança técnica de microsserviços.",
            "- Engenheiro de Software na Empresa Beta (2018 - 2021): Desenvolvimento backend.",
            "## Formação Acadêmica",
            "Bacharelado em Ciência da Computação - USP (2014 - 2018)",
            "## Habilidades e Idiomas",
            "Rust, Python, C++, Docker, Kubernetes, SQLite | Inglês Fluente"
        ]
    )
    
    create_pdf(
        os.path.join(output_dir, "Certificado_Conclusao_Rust_Avancado.pdf"),
        "CERTIFICADO DE CONCLUSÃO",
        [
            "Certificamos que Lucas Silva concluiu com êxito o curso de",
            "Programação em Rust e Concorrência de Alta Performance.",
            "Conferimos o presente certificado com Carga Horária de 60 horas.",
            "Grau de Aperfeiçoamento Profissional emitido pela Instituição de Ensino TechAcademy.",
            "Diretor Geral e Coordenador Acadêmico."
        ]
    )

    # 3. TXT Files
    create_txt(
        os.path.join(output_dir, "Comprovante_Pix_Transferencia_Aluguel.txt"),
        "Comprovante de Transferência PIX\n"
        "Instituição: Banco Inter S.A.\n"
        "Autenticação Mecânica / Eletrônica: 9A8B-7C6D-5E4F-3G2H\n"
        "Transação efetuada com sucesso.\n"
        "Valor Pago: R$ 1.800,00\n"
        "Data do Pagamento: 05/08/2024\n"
        "Identificador da Transação: E00416999202408051400abc987\n"
    )

    create_txt(
        os.path.join(output_dir, "Declaracao_de_Residencia_Comprovante.txt"),
        "Declaração de Residência / Comprovante de Endereço\n"
        "Eu, Fulano de Tal, declaro para os devidos fins que resido no endereço abaixo:\n"
        "Logradouro: Avenida Paulista, 1000, Apto 52\n"
        "Bairro: Bela Vista\n"
        "Município: São Paulo - UF: SP\n"
        "CEP: 01310-100\n"
    )

    create_txt(
        os.path.join(output_dir, "Cadastro_Pessoa_Fisica_CPF_Dados.txt"),
        "Ministério da Fazenda - Receita Federal do Brasil\n"
        "Cadastro de Pessoas Físicas - Comprovante de Inscrição\n"
        "Número do CPF: 123.456.789-00\n"
        "Nome: Maria de Oliveira Santos\n"
        "Data de Nascimento: 14/07/1990\n"
        "Nome da Mãe: Ana de Oliveira\n"
    )

    create_txt(
        os.path.join(output_dir, "Contrato_Locacao_Residencial_Minuta.txt"),
        "Instrumento Particular de Contrato de Locação Residencial\n"
        "Contratante: Locador João Mendes\n"
        "Contratada: Locatária Beatriz Costa\n"
        "Cláusula Primeira: O presente contrato tem por objeto o imóvel sito à Rua das Flores, 120.\n"
        "Foro da Comarca para dirimir quaisquer dúvidas.\n"
        "Testemunhas e Assinatura das Partes.\n"
    )

    create_txt(
        os.path.join(output_dir, "Notas_de_Reuniao_Planejamento_Sprint.txt"),
        "Ata de Reunião - Sprint Planning 42\n"
        "Participantes: Time de Engenharia e Design\n"
        "Assuntos Discutidos:\n"
        "1. Performance do scanner de arquivos em Rust\n"
        "2. Melhorias na busca global Ctrl+K\n"
        "3. Lançamento da versão 1.0 portátil\n"
    )

    create_txt(
        os.path.join(output_dir, "Lista_de_Ideias_e_Projetos.txt"),
        "Ideias para futuros projetos e aplicações:\n"
        "- Indexo v2.0 com plugins e automações\n"
        "- App de anotações sincronizado em Markdown\n"
        "- Monitor de desempenho de hardware leve\n"
    )

    create_txt(
        os.path.join(output_dir, "Receita_Bolo_de_Cenoura_Vovo.txt"),
        "Receita de Bolo de Cenoura Fofinho:\n"
        "Ingredientes:\n"
        "- 3 cenouras médias raladas\n"
        "- 4 ovos\n"
        "- 1/2 xícara de óleo\n"
        "- 2 xícaras de açúcar\n"
        "- 2 e 1/2 xícaras de farinha de trigo\n"
        "- 1 colher de sopa de fermento\n"
        "Cobertura de chocolate brigadeiro tradicional.\n"
    )

    # 4. Imagens JPG com EXIF e sem EXIF
    # Foto com data de Maio 2024 e Câmera Canon
    create_jpg_with_exif(
        os.path.join(output_dir, "IMG_20240510_142010_Parque.jpg"),
        width=800, height=600,
        color=(70, 130, 90),
        text="Parque Ibirapuera - Foto de Maio 2024 (Canon EOS)",
        date_str="2024:05:10 14:20:10",
        make="Canon",
        model="EOS Rebel T7"
    )

    # Foto com data de Janeiro 2023 e Câmera Sony
    create_jpg_with_exif(
        os.path.join(output_dir, "DSC_0042_Praia_Ferias_Janeiro.jpg"),
        width=800, height=600,
        color=(40, 120, 180),
        text="Praia de Ubatuba - Janeiro 2023 (Sony Alpha)",
        date_str="2023:01:15 10:15:30",
        make="Sony",
        model="Alpha A6000"
    )

    # Foto Panorâmica com data de Dezembro 2023
    create_jpg_with_exif(
        os.path.join(output_dir, "PANO_20231231_235900_Reveillon.jpg"),
        width=1200, height=400,
        color=(30, 30, 70),
        text="Panorâmica Reveillon 2024 (Samsung Galaxy)",
        date_str="2023:12:31 23:59:00",
        make="Samsung",
        model="Galaxy S23"
    )

    # Foto de CNH / RG simulada
    create_jpg_with_exif(
        os.path.join(output_dir, "Documento_CNH_Carteira_Habilitacao.jpg"),
        width=800, height=500,
        color=(220, 230, 210),
        text="Carteira Nacional de Habilitação - Senatran / Detran\nCategoria B - Órgão Emissor",
        date_str="2022:08:20 11:00:00",
        make="Apple",
        model="iPhone 13"
    )

    # Imagem simples sem EXIF
    img_simple = Image.new("RGB", (600, 400), color=(150, 100, 180))
    draw_simple = ImageDraw.Draw(img_simple)
    draw_simple.text((50, 50), "Banner Grafico sem Metadados EXIF", fill=(255, 255, 255))
    img_simple.save(os.path.join(output_dir, "Banner_Grafico_Design.jpg"), "JPEG", quality=85)

    # 5. Subpasta desorganizada (para testar busca recursiva e subdiretórios)
    subfolder = os.path.join(output_dir, "Downloads_Baguncados")
    os.makedirs(subfolder, exist_ok=True)
    
    create_pdf(
        os.path.join(subfolder, "Fatura_Claro_Telefonia_Abril.pdf"),
        "CLARO S.A. - COMBO MULTI CONTROLE",
        [
            "Fatura Mensal Claro Móvel e Pós",
            "Claro S.A. - CNPJ: 40.432.544/0001-47",
            "Franquia de Internet 30GB + Minutos de Voz",
            "Total a Pagar: R$ 69,90"
        ]
    )

    create_txt(
        os.path.join(subfolder, "Rascunho_Ideias_Desorganizadas.txt"),
        "Lista de coisas baixadas da internet:\n- Artigos sobre inteligência artificial\n- Tutoriais de PyQt6 e Rust"
    )

    create_jpg_with_exif(
        os.path.join(subfolder, "IMG_20240401_091000_Cafe.jpg"),
        width=600, height=600,
        color=(110, 80, 50),
        text="Café da Manhã - 01/04/2024",
        date_str="2024:04:01 09:10:00",
        make="Google",
        model="Pixel 7"
    )

    # 6. Duplicatas Exatas (para testar o detector de duplicatas SHA-256)
    dups_folder = os.path.join(output_dir, "Arquivos_Duplicados_Teste")
    os.makedirs(dups_folder, exist_ok=True)
    
    # Copia exata do boleto
    shutil.copy2(
        os.path.join(output_dir, "Boleto_Bancario_Banco_do_Brasil.pdf"),
        os.path.join(dups_folder, "Boleto_Bancario_Banco_do_Brasil_COPIA_DUPLICADA.pdf")
    )
    # Copia exata da foto
    shutil.copy2(
        os.path.join(output_dir, "IMG_20240510_142010_Parque.jpg"),
        os.path.join(dups_folder, "IMG_20240510_142010_Parque_COPIA_DUPLICADA.jpg")
    )
    # Copia exata do txt
    shutil.copy2(
        os.path.join(output_dir, "Comprovante_Pix_Transferencia_Aluguel.txt"),
        os.path.join(dups_folder, "Comprovante_Pix_Transferencia_Aluguel_COPIA_DUPLICADA.txt")
    )

    print("\nTodos os arquivos de teste foram gerados com sucesso!")
    print(f"Total de arquivos na pasta de testes: {sum(len(files) for _, _, files in os.walk(output_dir))}")

def main():
    parser = argparse.ArgumentParser(description="Gera uma base de testes rica e diversificada para o Indexo.")
    parser.add_argument(
        "--output", "-o",
        default=DEFAULT_OUTPUT_DIR,
        help=f"Diretório de destino (padrão: {DEFAULT_OUTPUT_DIR})"
    )
    args = parser.parse_args()
    generate_dataset(output_dir=args.output)

if __name__ == "__main__":
    main()
