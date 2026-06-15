# -*- coding: utf-8 -*-
"""
Camada de acesso ao banco de dados SQLite do AutoPag.

Responsabilidades:
  - Criação e migração das tabelas (DDL explícito, sem ORM).
  - CRUD de contas, log de auditoria e configuração bancária.
  - População de dados de demonstração para a Entrega 1.
"""
import sqlite3
from pathlib import Path
from typing import Optional
import sys

# Garante importação correta rodando de qualquer diretório
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config.settings import DB_PATH


# ─── DDL — scripts prontos para executar (RNF-03, seção 4 da doc) ─────────────

_SQL_CONTAS = """
CREATE TABLE IF NOT EXISTS contas (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    id_display          TEXT    NOT NULL,
    arquivo_origem      TEXT    NOT NULL DEFAULT '',
    arquivo_atual       TEXT    NOT NULL DEFAULT '',
    tipo                TEXT    NOT NULL CHECK(tipo IN ('PIX','BOLETO')),
    fornecedor          TEXT,
    valor               REAL,
    vencimento          TEXT,
    codigo_pagamento    TEXT    NOT NULL DEFAULT '',
    status              TEXT    NOT NULL DEFAULT 'PENDENTE'
                                CHECK(status IN ('PENDENTE','ENVIADO','PAGO','ERRO','REVISAO')),
    id_transacao_banco  TEXT,
    data_envio          TEXT,
    data_pagamento      TEXT,
    arquivo_comprovante TEXT,
    criado_em           TEXT    DEFAULT (datetime('now','localtime')),
    atualizado_em       TEXT    DEFAULT (datetime('now','localtime'))
);
"""

_SQL_LOG_AUDITORIA = """
CREATE TABLE IF NOT EXISTS log_auditoria (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT    DEFAULT (datetime('now','localtime')),
    acao      TEXT    NOT NULL,
    conta_id  INTEGER,
    resultado TEXT    NOT NULL CHECK(resultado IN ('SUCESSO','ERRO')),
    detalhe   TEXT,
    FOREIGN KEY (conta_id) REFERENCES contas(id)
);
"""

_SQL_CONFIG_BANCO = """
CREATE TABLE IF NOT EXISTS config_banco (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    banco         TEXT    NOT NULL CHECK(banco IN ('BRADESCO','BB')),
    client_id     TEXT    NOT NULL,
    client_secret TEXT    NOT NULL,
    caminho_cert  TEXT    NOT NULL,
    url_base_api  TEXT    NOT NULL,
    ativo         INTEGER DEFAULT 1
);
"""

_SQL_TRIGGER_TS = """
CREATE TRIGGER IF NOT EXISTS trg_atualizar_timestamp
AFTER UPDATE ON contas
FOR EACH ROW
BEGIN
    UPDATE contas
    SET    atualizado_em = datetime('now','localtime')
    WHERE  id = OLD.id;
END;
"""


def _conectar() -> sqlite3.Connection:
    """Retorna uma conexão SQLite com row_factory e pragmas de segurança."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


def inicializar_banco() -> None:
    """
    Cria as tabelas e o trigger caso ainda não existam.
    Chamado uma única vez na inicialização da aplicação.
    """
    with _conectar() as conn:
        conn.execute(_SQL_CONTAS)
        conn.execute(_SQL_LOG_AUDITORIA)
        conn.execute(_SQL_CONFIG_BANCO)
        conn.execute(_SQL_TRIGGER_TS)
        conn.commit()


def popular_dados_demo() -> None:
    """
    Insere registros de demonstração se a tabela contas estiver vazia.
    Exclusivo da Entrega 1 — substitua por dados reais nas próximas entregas.
    """
    with _conectar() as conn:
        if conn.execute("SELECT COUNT(*) FROM contas").fetchone()[0] > 0:
            return  # Banco já tem dados — não sobrescreve

        demo = [
            ("boleto_001", "Papel & Cia Ltda",         450.00,  "2026-06-15", "PIX",    "PENDENTE"),
            ("boleto_002", "Gráfica Nordeste",         1230.50,  "2026-06-16", "BOLETO", "ENVIADO"),
            ("boleto_003", "TechSupri Informática",     890.00,  "2026-06-14", "PIX",    "PAGO"),
            ("boleto_004", "Distribuidora Atlas",       345.75,  "2026-06-17", "BOLETO", "ERRO"),
            ("boleto_005", "Escritório Total ME",      2100.00,  "2026-06-18", "PIX",    "PENDENTE"),
            ("boleto_006", "Limpeza & Conservação",     680.00,  "2026-06-19", "BOLETO", "PENDENTE"),
            ("boleto_007", "Segurança Corporativa",    3500.00,  "2026-06-20", "BOLETO", "ENVIADO"),
            ("boleto_008", "Internet Fibra Pro",        299.90,  "2026-06-13", "PIX",    "PAGO"),
            ("boleto_009", "Aluguel Comercial SA",     5800.00,  "2026-06-10", "BOLETO", "REVISAO"),
            ("boleto_010", "Fornecedor X Ltda",         120.00,  "2026-06-21", "PIX",    "PENDENTE"),
            ("boleto_011", "InfoTech Soluções",         875.30,  "2026-06-22", "BOLETO", "PENDENTE"),
            ("boleto_012", "Corretora de Seguros SP",  1450.00,  "2026-06-12", "PIX",    "PAGO"),
        ]

        conn.executemany(
            """
            INSERT INTO contas
                (id_display, fornecedor, valor, vencimento, tipo, status,
                 arquivo_origem, arquivo_atual, codigo_pagamento)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (r[0], r[1], r[2], r[3], r[4], r[5],
                 f"{r[0]}.pdf", f"{r[0]}.pdf", "000201DEMO")
                for r in demo
            ],
        )
        conn.commit()


