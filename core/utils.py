# -*- coding: utf-8 -*-
"""
Funções utilitárias do AutoPag.
"""
from datetime import datetime
from pathlib import Path


def formatar_moeda(valor: float | None) -> str:
    """
    Converte float para o padrão monetário brasileiro.

    Args:
        valor: Número de ponto flutuante ou None.

    Returns:
        'R$ 1.230,50' ou 'N/D' se None.
    """
    if valor is None:
        return "N/D"
    return "R$ {:,.2f}".format(valor).replace(",", "X").replace(".", ",").replace("X", ".")


def formatar_data(data_iso: str | None) -> str:
    """
    Converte data ISO 'YYYY-MM-DD' para 'DD/MM/YYYY'.

    Args:
        data_iso: Data em formato ISO ou None.

    Returns:
        '15/06/2026' ou 'N/D' em caso de falha.
    """
    if not data_iso:
        return "N/D"
    try:
        return datetime.strptime(data_iso[:10], "%Y-%m-%d").strftime("%d/%m/%Y")
    except ValueError:
        return data_iso


def truncar_texto(texto: str | None, limite: int = 32) -> str:
    """
    Trunca texto longo adicionando '…' ao final.

    Args:
        texto:  Texto de entrada. None devolve '—'.
        limite: Número máximo de caracteres antes do truncamento.

    Returns:
        Texto original ou truncado com '…'.
    """
    if not texto:
        return "—"
    return texto if len(texto) <= limite else texto[: limite - 1] + "…"


def criar_diretorios(base_dir: Path) -> None:
    """
    Cria a estrutura de diretórios necessária para a aplicação.
    Seguro para chamar múltiplas vezes (exist_ok=True).

    Args:
        base_dir: Diretório raiz do projeto.
    """
    dirs = [
        base_dir / "dados" / "A_Pagar",
        base_dir / "dados" / "Processados",
        base_dir / "dados" / "Comprovantes",
        base_dir / "logs",
        base_dir / "assets",
        base_dir / "config" / "certificados",
    ]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)