# -*- coding: utf-8 -*-
"""
Tabela customizada de contas a pagar — implementada com CTkFrames.

Componentes:
  _LinhaTabela  — uma linha da tabela com hover e seleção
  TabelaContas  — cabeçalho fixo + área scrollável + estado vazio
"""
import sys
from pathlib import Path
from typing import Callable, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import customtkinter as ctk
from gui.componentes import BadgeStatus
from core.utils import formatar_moeda, formatar_data, truncar_texto
from config.settings import (
    COR_FUNDO, COR_SUPERFICIE, COR_LINHA_PAR, COR_LINHA_IMPAR,
    COR_LINHA_HOVER, COR_LINHA_SELECIONADA, COR_BORDA,
    COR_ACCENT, COR_TEXTO, COR_TEXTO_SECUNDARIO, COR_TEXTO_MUTED,
)

ALTURA_LINHA = 48  # pixels fixos por linha


class _LinhaTabela(ctk.CTkFrame):
    """
    Frame que representa uma única linha da tabela de contas.
    Gerencia hover visual e estado de seleção.
    """

    def __init__(
        self,
        parent: ctk.CTkBaseClass,
        conta: dict,
        index: int,
        callback_selecao: Optional[Callable] = None,
        **kwargs,
    ) -> None:
        self._cor_bg = COR_LINHA_PAR if index % 2 == 0 else COR_LINHA_IMPAR
        super().__init__(
            parent,
            fg_color=self._cor_bg,
            corner_radius=0,
            height=ALTURA_LINHA,
            **kwargs,
        )
        self.pack_propagate(False)

        self._conta           = conta
        self._selecionada     = False
        self._callback        = callback_selecao
        self._filhos: list    = []

        self._construir()
        self._vincular_eventos()

    # ── Construção visual ─────────────────────────────────────────────────────

    def _construir(self) -> None:
        """Cria os labels e a badge de status da linha."""
        c = self._conta

        # Tipo recebe cor própria (Pix em azul-claro, Boleto em cinza)
        tipo = c.get("tipo", "—")
        cor_tipo = "#7BA3F8" if tipo == "PIX" else COR_TEXTO_SECUNDARIO

        colunas = [
            # (texto, largura, âncora, cor_texto, padx_esq)
            (c.get("id_display", "—"),              130, "w",      COR_TEXTO,            14),
            (truncar_texto(c.get("fornecedor"), 33), 260, "w",      COR_TEXTO,             4),
            (formatar_moeda(c.get("valor")),          120, "e",      COR_TEXTO,             4),
            (formatar_data(c.get("vencimento")),      115, "center", COR_TEXTO_SECUNDARIO,  4),
            (tipo,                                     85, "center", cor_tipo,              4),
        ]

        for texto, larg, ancora, cor, padx in colunas:
            lbl = ctk.CTkLabel(
                self,
                text=texto,
                width=larg,
                anchor=ancora,
                font=ctk.CTkFont(family="Segoe UI", size=12),
                text_color=cor,
            )
            lbl.pack(side="left", padx=(padx, 3))
            self._filhos.append(lbl)

        # Badge de status
        self._badge = BadgeStatus(self, c.get("status", "PENDENTE"))
        self._badge.pack(side="left", padx=(8, 0))
        self._filhos.append(self._badge)

    # ── Eventos ───────────────────────────────────────────────────────────────

    def _vincular_eventos(self) -> None:
        """Vincula hover e clique no frame e em todos os filhos diretos."""
        for w in [self] + self._filhos:
            w.bind("<Enter>",    self._on_enter)
            w.bind("<Leave>",    self._on_leave)
            w.bind("<Button-1>", self._on_click)

        # Badge tem sub-widget interno — propaga também
        self._badge.vincular_eventos(self._on_enter, self._on_leave, self._on_click)

    def _on_enter(self, event=None) -> None:
        if not self._selecionada:
            self.configure(fg_color=COR_LINHA_HOVER)

    def _on_leave(self, event=None) -> None:
        if self._selecionada:
            return
        # Evita flash ao mover entre widgets filhos dentro da mesma linha
        try:
            w = self.winfo_containing(event.x_root, event.y_root)
            if w is not None:
                caminho_w    = str(w)
                caminho_self = str(self)
                if caminho_w == caminho_self or caminho_w.startswith(caminho_self + "."):
                    return
        except Exception:
            pass
        self.configure(fg_color=self._cor_bg)

    def _on_click(self, event=None) -> None:
        if self._callback:
            self._callback(self)

    # ── API pública ───────────────────────────────────────────────────────────

    def selecionar(self) -> None:
        self._selecionada = True
        self.configure(fg_color=COR_LINHA_SELECIONADA)

    def desselecionar(self) -> None:
        self._selecionada = False
        self.configure(fg_color=self._cor_bg)

    @property
    def conta(self) -> dict:
        return self._conta


