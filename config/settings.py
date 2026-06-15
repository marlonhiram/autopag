# -*- coding: utf-8 -*-
"""
Configurações centralizadas do AutoPag.
Paleta de cores, caminhos e constantes de interface.
"""
from pathlib import Path

# ─── Caminhos ─────────────────────────────────────────────────────────────────
BASE_DIR         = Path(__file__).resolve().parent.parent
DIR_DADOS        = BASE_DIR / "dados"
DIR_A_PAGAR      = DIR_DADOS / "A_Pagar"
DIR_PROCESSADOS  = DIR_DADOS / "Processados"
DIR_COMPROVANTES = DIR_DADOS / "Comprovantes"
DIR_LOGS         = BASE_DIR / "logs"
DIR_ASSETS       = BASE_DIR / "assets"
DIR_CERTIFICADOS = BASE_DIR / "config" / "certificados"
DB_PATH          = DIR_DADOS / "autopag.db"

# ─── Interface ────────────────────────────────────────────────────────────────
APP_TITULO  = "AutoPag  —  Automação de Contas a Pagar"
APP_VERSAO  = "v1.0.0-MVP"
APP_LARGURA = 1200
APP_ALTURA  = 760
APP_TEMA    = "dark"
APP_COR     = "blue"

# ─── Paleta de Cores ──────────────────────────────────────────────────────────
COR_FUNDO              = "#0D0D1B"
COR_SUPERFICIE         = "#13132A"
COR_SUPERFICIE_ELEVADA = "#1A1A38"
COR_LINHA_PAR          = "#111126"
COR_LINHA_IMPAR        = "#14142E"
COR_LINHA_HOVER        = "#1E1E42"
COR_LINHA_SELECIONADA  = "#252560"
COR_BORDA              = "#25254A"
COR_ACCENT             = "#4F7EF5"
COR_ACCENT_HOVER       = "#6B94F8"
COR_TEXTO              = "#DCDCFF"
COR_TEXTO_SECUNDARIO   = "#7878A8"
COR_TEXTO_MUTED        = "#44446A"

# ─── Status: cores (bg + fg) ──────────────────────────────────────────────────
# [DEC-005] Tabela customizada com CTkFrames + badges coloridas por status.
# Optou-se por implementar linhas como CTkFrames em vez do ttk.Treeview nativo
# para alcançar o padrão visual moderno exigido. Trade-off: mais código de UI;
# ganho: hover, seleção, badges, total controle visual sem depender de ttk.Style.
STATUS_CORES = {
    "PENDENTE": {"bg": "#78350F", "fg": "#FDE68A"},
    "ENVIADO":  {"bg": "#1E3A8A", "fg": "#BFDBFE"},
    "PAGO":     {"bg": "#064E3B", "fg": "#6EE7B7"},
    "ERRO":     {"bg": "#7F1D1D", "fg": "#FECACA"},
    "REVISAO":  {"bg": "#4C1D95", "fg": "#DDD6FE"},
}
STATUS_ICONES = {
    "PENDENTE": "⏳",
    "ENVIADO":  "📤",
    "PAGO":     "✅",
    "ERRO":     "❌",
    "REVISAO":  "⚠️",
}

# ─── Colunas da tabela (chave, título, largura px, âncora) ────────────────────
COLUNAS_TABELA = [
    {"chave": "id_display", "titulo": "Identificador", "largura": 130, "ancora": "w"},
    {"chave": "fornecedor", "titulo": "Fornecedor",    "largura": 260, "ancora": "w"},
    {"chave": "valor",      "titulo": "Valor (R$)",    "largura": 120, "ancora": "e"},
    {"chave": "vencimento", "titulo": "Vencimento",    "largura": 115, "ancora": "center"},
    {"chave": "tipo",       "titulo": "Tipo",          "largura": 85,  "ancora": "center"},
    {"chave": "status",     "titulo": "Status",        "largura": 140, "ancora": "center"},
]

# ─── Modo Simulação (Entrega 3) ───────────────────────────────────────────────
# True  → BancoMock: nenhuma credencial necessária, fluxo completo funciona
# False → API real (Bradesco ou BB). Exige credenciais na tabela config_banco.
MODO_SIMULACAO = True
BANCO_ATIVO    = "BRADESCO"   # "BRADESCO" ou "BB"

# ─── Aliases de compatibilidade com os módulos 3 e 4 ────────────────────────
MODO_MOCK           = MODO_SIMULACAO          # usado em banco_api.py
KEYRING_SERVICO     = "AutoPag"               # namespace no Windows Credential Manager
PASTA_COMPROVANTES  = DIR_COMPROVANTES        # alias legível em comprovantes.py

# ─── Credenciais Bradesco (preencher na homologação) ─────────────────────────
# Chave PIX da conta pagadora da empresa (CNPJ, e-mail, telefone ou aleatória).
# Obrigatório para o campo "chave" no payload PUT /v2/cob da API Bradesco.
BRADESCO_CHAVE_PIX  = ""   # TODO: preencher com a chave PIX cadastrada no Bradesco

# ─── URLs das APIs bancárias ──────────────────────────────────────────────────
# Estes valores vão para a tabela config_banco (campo url_base_api).
# Listados aqui como referência para facilitar o cadastro no banco de dados.
BRADESCO_URL_SANDBOX = "https://qrpix-h.bradesco.com.br"
BRADESCO_URL_PROD    = "https://qrpix.bradesco.com.br"
BB_URL_SANDBOX_API   = "https://api.sandbox.bb.com.br"
BB_URL_PROD_API      = "https://api.bb.com.br"
