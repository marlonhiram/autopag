# -*- coding: utf-8 -*-
"""
Testa o BancoMockAPI e as operações de alto nível (enviar_lote, atualizar_status_lote)
sem nenhuma credencial bancária real ou conexão de rede.
"""
import sys
import time
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.fixture(autouse=True)
def banco_temporario(tmp_path, monkeypatch):
    import config.settings as s
    monkeypatch.setattr(s, "DB_PATH", tmp_path / "test.db")
    monkeypatch.setattr(s, "MODO_MOCK", True)
    monkeypatch.setattr(s, "MODO_SIMULACAO", True)
    monkeypatch.setattr(s, "PASTA_COMPROVANTES", tmp_path)

    import core.database as db
    import importlib
    importlib.reload(db)
    db.inicializar_banco()


from core.banco_api import BancoMockAPI, obter_cliente, enviar_lote, atualizar_status_lote
import core.database as db


class TestBancoMockAPI:
    def test_autenticar_retorna_true(self):
        mock = BancoMockAPI()
        assert mock.autenticar() is True

    def test_enviar_pagamento_retorna_id_mock(self):
        mock = BancoMockAPI()
        id_ = mock.enviar_pagamento({"valor": 100.0, "codigo_pagamento": "000201"})
        assert id_.startswith("MOCK-")

    def test_enviar_pagamento_registra_timestamp(self):
        mock = BancoMockAPI()
        id_ = mock.enviar_pagamento({"valor": 100.0, "codigo_pagamento": "000201"})
        assert id_ in BancoMockAPI._enviados

    def test_consultar_status_retorna_agendado_imediatamente(self):
        mock = BancoMockAPI()
        id_ = mock.enviar_pagamento({"valor": 100.0, "codigo_pagamento": "0"})
        assert mock.consultar_status(id_) == "AGENDADO"

    def test_consultar_status_id_desconhecido_retorna_pago(self):
        mock = BancoMockAPI()
        # ID que não foi enviado nesta sessão = transação antiga = considera PAGO
        assert mock.consultar_status("ID-INEXISTENTE") == "PAGO"

    def test_baixar_comprovante_cria_pdf_valido(self, tmp_path):
        mock = BancoMockAPI()
        destino = tmp_path / "comp_teste.pdf"
        mock.baixar_comprovante("MOCK-TESTE", destino)
        assert destino.exists()
        assert destino.read_bytes().startswith(b"%PDF")


class TestObterCliente:
    def test_retorna_mock_quando_modo_mock(self, monkeypatch):
        import config.settings as s
        monkeypatch.setattr(s, "MODO_MOCK", True)
        cliente = obter_cliente()
        assert isinstance(cliente, BancoMockAPI)


class TestEnviarLote:
    def _inserir_conta(self, id_display, status="PENDENTE", valor=100.0, codigo="PIX001"):
        db.inserir_conta({
            "id_display": id_display, "arquivo_origem": f"{id_display}.pdf",
            "arquivo_atual": f"{id_display}.pdf", "tipo": "PIX",
            "fornecedor": "Fornecedor Teste", "valor": valor,
            "vencimento": "2026-06-20", "codigo_pagamento": codigo,
            "status": status,
        })

    def test_sem_pendentes_retorna_zeros(self):
        resultado = enviar_lote()
        assert resultado == {"enviadas": 0, "falhas": 0, "puladas": 0}

    def test_envia_contas_pendentes(self):
        self._inserir_conta("b001")
        self._inserir_conta("b002")
        resultado = enviar_lote()
        assert resultado["enviadas"] == 2
        assert resultado["falhas"] == 0

    def test_conta_sem_valor_e_pulada(self):
        self._inserir_conta("b001", valor=0)
        resultado = enviar_lote()
        assert resultado["puladas"] == 1
        assert resultado["enviadas"] == 0

    def test_conta_sem_codigo_e_pulada(self):
        self._inserir_conta("b001", codigo="")
        resultado = enviar_lote()
        assert resultado["puladas"] == 1

    def test_status_vira_enviado_apos_envio(self):
        self._inserir_conta("b001")
        enviar_lote()
        contas = db.buscar_contas_por_status("ENVIADO")
        assert len(contas) == 1
        assert contas[0]["id_transacao_banco"].startswith("MOCK-")

    def test_contas_nao_pendentes_ignoradas(self):
        self._inserir_conta("b001", status="PAGO")
        self._inserir_conta("b002", status="ERRO")
        resultado = enviar_lote()
        assert resultado["enviadas"] == 0


class TestAtualizarStatusLote:
    def test_sem_enviadas_retorna_zero(self):
        assert atualizar_status_lote() == 0

    def test_transacao_antiga_vira_pago(self):
        # Insere conta ENVIADA com ID que não está em _enviados (transação "antiga")
        id_ = db.inserir_conta({
            "id_display": "b001", "arquivo_origem": "b.pdf",
            "arquivo_atual": "b.pdf", "tipo": "PIX",
            "fornecedor": "X", "valor": 100.0, "vencimento": "2026-06-20",
            "codigo_pagamento": "0", "status": "ENVIADO",
        })
        db.atualizar_conta(id_, {"id_transacao_banco": "ID-SEM-TIMESTAMP"})
        pagas = atualizar_status_lote()
        assert pagas == 1
        assert db.buscar_contas_por_status("PAGO")[0]["id"] == id_
