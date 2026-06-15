# AutoPag — Automação de Contas a Pagar

Sistema desktop Windows que automatiza o fluxo de contas a pagar para empresas com ERPs legados (Delphi, VB6, Progress), sem substituir o ERP existente.

## O problema

Empresas com ERPs legados não têm integração com APIs bancárias modernas. O financeiro digita códigos Pix manualmente, fotografa QR Codes com celular e arquiva comprovantes em papel — processo lento, propenso a erros e impossível de auditar.

## A solução

AutoPag atua como camada de automação satélite: lê PDFs de boletos e Pix, extrai os dados automaticamente e envia o lote para aprovação no banco. O ERP continua intacto, o processo fica documentado e rastreável.

| Processo manual | Com AutoPag |
|---|---|
| Digita código Pix (risco de erro) | Extrai automaticamente do PDF |
| Usa celular para ler QR Code | App Windows lê o QR Code do PDF |
| Sem rastreabilidade | Log de auditoria completo |
| Comprovante perdido ou fora de ordem | Impressão intercalada automática |

## Funcionalidades

- **Leitura inteligente de PDFs** com hierarquia de fallback em 3 níveis: texto nativo (pdfplumber) → QR Code (pyzbar/OpenCV) → OCR (Tesseract)
- **Envio em lote** para APIs bancárias via OAuth2 + mTLS
- **Consulta de status** automática com polling
- **Download e merge de comprovantes** intercalando boleto + comprovante em ordem sequencial
- **Log de auditoria** completo com rotação diária e retenção de 90 dias
- **Modo simulação** para demonstração sem credenciais bancárias

## Stack

| Camada | Tecnologia |
|---|---|
| Interface | Python 3.11+ + CustomTkinter 5.x |
| Banco de dados | SQLite (WAL mode) |
| Leitura de PDFs | pdfplumber + pyzbar (ou OpenCV) + Tesseract |
| API bancária | requests + cryptography (mTLS) |
| Credenciais | keyring (Windows Credential Manager) |
| Monitoramento | watchdog |

## Arquitetura

O sistema é dividido em 4 módulos independentes:

```
PDF entrada → [Módulo 1: Leitor]   → SQLite
                                        ↓
                              [Módulo 2: GUI] ← operador confere
                                        ↓
                         [Módulo 3: API Bancária] → banco (lote agendado)
                                        ↓
                              gestor aprova no Internet Banking
                                        ↓
                         [Módulo 4: Comprovantes] → impressão intercalada
```

A integração bancária usa o padrão **Adapter**: cada banco é um módulo isolado que implementa a mesma interface (`BancoAPIBase`). Adicionar um novo banco não requer alterar nenhum código existente.

## Bancos suportados

| Banco | Status |
|---|---|
| Mock (simulação) | ✅ Funcional |
| Bradesco (PIX API v2.6.1) | 🔄 Aguardando credenciais sandbox |
| Banco do Brasil (Pagamentos v3) | 🔄 Aguardando credenciais sandbox |

---

## Instalação no Windows

### Pré-requisitos

**1. Python 3.11 ou superior**

Baixe em [python.org/downloads](https://python.org/downloads) e execute o instalador.
> **Importante:** na primeira tela do instalador, marque **"Add Python to PATH"** antes de clicar em Install Now.

Confirme a instalação abrindo o Prompt de Comando e digitando:
```
python --version
```

**2. Tesseract OCR** *(necessário para leitura de PDFs escaneados — Nível 3)*

- Baixe o instalador em: [github.com/UB-Mannheim/tesseract/releases](https://github.com/UB-Mannheim/tesseract/releases)
- Execute o instalador e marque o pacote de idioma **Portuguese** durante a instalação

**3. Poppler** *(necessário para converter PDF em imagem — Níveis 2 e 3)*

- Baixe o `.zip` em: [github.com/oschwartz10612/poppler-windows/releases](https://github.com/oschwartz10612/poppler-windows/releases)
- Extraia para `C:\poppler\`
- Adicione `C:\poppler\Library\bin` ao PATH do Windows:
  - Tecla Windows → pesquise **"Editar as variáveis de ambiente do sistema"**
  - Clique em **Variáveis de Ambiente**
  - Em "Variáveis do sistema", selecione **Path** → **Editar** → **Novo**
  - Digite: `C:\poppler\Library\bin`
  - Clique OK em todas as janelas

**4. ZBar** *(opcional — melhora a leitura de QR Code)*

O sistema lê QR Code de duas formas, automaticamente:

| Modo | Quando usa | Qualidade |
|---|---|---|
| **pyzbar** (zbar) | ZBar instalado | Melhor — mais preciso em imagens de baixa qualidade |
| **OpenCV** | Sempre disponível (já incluso) | Boa — suficiente para boletos padrão |

Se quiser instalar o ZBar para máxima precisão:
- Baixe em: [sourceforge.net/projects/zbar/files/zbar/0.10/zbar-0.10-setup.exe](https://sourceforge.net/projects/zbar/files/zbar/0.10/zbar-0.10-setup.exe)
- Execute o instalador — sem configuração extra necessária

### Instalação das dependências

Abra o Prompt de Comando, navegue até a pasta do projeto e instale as dependências:

```
cd c:\autopag
pip install -r Requirements.txt
```

Aguarde o download concluir (pode levar alguns minutos).

### Executar

```
python main.py
```

A janela do AutoPag abrirá em **modo simulação** — o fluxo completo funciona sem nenhuma credencial bancária.

---

## Testes

```
pip install pytest
pytest tests/ -v
```

Os testes rodam sem PDF físico e sem credenciais bancárias — tudo é simulado por mocks.

---

## Configuração para produção

Quando as credenciais de sandbox estiverem disponíveis:

1. Defina `MODO_SIMULACAO = False` em `config/settings.py`
2. Guarde as credenciais no cofre do Windows:
```python
from core.banco_api import guardar_segredo
guardar_segredo("BRADESCO", "seu_client_secret")
```
3. Insira a configuração do banco na tabela `config_banco` do SQLite
4. Coloque os certificados `.pem` em `config/certificados/` (pasta ignorada pelo git)

---

## Segurança

- Credenciais armazenadas no **Windows Credential Manager** via `keyring` — nunca em arquivo
- Certificados bancários em pasta excluída do controle de versão
- **Dupla conferência humana obrigatória**: o sistema nunca executa pagamentos de forma autônoma
- Log de auditoria imutável de todas as operações

---

> Desenvolvido como ferramenta interna de automação financeira, posteriormente disponibilizado como portfólio.
