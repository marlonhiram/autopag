# -*- coding: utf-8 -*-
"""
Sistema de log de auditoria do AutoPag.
Cria um arquivo diário em logs/autopag_AAAA-MM-DD.log (RNF-07).
"""
import logging
import sys
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
import datetime

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config.settings import DIR_LOGS


def _criar_logger() -> logging.Logger:
    """Configura e retorna o logger principal da aplicação."""
    DIR_LOGS.mkdir(parents=True, exist_ok=True)

    log = logging.getLogger("autopag")
    if log.handlers:
        return log  # Evita duplicar handlers em reimportações

    log.setLevel(logging.DEBUG)

    fmt = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(module)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Arquivo: rotação à meia-noite, retenção de 90 dias (RNF-07)
    hoje = datetime.date.today().strftime("%Y-%m-%d")
    fh = TimedRotatingFileHandler(
        filename=str(DIR_LOGS / f"autopag_{hoje}.log"),
        when="midnight",
        interval=1,
        backupCount=90,
        encoding="utf-8",
    )
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)

    # Console — útil durante desenvolvimento
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(fmt)

    log.addHandler(fh)
    log.addHandler(ch)
    return log


# Instância global — todos os módulos importam este objeto
logger = _criar_logger()


def auditar(acao: str, resultado: str, detalhe: str = "", conta_id: int | None = None) -> None:
    """
    Registra uma operação no log de arquivo E na tabela log_auditoria.
    Atalho conveniente usado pelos módulos 3 e 4.

    Args:
        acao:      Código da operação — ex: 'ENVIO_API', 'DOWNLOAD_COMP'.
        resultado: 'SUCESSO' ou 'ERRO'.
        detalhe:   Mensagem descritiva.
        conta_id:  FK para contas (opcional).
    """
    nivel = logger.info if resultado == "SUCESSO" else logger.warning
    nivel(f"[{acao}] {resultado} — {detalhe}")

    # Persiste também no banco para rastreabilidade
    try:
        import sys
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
        from core.database import registrar_log
        registrar_log(acao, resultado, conta_id, detalhe or None)
    except Exception as e:
        logger.error(f"Falha ao persistir auditoria: {e}")