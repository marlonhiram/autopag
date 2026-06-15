# -*- coding: utf-8 -*-
"""
Módulo 1 — Leitura de PDFs e extração de dados.

Hierarquia de fallback (DEC-004):
  Nível 1: pdfplumber  — texto nativo selecionável (rápido, preciso)
  Nível 2: pyzbar      — QR Code Pix em imagem (pdf2image)
  Nível 3: Tesseract   — OCR completo para PDFs escaneados
  Falha total → status REVISAO + sinalização na interface (RF-04)

Cada nível importa com fallback gracioso: se a biblioteca não estiver
instalada, o nível é pulado sem travar a aplicação.
"""
import re
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional

logger = logging.getLogger("autopag")

# ─── Importações opcionais — falha graciosamente ──────────────────────────────

try:
    import pdfplumber
    _PDFPLUMBER_OK = True
except ImportError:
    _PDFPLUMBER_OK = False
    logger.warning("pdfplumber não disponível — Nível 1 desabilitado.")

try:
    from pyzbar import pyzbar as _pyzbar
    _PYZBAR_OK = True
except Exception:
    _PYZBAR_OK = False
    logger.warning("pyzbar não disponível ou DLL ausente — tentando OpenCV para QR Code.")

try:
    import cv2 as _cv2
    import numpy as _np
    _OPENCV_OK = True
except ImportError:
    _OPENCV_OK = False

try:
    from PIL import Image as _Image
    import pdf2image as _pdf2image
    _PDF2IMAGE_OK = True
except Exception:
    _PDF2IMAGE_OK = False
    logger.warning("pdf2image/Pillow não disponível — Nível 2 desabilitado.")

_NIVEL2_OK = _PDF2IMAGE_OK and (_PYZBAR_OK or _OPENCV_OK)

try:
    import pytesseract as _tesseract
    _TESSERACT_OK = True
except ImportError:
    _TESSERACT_OK = False
    logger.warning("pytesseract não disponível — Nível 3 (OCR) desabilitado.")


# ─── Regex para extração de campos ───────────────────────────────────────────

# Linha digitável: 47 ou 48 dígitos (com ou sem pontos/espaços)
_RE_LINHA_DIG  = re.compile(r"(\d[\d. ]{44,52}\d)")
_RE_VALOR      = re.compile(r"(?:valor|total|R\$)\s*:?\s*([\d.,]+)", re.IGNORECASE)
_RE_VENCIMENTO = re.compile(
    r"(?:vencimento|venc\.?)\s*:?\s*(\d{2}/\d{2}/\d{4}|\d{4}-\d{2}-\d{2})",
    re.IGNORECASE,
)
_RE_FORNECEDOR = re.compile(
    r"(?:cedente|benefici[aá]rio|pagamento\s+a|raz[aã]o\s+social)\s*:?\s*(.{5,80})",
    re.IGNORECASE,
)


# ─── DTO de resultado ─────────────────────────────────────────────────────────

class ResultadoLeitura:
    """Encapsula o resultado da tentativa de leitura de um PDF."""

    def __init__(self, caminho: Path) -> None:
        self.caminho:        Path            = caminho
        self.tipo:           Optional[str]   = None   # 'PIX' ou 'BOLETO'
        self.fornecedor:     Optional[str]   = None
        self.valor:          Optional[float] = None
        self.vencimento:     Optional[str]   = None   # 'YYYY-MM-DD'
        self.codigo:         Optional[str]   = None   # Pix ou linha digitável
        self.nivel_leitura:  int             = 0      # 1, 2 ou 3
        self.sucesso:        bool            = False
        self.erro:           Optional[str]   = None

    def to_dict(self) -> dict:
        """Converte para dict pronto para inserção no banco."""
        return {
            "id_display":       self.caminho.stem,
            "arquivo_origem":   self.caminho.name,
            "arquivo_atual":    self.caminho.name,
            "tipo":             self.tipo or "BOLETO",
            "fornecedor":       self.fornecedor,
            "valor":            self.valor,
            "vencimento":       self.vencimento,
            "codigo_pagamento": self.codigo or "",
            "status":           "PENDENTE" if self.sucesso else "REVISAO",
        }


# ─── Nível 1: pdfplumber ──────────────────────────────────────────────────────

def _nivel1_pdfplumber(caminho: Path, res: ResultadoLeitura) -> bool:
    """
    Tenta extrair texto nativo do PDF.

    Returns:
        True se código de pagamento foi localizado.
    """
    if not _PDFPLUMBER_OK:
        return False
    try:
        with pdfplumber.open(str(caminho)) as pdf:
            texto = "\n".join(p.extract_text() or "" for p in pdf.pages)
        if not texto.strip():
            return False
        return _extrair_campos(texto, res, nivel=1)
    except Exception as e:
        logger.warning(f"[N1-pdfplumber] {caminho.name}: {e}")
        return False


# ─── Nível 2: pyzbar (QR Code Pix) ───────────────────────────────────────────

