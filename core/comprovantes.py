# -*- coding: utf-8 -*-
"""
Módulo 4 — Comprovantes: download, merge intercalado e impressão.

Fluxo (RF-13/RF-14):
  1. Para cada conta PAGA sem comprovante: baixa o PDF do banco.
  2. Merge intercalado: boleto_001 + comprovante_001 + boleto_002 + ...
  3. Envia o PDF final para a impressora padrão do Windows.
"""

import platform
import time
from pathlib import Path

from config import settings
from core import banco_api, database
from core.logger import auditar


def baixar_comprovantes() -> int:
    """
    Baixa comprovantes de todas as contas PAGAS que ainda não têm PDF (RF-13).

    Returns:
        quantidade de comprovantes baixados.
    """
    baixados = 0
    pagas = [c for c in database.listar_contas("PAGO")
             if not c["arquivo_comprovante"]]
    if not pagas:
        return 0

    cliente = banco_api.obter_cliente()
    for conta in pagas:
        try:
            destino = settings.PASTA_COMPROVANTES / \
                f"comprovante_{conta['id_display']}.pdf"
            cliente.baixar_comprovante(conta["id_transacao_banco"], destino)
            database.atualizar_conta(conta["id"],
                                     {"arquivo_comprovante": str(destino)})
            baixados += 1
            auditar("DOWNLOAD_COMP", "SUCESSO", destino.name, conta["id"])
        except Exception as exc:
            auditar("DOWNLOAD_COMP", "ERRO",
                    f"{conta['id_display']}: {exc}", conta["id"])
    return baixados


def merge_intercalado() -> Path | None:
    """
    Gera um único PDF intercalando boleto + comprovante na ordem das
    contas pagas (RF-14): boleto_001, comp_001, boleto_002, comp_002...

    Contas pagas sem comprovante ou com boleto ausente em disco são
    puladas com registro em auditoria — nunca quebram o lote.

    Returns:
        caminho do PDF final, ou None se não havia nada para imprimir.
    """
    try:
        from pypdf import PdfWriter
    except ImportError as exc:
        raise RuntimeError(
            "Biblioteca pypdf não instalada. Execute: pip install pypdf") from exc

    pagas = [c for c in database.listar_contas("PAGO")
             if c["arquivo_comprovante"]]
    # ordem de leitura original (boleto_001 antes de boleto_002)
    pagas.sort(key=lambda c: c["id_display"])
    if not pagas:
        return None

    writer = PdfWriter()
    incluidas = 0
    for conta in pagas:
        boleto = Path(conta["arquivo_atual"])
        comp = Path(conta["arquivo_comprovante"])
        if not boleto.exists() or not comp.exists():
            auditar("IMPRESSAO", "ERRO",
                    f"{conta['id_display']}: arquivo ausente em disco "
                    f"(boleto={boleto.exists()}, comp={comp.exists()})",
                    conta["id"])
            continue
        try:
            writer.append(str(boleto))
            writer.append(str(comp))
            incluidas += 1
        except Exception as exc:
            auditar("IMPRESSAO", "ERRO",
                    f"{conta['id_display']}: PDF corrompido no merge: {exc}",
                    conta["id"])

    if incluidas == 0:
        return None

    saida = settings.PASTA_COMPROVANTES / \
        f"lote_impressao_{time.strftime('%Y-%m-%d_%H%M%S')}.pdf"
    with open(saida, "wb") as f:
        writer.write(f)
    auditar("IMPRESSAO", "SUCESSO",
            f"merge gerado: {saida.name} ({incluidas} pares)")
    return saida


def imprimir(caminho: Path) -> bool:
    """
    Envia o PDF para a impressora padrão do Windows via os.startfile.

    Em sistemas não-Windows (ambiente de desenvolvimento), apenas abre
    o arquivo — a impressão física é exclusiva do deploy em produção.

    Returns:
        True se o comando de impressão foi disparado.
    """
    import os
    try:
        if platform.system() == "Windows":
            os.startfile(str(caminho), "print")  # type: ignore[attr-defined]
        else:
            auditar("IMPRESSAO", "SUCESSO",
                    f"{caminho.name}: ambiente não-Windows, impressão pulada")
            return False
        auditar("IMPRESSAO", "SUCESSO", f"enviado à impressora: {caminho.name}")
        return True
    except Exception as exc:
        auditar("IMPRESSAO", "ERRO", f"{caminho.name}: {exc}")
        raise RuntimeError(
            f"Falha ao enviar para a impressora: {exc}. "
            f"Verifique se há impressora padrão configurada no Windows.") from exc


def fluxo_completo() -> dict:
    """
    Operação do botão 'Baixar e Imprimir' (RF-09):
    atualiza status -> baixa comprovantes -> merge -> imprime.

    Returns:
        dict com o resumo de cada etapa para feedback na interface.
    """
    pagas_novas = banco_api.atualizar_status_lote()
    baixados = baixar_comprovantes()
    arquivo = merge_intercalado()
    impresso = imprimir(arquivo) if arquivo else False
    return {
        "pagas_novas": pagas_novas,
        "baixados": baixados,
        "arquivo": str(arquivo) if arquivo else None,
        "impresso": impresso,
    }