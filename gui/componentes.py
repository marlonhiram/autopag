# -*- coding: utf-8 -*-
"""
Componentes reutilizáveis da interface AutoPag.

  BadgeStatus  — pill colorida por status (PENDENTE, ENVIADO, PAGO, ERRO, REVISAO)
  BotaoAcao    — botão estilizado para a barra de ferramentas
  CartaoStats  — card de estatística com barra lateral colorida
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import customtkinter as ctk
from config.settings import (
    STATUS_CORES, STATUS_ICONES,
    COR_SUPERFICIE_ELEVADA, COR_TEXTO, COR_TEXTO_SECUNDARIO,
    COR_ACCENT, COR_ACCENT_HOVER, COR_BORDA,
)


class BadgeStatus(ctk.CTkFrame):
    """Pill colorida indicando o status de uma conta a pagar."""

    def __init__(self, parent: ctk.CTkBaseClass, status: str, **kwargs) -> None:
        cores = STATUS_CORES.get(status, {"bg": "#2A2A50", "fg": "#9090C0"})
        super().__init__(
            parent,
            fg_color=cores["bg"],
            corner_radius=6,
            **kwargs,
        )
        icone = STATUS_ICONES.get(status, "•")
        self._label = ctk.CTkLabel(
            self,
            text=f"{icone}  {status}",
            text_color=cores["fg"],
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            width=110,
            padx=8,
            pady=4,
        )
        self._label.pack()

    def atualizar(self, novo_status: str) -> None:
        """Muda a badge visualmente para refletir um novo status."""
        cores = STATUS_CORES.get(novo_status, {"bg": "#2A2A50", "fg": "#9090C0"})
        icone = STATUS_ICONES.get(novo_status, "•")
        self.configure(fg_color=cores["bg"])
        self._label.configure(text=f"{icone}  {novo_status}", text_color=cores["fg"])

    def vincular_eventos(self, on_enter, on_leave, on_click) -> None:
        """Propaga eventos de hover/clique para o componente pai (linha da tabela)."""
        for w in (self, self._label):
            w.bind("<Enter>",    on_enter)
            w.bind("<Leave>",    on_leave)
            w.bind("<Button-1>", on_click)


class BotaoAcao(ctk.CTkButton):
    """Botão principal de ação com ícone e estilo padrão."""

    def __init__(self, parent: ctk.CTkBaseClass, texto: str, icone: str = "", **kwargs) -> None:
        label = f"{icone}  {texto}" if icone else texto
        defaults: dict = {
            "text":          label,
            "font":          ctk.CTkFont(family="Segoe UI", size=13),
            "fg_color":      COR_ACCENT,
            "hover_color":   COR_ACCENT_HOVER,
            "corner_radius": 8,
            "height":        40,
            "cursor":        "hand2",
        }
        defaults.update(kwargs)
        super().__init__(parent, **defaults)


class CartaoStats(ctk.CTkFrame):
    """
    Card de estatística com número em destaque e rótulo.
    Possui barra colorida lateral como elemento visual de identidade.
    """

    def __init__(
        self,
        parent: ctk.CTkBaseClass,
        rotulo: str,
        valor: int | str,
        cor_destaque: str,
        **kwargs,
    ) -> None:
        super().__init__(
            parent,
            fg_color=COR_SUPERFICIE_ELEVADA,
            corner_radius=10,
            border_width=1,
            border_color=COR_BORDA,
            **kwargs,
        )

        # Barra de cor lateral
        ctk.CTkFrame(self, fg_color=cor_destaque, width=4, corner_radius=0).pack(
            side="left", fill="y"
        )

        # Conteúdo
        frame = ctk.CTkFrame(self, fg_color="transparent")
        frame.pack(side="left", padx=(12, 20), pady=12)

        self._lbl_valor = ctk.CTkLabel(
            frame,
            text=str(valor),
            font=ctk.CTkFont(family="Segoe UI", size=26, weight="bold"),
            text_color=COR_TEXTO,
        )
        self._lbl_valor.pack(anchor="w")

        ctk.CTkLabel(
            frame,
            text=rotulo,
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=COR_TEXTO_SECUNDARIO,
        ).pack(anchor="w")

    def atualizar_valor(self, novo_valor: int | str) -> None:
        """Atualiza o número exibido no card."""
        self._lbl_valor.configure(text=str(novo_valor))