def _nivel2_qrcode(caminho: Path, res: ResultadoLeitura) -> bool:
    """
    Converte a primeira página em imagem e escaneia QR Codes Pix.
    Tenta pyzbar primeiro; usa OpenCV como fallback se pyzbar falhar.

    Returns:
        True se payload Pix válido encontrado.
    """
    if not _NIVEL2_OK:
        return False
    try:
        imgs = _pdf2image.convert_from_path(str(caminho), dpi=200, first_page=1, last_page=1)
        for img in imgs:
            payload = _ler_qrcode_imagem(img)
            if payload and payload.startswith("000201"):
                res.tipo          = "PIX"
                res.codigo        = payload
                res.nivel_leitura = 2
                logger.info(f"[N2] Pix encontrado em {caminho.name}")
                return True
        return False
    except Exception as e:
        logger.warning(f"[N2] {caminho.name}: {e}")
        return False


def _ler_qrcode_imagem(img) -> Optional[str]:
    """Tenta ler QR Code de uma imagem PIL. Usa pyzbar ou OpenCV."""
    # pyzbar (preferido, mais robusto)
    if _PYZBAR_OK:
        for cod in _pyzbar.decode(img):
            return cod.data.decode("utf-8")

    # OpenCV (fallback quando libzbar não está instalada no Windows)
    if _OPENCV_OK:
        import numpy as np
        img_cv = _cv2.cvtColor(np.array(img), _cv2.COLOR_RGB2BGR)
        detector = _cv2.QRCodeDetector()
        data, _, _ = detector.detectAndDecode(img_cv)
        if data:
            return data

    return None


# ─── Nível 3: Tesseract OCR ───────────────────────────────────────────────────

def _nivel3_ocr(caminho: Path, res: ResultadoLeitura) -> bool:
    """
    OCR completo via Tesseract. Usado apenas quando os dois níveis anteriores
    falharam (PDFs escaneados ou gerados como imagem).

    Returns:
        True se dados mínimos foram extraídos.
    """
    if not _TESSERACT_OK or not _PYZBAR_OK:
        return False
    try:
        imgs  = _pdf2image.convert_from_path(str(caminho), dpi=300)
        texto = "\n".join(_tesseract.image_to_string(img, lang="por") for img in imgs)
        return _extrair_campos(texto, res, nivel=3)
    except Exception as e:
        logger.warning(f"[N3-OCR] {caminho.name}: {e}")
        return False


# ─── Extração de campos por regex ────────────────────────────────────────────

def _extrair_campos(texto: str, res: ResultadoLeitura, nivel: int) -> bool:
    """
    Aplica regexes ao texto extraído para popular o ResultadoLeitura.

    Args:
        texto: Texto bruto do PDF.
        res:   Objeto a ser populado.
        nivel: Nível de leitura sendo executado.

    Returns:
        True se código de pagamento foi encontrado (campo obrigatório).
    """
    texto_limpo = texto.replace("\n", " ")

    # Linha digitável
    m = _RE_LINHA_DIG.search(texto_limpo)
    if m:
        res.codigo = re.sub(r"[^0-9]", "", m.group(1))
        res.tipo   = "BOLETO"

    # Valor
    m = _RE_VALOR.search(texto_limpo)
    if m:
        try:
            res.valor = float(m.group(1).replace(".", "").replace(",", "."))
        except ValueError:
            pass

    # Vencimento
    m = _RE_VENCIMENTO.search(texto_limpo)
    if m:
        raw = m.group(1)
        if "/" in raw:
            d, mo, a = raw.split("/")
            res.vencimento = f"{a}-{mo}-{d}"
        else:
            res.vencimento = raw

    # Fornecedor
    m = _RE_FORNECEDOR.search(texto_limpo)
    if m:
        res.fornecedor = m.group(1).strip()[:80]

    if res.codigo:
        res.nivel_leitura = nivel
        return True
    return False


# ─── API pública ──────────────────────────────────────────────────────────────

def ler_pdf(caminho: Path) -> ResultadoLeitura:
    """
    Processa um PDF pela hierarquia de fallback em três níveis (DEC-004).

    Args:
        caminho: Path para o arquivo .pdf a ser processado.

    Returns:
        ResultadoLeitura com sucesso=True se dados foram extraídos,
        ou sucesso=False com status REVISAO para intervenção manual.
    """
    res = ResultadoLeitura(caminho)
    logger.info(f"Processando: {caminho.name}")

    for nivel_fn in (_nivel1_pdfplumber, _nivel2_qrcode, _nivel3_ocr):
        if nivel_fn(caminho, res):
            res.sucesso = True
            return res

    res.erro = f"Nenhum nível de leitura extraiu dados de '{caminho.name}'. Revisão manual necessária."
    logger.warning(f"REVISAO_MANUAL — {caminho.name}")
    return res


def listar_pdfs_pendentes(pasta: Path) -> list[Path]:
    """
    Retorna lista de PDFs na pasta A_Pagar que ainda não foram processados.

    Args:
        pasta: Diretório de entrada (A_Pagar/).

    Returns:
        Lista de Paths dos arquivos .pdf encontrados.
    """
    if not pasta.exists():
        return []
    return sorted(pasta.glob("*.pdf"))