def buscar_todas_contas() -> list[dict]:
    """
    Retorna todas as contas ordenadas por ID crescente.

    Returns:
        Lista de dicionários com todos os campos da tabela contas.
    """
    with _conectar() as conn:
        rows = conn.execute("SELECT * FROM contas ORDER BY id ASC").fetchall()
        return [dict(r) for r in rows]


def buscar_contas_por_status(status: str) -> list[dict]:
    """
    Filtra contas por status.

    Args:
        status: 'PENDENTE', 'ENVIADO', 'PAGO', 'ERRO' ou 'REVISAO'.

    Returns:
        Lista de dicionários das contas filtradas.
    """
    with _conectar() as conn:
        rows = conn.execute(
            "SELECT * FROM contas WHERE status = ? ORDER BY id ASC", (status,)
        ).fetchall()
        return [dict(r) for r in rows]


def atualizar_status_conta(conta_id: int, novo_status: str) -> None:
    """
    Atualiza o status de uma conta. O trigger cuida do atualizado_em.

    Args:
        conta_id:    ID da conta na tabela contas.
        novo_status: Novo status a ser aplicado.
    """
    with _conectar() as conn:
        conn.execute(
            "UPDATE contas SET status = ? WHERE id = ?",
            (novo_status, conta_id),
        )
        conn.commit()


def registrar_log(
    acao: str,
    resultado: str,
    conta_id: Optional[int] = None,
    detalhe: Optional[str] = None,
) -> None:
    """
    Registra uma operação no log de auditoria (RF-15).

    Args:
        acao:      Código da operação — ex: 'LEITURA_PDF', 'ENVIO_API'.
        resultado: 'SUCESSO' ou 'ERRO'.
        conta_id:  FK para contas (opcional).
        detalhe:   Mensagem descritiva ou stack trace completo (opcional).
    """
    with _conectar() as conn:
        conn.execute(
            """
            INSERT INTO log_auditoria (acao, resultado, conta_id, detalhe)
            VALUES (?, ?, ?, ?)
            """,
            (acao, resultado, conta_id, detalhe),
        )
        conn.commit()


def contar_por_status() -> dict[str, int]:
    """
    Retorna contagem de contas agrupadas por status, mais o total geral.

    Returns:
        Dict com chaves 'TOTAL', 'PENDENTE', 'ENVIADO', 'PAGO', 'ERRO', 'REVISAO'.
    """
    with _conectar() as conn:
        rows = conn.execute(
            "SELECT status, COUNT(*) AS n FROM contas GROUP BY status"
        ).fetchall()

    resultado = {"TOTAL": 0, "PENDENTE": 0, "ENVIADO": 0, "PAGO": 0, "ERRO": 0, "REVISAO": 0}
    for r in rows:
        resultado[r["status"]] = r["n"]
        resultado["TOTAL"] += r["n"]
    return resultado


# ─── Funções adicionais usadas pelos módulos 3 e 4 ───────────────────────────

def listar_contas(status: str) -> list[dict]:
    """Alias de buscar_contas_por_status para compatibilidade interna."""
    return buscar_contas_por_status(status)


def atualizar_conta(conta_id: int, campos: dict) -> None:
    """
    Atualiza campos arbitrários de uma conta pelo ID.

    Args:
        conta_id: ID da conta na tabela.
        campos:   Dicionário {coluna: novo_valor}.
    """
    if not campos:
        return
    set_clause = ", ".join(f"{k} = ?" for k in campos)
    valores    = list(campos.values()) + [conta_id]
    with _conectar() as conn:
        conn.execute(f"UPDATE contas SET {set_clause} WHERE id = ?", valores)
        conn.commit()


def obter_config_banco(banco: str) -> dict | None:
    """
    Retorna a configuração ativa de um banco na tabela config_banco.

    Args:
        banco: 'BRADESCO' ou 'BB'.

    Returns:
        Dict com os campos da config ou None se não cadastrado.
    """
    with _conectar() as conn:
        row = conn.execute(
            "SELECT * FROM config_banco WHERE banco = ? AND ativo = 1 LIMIT 1",
            (banco,)
        ).fetchone()
        return dict(row) if row else None


def inserir_conta(dados: dict) -> int:
    """
    Insere uma nova conta no banco.

    Args:
        dados: Dicionário com campos da tabela contas.

    Returns:
        ID gerado (lastrowid).
    """
    campos  = ["id_display","arquivo_origem","arquivo_atual","tipo",
                "fornecedor","valor","vencimento","codigo_pagamento","status"]
    valores = [dados.get(c) for c in campos]
    with _conectar() as conn:
        cur = conn.execute(
            f"INSERT INTO contas ({','.join(campos)}) VALUES ({','.join(['?']*len(campos))})",
            valores,
        )
        conn.commit()
        return cur.lastrowid
