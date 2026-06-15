# -*- coding: utf-8 -*-
"""
Testa o Nível 2 da hierarquia de leitura: pyzbar + pdf2image + Pillow.

Estratégia: gera um PDF em memória que é apenas uma imagem (sem texto nativo),
contendo um QR Code Pix real. Isso força o leitor.py a:
  - Falhar no Nível 1 (pdfplumber não acha texto)
  - Ter sucesso no Nível 2 (pyzbar lê o QR Code da imagem)

Nenhum arquivo externo necessário — tudo gerado em tempo de execução.
"""
import sys
import io
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# ─── Verifica dependências disponíveis ────────────────────────────────────────

try:
    import qrcode
    _QRCODE_OK = True
except ImportError:
    _QRCODE_OK = False

try:
    import cv2 as _cv2
    import numpy as _np
    _OPENCV_OK = True
except ImportError:
    _OPENCV_OK = False

try:
    from pyzbar import pyzbar as _pyzbar
    _PYZBAR_OK = True
except Exception:
    _PYZBAR_OK = False

try:
    import pdf2image as _pdf2image
    from PIL import Image
    _PDF2IMAGE_OK = True
except Exception:
    _PDF2IMAGE_OK = False

_NIVEL2_OK = _PDF2IMAGE_OK and (_PYZBAR_OK or _OPENCV_OK)


def _gerar_pdf_com_qrcode(payload_pix: str, tmp_path: Path) -> Path:
    """
    Gera um PDF de uma página contendo apenas uma imagem com QR Code.
    pdfplumber não encontrará texto nativo → força o Nível 2.
    """
    # 1. Gera o QR Code como imagem
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=4,
    )
    qr.add_data(payload_pix)
    qr.make(fit=True)
    img_qr = qr.make_image(fill_color="black", back_color="white").convert("RGB")

    # 2. Cria uma "página de boleto" com o QR Code centralizado
    pagina = Image.new("RGB", (800, 1100), color=(255, 255, 255))
    qr_w, qr_h = img_qr.size
    x = (800 - qr_w) // 2
    y = (1100 - qr_h) // 2
    pagina.paste(img_qr, (x, y))

    # 3. Salva como PDF (Pillow salva imagem diretamente como PDF)
    caminho_pdf = tmp_path / "boleto_qrcode_teste.pdf"
    pagina.save(str(caminho_pdf), "PDF", resolution=150)
    return caminho_pdf


# ─── Payload Pix EMV de teste (estrutura real, valores fictícios) ──────────────
PAYLOAD_PIX_TESTE = (
    "00020126580014br.gov.bcb.pix0136123e4567-e89b-12d3-a456-426614174000"
    "5204000053039865802BR5913Fornecedor SA6009Sao Paulo"
    "62070503***6304ABCD"
)


@pytest.mark.skipif(not _QRCODE_OK, reason="qrcode não instalado: pip install qrcode")
@pytest.mark.skipif(not _NIVEL2_OK, reason="pyzbar/pdf2image não instalados ou Poppler ausente")
class TestLeituraNivel2:

    def test_pdf_imagem_ativa_nivel2(self, tmp_path):
        """PDF sem texto → pdfplumber falha → pyzbar encontra o QR Code."""
        from core.leitor import ler_pdf

        pdf = _gerar_pdf_com_qrcode(PAYLOAD_PIX_TESTE, tmp_path)
        resultado = ler_pdf(pdf)

        assert resultado.sucesso is True, f"Leitura falhou: {resultado.erro}"
        assert resultado.nivel_leitura == 2, (
            f"Esperava Nível 2 (pyzbar), mas usou Nível {resultado.nivel_leitura}"
        )
        assert resultado.tipo == "PIX"
        assert resultado.codigo is not None
        assert resultado.codigo.startswith("000201"), (
            f"Payload Pix inválido: {resultado.codigo[:20]}"
        )

    def test_payload_pix_preservado_integro(self, tmp_path):
        """Verifica que o payload extraído é idêntico ao que foi gravado no QR."""
        from core.leitor import ler_pdf

        pdf = _gerar_pdf_com_qrcode(PAYLOAD_PIX_TESTE, tmp_path)
        resultado = ler_pdf(pdf)

        assert resultado.codigo == PAYLOAD_PIX_TESTE

    def test_to_dict_nivel2_pronto_para_banco(self, tmp_path):
        """Resultado do Nível 2 gera dict válido para inserção no SQLite."""
        from core.leitor import ler_pdf

        pdf = _gerar_pdf_com_qrcode(PAYLOAD_PIX_TESTE, tmp_path)
        resultado = ler_pdf(pdf)
        d = resultado.to_dict()

        assert d["tipo"] == "PIX"
        assert d["status"] == "PENDENTE"
        assert d["codigo_pagamento"].startswith("000201")
        assert d["id_display"] == "boleto_qrcode_teste"

    def test_leitor_qrcode_direto_na_imagem(self, tmp_path):
        """Teste unitário isolado: lê QR Code diretamente da imagem (sem PDF)."""
        import qrcode as qc
        from core.leitor import _ler_qrcode_imagem

        payload = "000201TESTE_DIRETO"
        qr = qc.QRCode(box_size=10, border=4)
        qr.add_data(payload)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white").convert("RGB")

        resultado = _ler_qrcode_imagem(img)
        assert resultado == payload, f"QR Code lido: {resultado!r}"


@pytest.mark.skipif(not _NIVEL2_OK, reason="pdf2image/Poppler não disponíveis")
class TestPdf2Image:

    def test_converte_pdf_para_imagem(self, tmp_path):
        """Verifica que pdf2image consegue converter o PDF gerado."""
        if not _QRCODE_OK:
            pytest.skip("qrcode não instalado")

        pdf = _gerar_pdf_com_qrcode(PAYLOAD_PIX_TESTE, tmp_path)
        imgs = _pdf2image.convert_from_path(str(pdf), dpi=150)

        assert len(imgs) == 1
        assert imgs[0].width > 0
        assert imgs[0].height > 0
