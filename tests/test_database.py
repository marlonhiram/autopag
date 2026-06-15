# -*- coding: utf-8 -*-
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.fixture(autouse=True)
def banco_temporario(tmp_path, monkeypatch):
    """Redireciona DB_PATH para um arquivo temporário em cada teste."""
    import config.settings as s
    db_temp = tmp_path / "test_autopag.db"
    monkeypatch.setattr(s, "DB_PATH", db_temp)

    import core.database as db
    import importlib
    importlib.reload(db)
    return db_temp


import core.database as db


class TestInicializarBanco:
    def test_cria_tabela_contas(self, tmp_path):
        db.inicializar_banco()
        import sqlite3, config.settings as s
        with sqlite3.connect(str(s.DB_PATH)) as conn:
            tabelas = {r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        assert "contas" in tabelas
        assert "log_auditoria" in tabelas
        assert "config_banco" in tabelas

    def test_cria_trigger_timestamp(self):
        db.inicializar_banco()
        import sqlite3, config.settings as s
        with sqlite3.connect(str(s.DB_PATH)) as conn:
            triggers = {r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='trigger'").fetchall()}
        assert "trg_atualizar_timestamp" in triggers

    def test_idempotente(self):
        db.inicializar_banco()
        db.inicializar_banco()  # não deve lançar erro


class TestInserirEBuscar:
    def setup_method(self):
        db.inicializar_banco()

    def _conta_base(self, **kwargs):
        base = {
            "id_display": "boleto_001",
            "arquivo_origem": "boleto_001.pdf",
            "arquivo_atual": "boleto_001.pdf",
            "tipo": "PIX",
            "fornecedor": "Fornecedor Teste",
            "valor": 450.00,
            "vencimento": "2026-06-15",
            "codigo_pagamento": "000201TESTE",
            "status": "PENDENTE",
        }
        base.update(kwargs)
        return base

    def test_inserir_retorna_id(self):
        id_ = db.inserir_conta(self._conta_base())
        assert isinstance(id_, int)
        assert id_ > 0

    def test_buscar_todas_retorna_inserido(self):
        db.inserir_conta(self._conta_base())
        contas = db.buscar_todas_contas()
        assert len(contas) == 1
        assert contas[0]["fornecedor"] == "Fornecedor Teste"

    def test_buscar_por_status_filtra(self):
        db.inserir_conta(self._conta_base(id_display="b001", status="PENDENTE"))
        db.inserir_conta(self._conta_base(id_display="b002", status="PAGO"))
        assert len(db.buscar_contas_por_status("PENDENTE")) == 1
        assert len(db.buscar_contas_por_status("PAGO")) == 1
        assert len(db.buscar_contas_por_status("ENVIADO")) == 0

    def test_listar_contas_alias(self):
        db.inserir_conta(self._conta_base(status="ENVIADO"))
        assert len(db.listar_contas("ENVIADO")) == 1


class TestAtualizarConta:
    def setup_method(self):
        db.inicializar_banco()

    def test_atualiza_status(self):
        id_ = db.inserir_conta({
            "id_display": "b001", "arquivo_origem": "b.pdf",
            "arquivo_atual": "b.pdf", "tipo": "BOLETO",
            "fornecedor": "X", "valor": 100.0, "vencimento": "2026-06-20",
            "codigo_pagamento": "123", "status": "PENDENTE",
        })
        db.atualizar_conta(id_, {"status": "ENVIADO"})
        conta = db.buscar_todas_contas()[0]
        assert conta["status"] == "ENVIADO"

    def test_atualiza_multiplos_campos(self):
        id_ = db.inserir_conta({
            "id_display": "b001", "arquivo_origem": "b.pdf",
            "arquivo_atual": "b.pdf", "tipo": "PIX",
            "fornecedor": "Y", "valor": 200.0, "vencimento": "2026-06-20",
            "codigo_pagamento": "456", "status": "PENDENTE",
        })
        db.atualizar_conta(id_, {
            "status": "PAGO",
            "id_transacao_banco": "TX-123",
            "data_pagamento": "2026-06-14 10:00:00",
        })
        conta = db.buscar_todas_contas()[0]
        assert conta["status"] == "PAGO"
        assert conta["id_transacao_banco"] == "TX-123"

    def test_campos_vazios_nao_atualiza(self):
        id_ = db.inserir_conta({
            "id_display": "b001", "arquivo_origem": "b.pdf",
            "arquivo_atual": "b.pdf", "tipo": "PIX",
            "fornecedor": "Z", "valor": 300.0, "vencimento": "2026-06-20",
            "codigo_pagamento": "789", "status": "PENDENTE",
        })
        db.atualizar_conta(id_, {})  # não deve lançar erro
        assert db.buscar_todas_contas()[0]["status"] == "PENDENTE"


class TestContarPorStatus:
    def setup_method(self):
        db.inicializar_banco()

    def test_banco_vazio_retorna_zeros(self):
        resultado = db.contar_por_status()
        assert resultado["TOTAL"] == 0
        assert resultado["PENDENTE"] == 0

    def test_contagem_correta(self):
        for i, status in enumerate(["PENDENTE", "PENDENTE", "PAGO", "ERRO"]):
            db.inserir_conta({
                "id_display": f"b00{i}", "arquivo_origem": "b.pdf",
                "arquivo_atual": "b.pdf", "tipo": "PIX",
                "fornecedor": "X", "valor": 100.0, "vencimento": "2026-06-20",
                "codigo_pagamento": "0", "status": status,
            })
        resultado = db.contar_por_status()
        assert resultado["TOTAL"] == 4
        assert resultado["PENDENTE"] == 2
        assert resultado["PAGO"] == 1
        assert resultado["ERRO"] == 1


class TestPopularDadosDemo:
    def setup_method(self):
        db.inicializar_banco()

    def test_insere_12_registros(self):
        db.popular_dados_demo()
        assert len(db.buscar_todas_contas()) == 12

    def test_nao_duplica_em_segunda_chamada(self):
        db.popular_dados_demo()
        db.popular_dados_demo()
        assert len(db.buscar_todas_contas()) == 12


class TestRegistrarLog:
    def setup_method(self):
        db.inicializar_banco()

    def test_registra_sucesso(self):
        db.registrar_log("ENVIO_API", "SUCESSO", detalhe="teste")
        import sqlite3, config.settings as s
        with sqlite3.connect(str(s.DB_PATH)) as conn:
            rows = conn.execute("SELECT * FROM log_auditoria").fetchall()
        assert len(rows) == 1

    def test_registra_com_conta_id(self):
        id_ = db.inserir_conta({
            "id_display": "b001", "arquivo_origem": "b.pdf",
            "arquivo_atual": "b.pdf", "tipo": "PIX",
            "fornecedor": "X", "valor": 100.0, "vencimento": "2026-06-20",
            "codigo_pagamento": "0", "status": "PENDENTE",
        })
        db.registrar_log("LEITURA_PDF", "SUCESSO", conta_id=id_)
        import sqlite3, config.settings as s
        with sqlite3.connect(str(s.DB_PATH)) as conn:
            row = conn.execute("SELECT conta_id FROM log_auditoria").fetchone()
        assert row[0] == id_
