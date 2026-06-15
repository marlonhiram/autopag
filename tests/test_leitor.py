# -*- coding: utf-8 -*-
"""
Testa a lógica de extração de dados do leitor sem precisar de PDFs físicos
nem das bibliotecas opcionais (pdfplumber, pyzbar, Tesseract).
"""
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.leitor import (
    _extrair_campos, ResultadoLeitura,
    listar_pdfs_pendentes,
)


class TestExtrairCampos:
    def _res(self, nome="boleto_001.pdf"):
        return ResultadoLeitura(Path(nome))

    def test_extrai_linha_digitavel(self):
        texto = "Linha digitável: 34191.09008 61207.727285 61780.830003 1 93480000045000"
        res = self._res()
        encontrou = _extrair_campos(texto, res, nivel=1)
        assert encontrou is True
        assert res.codigo is not None
        assert res.tipo == "BOLETO"

    def test_extrai_valor_com_ponto_milhar(self):
        texto = "Linha: 34191.09008 61207.727285 61780.830003 1 93480000045000 Valor: R$ 1.230,50"
        res = self._res()
        _extrair_campos(texto, res, nivel=1)
        assert res.valor == 1230.50

    def test_extrai_valor_simples(self):
        texto = "34191.09008 61207.727285 61780.830003 1 93480000045000 Total: 450,00"
        res = self._res()
        _extrair_campos(texto, res, nivel=1)
        assert res.valor == 450.00

    def test_extrai_vencimento_formato_barra(self):
        texto = "34191.09008 61207.727285 61780.830003 1 93480000045000 Vencimento: 15/06/2026"
        res = self._res()
        _extrair_campos(texto, res, nivel=1)
        assert res.vencimento == "2026-06-15"

    def test_extrai_vencimento_formato_iso(self):
        texto = "34191.09008 61207.727285 61780.830003 1 93480000045000 Vencimento: 2026-06-15"
        res = self._res()
        _extrair_campos(texto, res, nivel=1)
        assert res.vencimento == "2026-06-15"

    def test_extrai_fornecedor(self):
        texto = "34191.09008 61207.727285 61780.830003 1 93480000045000 Cedente: Fornecedor LTDA"
        res = self._res()
        _extrair_campos(texto, res, nivel=1)
        assert res.fornecedor is not None
        assert "Fornecedor" in res.fornecedor

    def test_sem_codigo_retorna_false(self):
        texto = "Texto sem nenhum código de pagamento válido aqui."
        res = self._res()
        encontrou = _extrair_campos(texto, res, nivel=1)
        assert encontrou is False
        assert res.codigo is None

    def test_nivel_registrado_corretamente(self):
        texto = "34191.09008 61207.727285 61780.830003 1 93480000045000"
        res = self._res()
        _extrair_campos(texto, res, nivel=3)
        assert res.nivel_leitura == 3


class TestResultadoLeitura:
    def test_to_dict_com_sucesso(self):
        res = ResultadoLeitura(Path("boleto_001.pdf"))
        res.sucesso = True
        res.tipo = "PIX"
        res.valor = 450.0
        resultado = res.to_dict()
        assert resultado["id_display"] == "boleto_001"
        assert resultado["status"] == "PENDENTE"
        assert resultado["tipo"] == "PIX"

    def test_to_dict_sem_sucesso_vira_revisao(self):
        res = ResultadoLeitura(Path("boleto_002.pdf"))
        res.sucesso = False
        resultado = res.to_dict()
        assert resultado["status"] == "REVISAO"
        assert resultado["id_display"] == "boleto_002"

    def test_to_dict_tipo_padrao_boleto(self):
        res = ResultadoLeitura(Path("boleto_003.pdf"))
        res.sucesso = True
        assert res.to_dict()["tipo"] == "BOLETO"

    def test_to_dict_codigo_vazio_quando_none(self):
        res = ResultadoLeitura(Path("boleto_004.pdf"))
        assert res.to_dict()["codigo_pagamento"] == ""