# ─────────────────────────────────────────────────────────────────────────────


class TabelaContas(ctk.CTkFrame):
    """
    Componente completo da tabela de contas a pagar.
    Contém cabeçalho fixo, área scrollável e estado vazio com instrução.
    """

    def __init__(self, parent: ctk.CTkBaseClass, **kwargs) -> None:
        super().__init__(parent, fg_color=COR_FUNDO, corner_radius=0, **kwargs)

        self._linhas:                list[_LinhaTabela] = []
        self._widgets_conteudo:      list               = []
        self._linha_selecionada:     Optional[_LinhaTabela] = None
        self._cb_selecao_externa:    Optional[Callable] = None

        self._construir_cabecalho()
        self._construir_area_scroll()

    # ── Construção ────────────────────────────────────────────────────────────

    def _construir_cabecalho(self) -> None:
        """Cabeçalho fixo com labels de coluna em caixa-alta."""
        hdr = ctk.CTkFrame(self, fg_color=COR_FUNDO, corner_radius=0, height=38)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)

        colunas_hdr = [
            ("Identificador", 130, "w",      14),
            ("Fornecedor",    260, "w",       4),
            ("Valor (R$)",    120, "e",       4),
            ("Vencimento",    115, "center",  4),
            ("Tipo",           85, "center",  4),
            ("Status",        140, "center",  8),
        ]
        for titulo, larg, ancora, padx in colunas_hdr:
            ctk.CTkLabel(
                hdr,
                text=titulo.upper(),
                width=larg,
                anchor=ancora,
                font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
                text_color=COR_TEXTO_MUTED,
            ).pack(side="left", padx=(padx, 3))

        # Linha separadora do cabeçalho
        ctk.CTkFrame(self, fg_color=COR_BORDA, height=1, corner_radius=0).pack(fill="x")

    def _construir_area_scroll(self) -> None:
        """Área scrollável que receberá as linhas da tabela."""
        self._scroll = ctk.CTkScrollableFrame(
            self,
            fg_color="transparent",
            scrollbar_button_color=COR_SUPERFICIE,
            scrollbar_button_hover_color=COR_ACCENT,
            corner_radius=0,
        )
        self._scroll.pack(fill="both", expand=True)

    # ── API pública ───────────────────────────────────────────────────────────

    def atualizar(self, contas: list[dict]) -> None:
        """
        Re-renderiza toda a tabela com a lista de contas recebida.

        Args:
            contas: Lista de dicionários retornada pelo banco.
        """
        # Destrói conteúdo anterior (linhas + separadores + label vazio)
        for w in self._widgets_conteudo:
            w.destroy()
        self._widgets_conteudo.clear()
        self._linhas.clear()
        self._linha_selecionada = None

        if not contas:
            self._renderizar_estado_vazio()
            return

        for i, conta in enumerate(contas):
            linha = _LinhaTabela(
                self._scroll,
                conta=conta,
                index=i,
                callback_selecao=self._on_linha_clicada,
            )
            linha.pack(fill="x")
            self._widgets_conteudo.append(linha)
            self._linhas.append(linha)

            sep = ctk.CTkFrame(self._scroll, fg_color=COR_BORDA, height=1, corner_radius=0)
            sep.pack(fill="x")
            self._widgets_conteudo.append(sep)

    def _renderizar_estado_vazio(self) -> None:
        """Exibe mensagem orientando o usuário a importar boletos."""
        lbl = ctk.CTkLabel(
            self._scroll,
            text="Nenhuma conta encontrada.\n\nClique em  📂  Processar Pasta  para importar boletos.",
            font=ctk.CTkFont(family="Segoe UI", size=14),
            text_color=COR_TEXTO_SECUNDARIO,
            justify="center",
        )
        lbl.pack(expand=True, pady=80)
        self._widgets_conteudo.append(lbl)

    def ao_selecionar(self, callback: Callable) -> None:
        """
        Registra o callback chamado quando uma linha é selecionada.

        Args:
            callback: Função que recebe o dict da conta selecionada.
        """
        self._cb_selecao_externa = callback

    @property
    def conta_selecionada(self) -> Optional[dict]:
        """Dicionário da conta atualmente selecionada ou None."""
        return self._linha_selecionada.conta if self._linha_selecionada else None

    # ── Privado ───────────────────────────────────────────────────────────────

    def _on_linha_clicada(self, linha: _LinhaTabela) -> None:
        """Garante seleção exclusiva: deseleciona a anterior antes de selecionar a nova."""
        if self._linha_selecionada and self._linha_selecionada is not linha:
            self._linha_selecionada.desselecionar()
        linha.selecionar()
        self._linha_selecionada = linha
        if self._cb_selecao_externa:
            self._cb_selecao_externa(linha.conta)