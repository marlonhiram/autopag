# -*- coding: utf-8 -*-
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core.utils import formatar_moeda, formatar_data, truncar_texto, criar_diretorios


class TestFormatarMoeda:
    def test_valor_normal(self):
        assert formatar_moeda(1230.50) == "R$ 1.230,50"

    def test_valor_simples(self):
        assert formatar_moeda(450.00) == "R$ 450,00"

    def test_valor_grande(self):
        assert formatar_moeda(5800.00) == "R$ 5.800,00"

    def test_valor_none(self):
        assert formatar_moeda(None) == "N/D"

    def test_valor_zero(self):
        assert formatar_moeda(0.0) == "R$ 0,00"

    def test_valor_centavos(self):
        assert formatar_moeda(0.99) == "R$ 0,99"


class TestFormatarData:
    def test_data_iso(self):
        assert formatar_data("2026-06-15") == "15/06/2026"

    def test_data_none(self):
        assert formatar_data(None) == "N/D"

    def test_data_vazia(self):
        assert formatar_data("") == "N/D"

    def test_data_invalida_retorna_original(self):
        assert formatar_data("nao-e-data") == "nao-e-data"

    def test_data_com_timestamp(self):
        # Deve usar só os 10 primeiros caracteres
        assert formatar_data("2026-06-15 10:30:00") == "15/06/2026"


class TestTruncarTexto:
    def test_texto_curto_nao_trunca(self):
        assert truncar_texto("Texto curto") == "Texto curto"

    def test_texto_longo_trunca(self):
        resultado = truncar_texto("Fornecedor com nome muito longo LTDA", 20)
        assert resultado.endswith("…")
        assert len(resultado) == 20

    def test_none_retorna_traco(self):
        assert truncar_texto(None) == "—"

    def test_string_vazia_retorna_traco(self):
        assert truncar_texto("") == "—"

    def test_limite_exato_nao_trunca(self):
        texto = "a" * 32
        assert truncar_texto(texto) == texto

    def test_limite_mais_um_trunca(self):
        texto = "a" * 33
        assert truncar_texto(texto).endswith("…")


class TestCriarDiretorios:
    def test_cria_estrutura_completa(self, tmp_path):
        criar_diretorios(tmp_path)
        assert (tmp_path / "dados" / "A_Pagar").exists()
        assert (tmp_path / "dados" / "Processados").exists()
        assert (tmp_path / "dados" / "Comprovantes").exists()
        assert (tmp_path / "logs").exists()
        assert (tmp_path / "config" / "certificados").exists()

    def test_idempotente(self, tmp_path):
        criar_diretorios(tmp_path)
        criar_diretorios(tmp_path)  # segunda chamada não deve lançar erro