class TestLerPdfCompleto:
    """
    Testa o fluxo completo de ler_pdf() sem precisar de um PDF físico.
    Usa unittest.mock para substituir pdfplumber por um dublê que retorna
    texto controlado — o código de extração não sabe a diferença.
    """

    def _criar_pdf_fake(self, tmp_path, nome="boleto_001.pdf"):
        """Cria um arquivo vazio só para o Path existir no disco."""
        p = tmp_path / nome
        p.write_bytes(b"%PDF-1.4 fake")
        return p

    def _mock_pdfplumber(self, texto):
        """Monta o dublê do pdfplumber retornando o texto fornecido."""
        from unittest.mock import MagicMock, patch
        pagina = MagicMock()
        pagina.extract_text.return_value = texto
        ctx = MagicMock()
        ctx.__enter__ = MagicMock(return_value=MagicMock(pages=[pagina]))
        ctx.__exit__ = MagicMock(return_value=False)
        return patch("core.leitor.pdfplumber.open", return_value=ctx)

    def test_boleto_extraido_com_sucesso(self, tmp_path):
        from core.leitor import ler_pdf
        texto = (
            "Cedente: Fornecedor LTDA "
            "Valor: R$ 450,00 "
            "Vencimento: 15/06/2026 "
            "34191.09008 61207.727285 61780.830003 1 93480000045000"
        )
        pdf = self._criar_pdf_fake(tmp_path)
        with self._mock_pdfplumber(texto):
            resultado = ler_pdf(pdf)

        assert resultado.sucesso is True
        assert resultado.tipo == "BOLETO"
        assert resultado.valor == 450.0
        assert resultado.vencimento == "2026-06-15"
        assert resultado.fornecedor is not None
        assert resultado.nivel_leitura == 1

    def test_pdf_sem_dados_vira_revisao(self, tmp_path):
        from core.leitor import ler_pdf
        pdf = self._criar_pdf_fake(tmp_path, "sem_dados.pdf")
        # pdfplumber retorna texto sem nenhum código de pagamento
        with self._mock_pdfplumber("Texto qualquer sem código de boleto ou pix"):
            resultado = ler_pdf(pdf)

        assert resultado.sucesso is False
        assert resultado.to_dict()["status"] == "REVISAO"

    def test_pdf_sem_texto_vai_para_nivel2(self, tmp_path):
        from unittest.mock import patch, MagicMock
        from core.leitor import ler_pdf
        pdf = self._criar_pdf_fake(tmp_path)

        # Nível 1: pdfplumber retorna texto vazio → passa para nível 2
        ctx_vazio = MagicMock()
        ctx_vazio.__enter__ = MagicMock(
            return_value=MagicMock(pages=[MagicMock(extract_text=lambda: "")])
        )
        ctx_vazio.__exit__ = MagicMock(return_value=False)

        with patch("core.leitor.pdfplumber.open", return_value=ctx_vazio):
            with patch("core.leitor._PYZBAR_OK", False):
                with patch("core.leitor._TESSERACT_OK", False):
                    resultado = ler_pdf(pdf)

        # Sem nível 2 nem 3 disponíveis → REVISAO
        assert resultado.sucesso is False


class TestListarPdfsPendentes:
    def test_pasta_inexistente_retorna_vazio(self, tmp_path):
        assert listar_pdfs_pendentes(tmp_path / "nao_existe") == []

    def test_pasta_vazia_retorna_vazio(self, tmp_path):
        assert listar_pdfs_pendentes(tmp_path) == []

    def test_retorna_apenas_pdfs(self, tmp_path):
        (tmp_path / "boleto.pdf").touch()
        (tmp_path / "boleto.txt").touch()
        (tmp_path / "imagem.png").touch()
        resultado = listar_pdfs_pendentes(tmp_path)
        assert len(resultado) == 1
        assert resultado[0].name == "boleto.pdf"

    def test_retorna_ordenado(self, tmp_path):
        (tmp_path / "boleto_003.pdf").touch()
        (tmp_path / "boleto_001.pdf").touch()
        (tmp_path / "boleto_002.pdf").touch()
        nomes = [p.name for p in listar_pdfs_pendentes(tmp_path)]
        assert nomes == ["boleto_001.pdf", "boleto_002.pdf", "boleto_003.pdf"]

    def test_retorna_paths_absolutos(self, tmp_path):
        (tmp_path / "boleto.pdf").touch()
        resultado = listar_pdfs_pendentes(tmp_path)
        assert resultado[0].is_absolute()
