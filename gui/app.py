# -*- coding: utf-8 -*-
"""
Módulo 2 — Janela principal do AutoPag.

Layout:
  ┌──────────────────────────────────────────────────────┐
  │  Cabeçalho: logo + título + versão                   │
  │  Cards: Total | Pendentes | Enviadas | Pagas | Erros │
  │  Toolbar: Processar | Enviar | Imprimir | Demo       │
  │  Barra de progresso (visível apenas durante operações│
  │  Tabela customizada (gui.tabela.TabelaContas)        │
  │  Barra de status                                     │
  └──────────────────────────────────────────────────────┘

Toda operação demorada roda em thread daemon — a interface nunca
congela. Resultados chegam de volta via self.after(0, callback).
"""
import sys
import threading
import time
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import customtkinter as ctk

from gui.tabela import TabelaContas
from gui.componentes import BotaoAcao, CartaoStats
from core import database as db
from core.logger import logger
from config.settings import (
    APP_TITULO, APP_VERSAO, APP_LARGURA, APP_ALTURA, MODO_SIMULACAO,
    COR_FUNDO, COR_SUPERFICIE, COR_SUPERFICIE_ELEVADA,
    COR_BORDA, COR_ACCENT, COR_ACCENT_HOVER,
    COR_TEXTO, COR_TEXTO_SECUNDARIO,
)


class JanelaPrincipal(ctk.CTk):
    """
    Janela raiz do AutoPag.
    Orquestra layout, dados, threading e feedback visual.
    """

    def __init__(self) -> None:
        super().__init__()
        self.title(APP_TITULO)
        self.geometry(f"{APP_LARGURA}x{APP_ALTURA}")
        self.minsize(920, 580)
        self.configure(fg_color=COR_FUNDO)
        self._centralizar()
        self._operacao_em_curso = False

        self._construir_cabecalho()
        self._construir_stats()
        self._construir_toolbar()
        self._construir_progresso()
        self._construir_tabela()
        self._construir_barra_status()
        self._carregar_contas()

    # ── Posicionamento ────────────────────────────────────────────────────────

    def _centralizar(self) -> None:
        self.update_idletasks()
        x = (self.winfo_screenwidth()  - APP_LARGURA) // 2
        y = (self.winfo_screenheight() - APP_ALTURA)  // 2
        self.geometry(f"{APP_LARGURA}x{APP_ALTURA}+{x}+{y}")

    # ── Widgets ───────────────────────────────────────────────────────────────

    def _construir_cabecalho(self) -> None:
        frame = ctk.CTkFrame(self, fg_color=COR_SUPERFICIE, corner_radius=0, height=62)
        frame.pack(fill="x")
        frame.pack_propagate(False)

        ctk.CTkLabel(frame, text="🏦", font=ctk.CTkFont(size=26)).pack(
            side="left", padx=(20, 8))

        bloco = ctk.CTkFrame(frame, fg_color="transparent")
        bloco.pack(side="left")
        ctk.CTkLabel(bloco, text="AutoPag",
                     font=ctk.CTkFont(family="Segoe UI", size=17, weight="bold"),
                     text_color=COR_TEXTO).pack(anchor="w")
        ctk.CTkLabel(bloco, text="Automação de Contas a Pagar",
                     font=ctk.CTkFont(family="Segoe UI", size=10),
                     text_color=COR_TEXTO_SECUNDARIO).pack(anchor="w")

        modo_txt = "● SIMULAÇÃO" if MODO_SIMULACAO else "● PRODUÇÃO"
        modo_cor = "#F59E0B" if MODO_SIMULACAO else "#10B981"
        ctk.CTkLabel(frame, text=modo_txt,
                     font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
                     text_color=modo_cor).pack(side="right", padx=(0, 16))
        ctk.CTkLabel(frame, text=APP_VERSAO,
                     font=ctk.CTkFont(family="Segoe UI", size=11),
                     text_color=COR_TEXTO_SECUNDARIO).pack(side="right", padx=(16, 4))

        ctk.CTkFrame(self, fg_color=COR_BORDA, height=1, corner_radius=0).pack(fill="x")

    def _construir_stats(self) -> None:
        frame = ctk.CTkFrame(self, fg_color=COR_FUNDO, corner_radius=0)
        frame.pack(fill="x", padx=20, pady=(14, 0))

        cfg = [
            ("Total",     "TOTAL",    "#4F7EF5"),
            ("Pendentes", "PENDENTE", "#D97706"),
            ("Enviadas",  "ENVIADO",  "#2563EB"),
            ("Pagas",     "PAGO",     "#059669"),
            ("Com Erro",  "ERRO",     "#DC2626"),
        ]
        self._cards: dict[str, CartaoStats] = {}
        for rotulo, chave, cor in cfg:
            card = CartaoStats(frame, rotulo=rotulo, valor=0, cor_destaque=cor)
            card.pack(side="left", padx=(0, 10), pady=4, ipadx=4, ipady=2)
            self._cards[chave] = card

    def _construir_toolbar(self) -> None:
        frame = ctk.CTkFrame(self, fg_color=COR_FUNDO, corner_radius=0)
        frame.pack(fill="x", padx=20, pady=12)

        self._btn_processar = BotaoAcao(
            frame, texto="Processar Pasta", icone="📂", width=185,
            command=self._cmd_processar_pasta)
        self._btn_processar.pack(side="left", padx=(0, 8))

        self._btn_enviar = BotaoAcao(
            frame, texto="Enviar Lote", icone="📤", width=155,
            fg_color="#1D4ED8", hover_color="#2563EB",
            command=self._cmd_enviar_lote)
        self._btn_enviar.pack(side="left", padx=(0, 8))

        self._btn_imprimir = BotaoAcao(
            frame, texto="Baixar e Imprimir", icone="🖨️", width=185,
            fg_color="#065F46", hover_color="#059669",
            command=self._cmd_baixar_imprimir)
        self._btn_imprimir.pack(side="left", padx=(0, 8))

        # Separador visual
        ctk.CTkFrame(frame, fg_color=COR_BORDA, width=1, corner_radius=0).pack(
            side="left", fill="y", padx=12, pady=6)

        # Botão Demo — destaque laranja, exclusivo para apresentações
        self._btn_demo = BotaoAcao(
            frame, texto="Demo Completo", icone="🎬", width=175,
            fg_color="#92400E", hover_color="#B45309",
            command=self._cmd_demo_completo)
        self._btn_demo.pack(side="left", padx=(0, 8))

        # Atualizar (secundário)
        ctk.CTkButton(
            frame, text="↻  Atualizar",
            font=ctk.CTkFont(family="Segoe UI", size=13),
            fg_color="transparent", hover_color=COR_SUPERFICIE,
            text_color=COR_TEXTO_SECUNDARIO,
            border_width=1, border_color=COR_BORDA,
            corner_radius=8, height=40, width=120, cursor="hand2",
            command=self._carregar_contas,
        ).pack(side="left")

        ctk.CTkFrame(self, fg_color=COR_BORDA, height=1, corner_radius=0).pack(fill="x")

    def _construir_progresso(self) -> None:
        """Barra de progresso — fica oculta e aparece apenas durante operações."""
        self._frame_progresso = ctk.CTkFrame(
            self, fg_color=COR_SUPERFICIE, corner_radius=0, height=36)
        # não faz pack aqui — aparece sob demanda

        self._progresso = ctk.CTkProgressBar(
            self._frame_progresso,
            mode="indeterminate",
            fg_color=COR_BORDA,
            progress_color=COR_ACCENT,
            height=4,
            corner_radius=0,
        )
        self._progresso.pack(fill="x", side="bottom")

        self._lbl_progresso = ctk.CTkLabel(
            self._frame_progresso,
            text="",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=COR_TEXTO_SECUNDARIO,
        )
        self._lbl_progresso.pack(side="left", padx=16, pady=6)

    def _construir_tabela(self) -> None:
        self._tabela = TabelaContas(self)
        self._tabela.pack(fill="both", expand=True)
        self._tabela.ao_selecionar(self._on_conta_selecionada)

    def _construir_barra_status(self) -> None:
        ctk.CTkFrame(self, fg_color=COR_BORDA, height=1, corner_radius=0).pack(fill="x")
        frame = ctk.CTkFrame(self, fg_color=COR_SUPERFICIE, corner_radius=0, height=28)
        frame.pack(fill="x")
        frame.pack_propagate(False)

        self._lbl_status = ctk.CTkLabel(
            frame, text="Pronto",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=COR_TEXTO_SECUNDARIO)
        self._lbl_status.pack(side="left", padx=16)

        self._lbl_timestamp = ctk.CTkLabel(
            frame, text="",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=COR_TEXTO_SECUNDARIO)
        self._lbl_timestamp.pack(side="right", padx=16)

    # ── Dados ─────────────────────────────────────────────────────────────────

    def _carregar_contas(self) -> None:
        """Atualiza tabela e cards com dados frescos do banco."""
        try:
            contas    = db.buscar_todas_contas()
            contagens = db.contar_por_status()
            self._tabela.atualizar(contas)
            for chave, card in self._cards.items():
                card.atualizar_valor(contagens.get(chave, 0))
            total = len(contas)
            agora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            self._lbl_status.configure(
                text=f"✓  {total} conta{'s' if total != 1 else ''} carregada{'s' if total != 1 else ''}")
            self._lbl_timestamp.configure(text=f"Atualizado em {agora}")
        except Exception as e:
            logger.error(f"Falha ao carregar contas: {e}", exc_info=True)
            self._mostrar_erro("Não foi possível carregar as contas.\nVeja o arquivo de log.")

    def _on_conta_selecionada(self, conta: dict) -> None:
        self._lbl_status.configure(
            text=f"Selecionado:  {conta.get('id_display', '—')}  •  "
                 f"{conta.get('fornecedor', '—')}  •  "
                 f"{conta.get('status', '—')}")

    # ── Threading helpers ─────────────────────────────────────────────────────

    def _iniciar_operacao(self, mensagem: str) -> None:
        """Exibe barra de progresso e bloqueia botões de ação."""
        self._operacao_em_curso = True
        for btn in (self._btn_processar, self._btn_enviar,
                    self._btn_imprimir, self._btn_demo):
            btn.configure(state="disabled")
        self._lbl_progresso.configure(text=mensagem)
        self._frame_progresso.pack(fill="x", after=self._tabela)  # injeta acima da tabela
        self._progresso.start()
        self._lbl_status.configure(text=f"⏳  {mensagem}")

    def _finalizar_operacao(self) -> None:
        """Oculta barra de progresso e libera botões."""
        self._progresso.stop()
        self._frame_progresso.pack_forget()
        for btn in (self._btn_processar, self._btn_enviar,
                    self._btn_imprimir, self._btn_demo):
            btn.configure(state="normal")
        self._operacao_em_curso = False

    def _executar_em_thread(self, fn, cb_sucesso, cb_erro) -> None:
        """Roda fn() em thread daemon; resultado volta via .after(0, ...)."""
        def worker():
            try:
                resultado = fn()
                self.after(0, cb_sucesso, resultado)
            except Exception as e:
                logger.error(str(e), exc_info=True)
                self.after(0, cb_erro, str(e))
        threading.Thread(target=worker, daemon=True).start()

    # ── Processar Pasta ───────────────────────────────────────────────────────

    def _cmd_processar_pasta(self) -> None:
        """RF-07 — Lê PDFs da pasta A_Pagar/ (ou simula em modo demo)."""
        if self._operacao_em_curso:
            return
        self._iniciar_operacao("Lendo PDFs da pasta A_Pagar…")
        self._executar_em_thread(
            self._worker_processar,
            self._pos_processar,
            lambda e: (self._finalizar_operacao(),
                       self._mostrar_erro(f"Erro ao processar pasta:\n{e}")))

    def _worker_processar(self) -> dict:
        from config.settings import DIR_A_PAGAR, MODO_SIMULACAO
        from core.leitor import listar_pdfs_pendentes, ler_pdf

        if MODO_SIMULACAO:
            return self._simular_leitura()

        pdfs = listar_pdfs_pendentes(DIR_A_PAGAR)
        if not pdfs:
            return {"processados": 0, "revisao": 0, "mensagem": "Nenhum PDF encontrado em dados/A_Pagar/"}

        processados = revisao = 0
        for pdf in pdfs:
            resultado = ler_pdf(pdf)
            if resultado.sucesso:
                db.inserir_conta(resultado.to_dict())
                processados += 1
            else:
                db.inserir_conta(resultado.to_dict())  # entra como REVISAO
                revisao += 1
        return {"processados": processados, "revisao": revisao,
                "mensagem": f"{processados} conta(s) lidas, {revisao} para revisão manual."}

    def _simular_leitura(self) -> dict:
        """Gera contas realistas sem precisar de PDFs físicos."""
        import random
        novos = [
            ("NF_2026_047",  "Materiais de Escritório LTDA",  487.50,  "2026-06-25", "BOLETO"),
            ("NF_2026_048",  "Cloud Hosting Services",       1890.00,  "2026-06-26", "PIX"),
            ("NF_2026_049",  "Transportadora Rápida ME",      320.00,  "2026-06-27", "BOLETO"),
            ("NF_2026_050",  "Software License Corp",        2250.00,  "2026-06-28", "PIX"),
        ]
        time.sleep(1.2)  # simula tempo de leitura
        for id_display, fornecedor, valor, venc, tipo in novos:
            db.inserir_conta({
                "id_display": id_display, "fornecedor": fornecedor,
                "valor": valor, "vencimento": venc, "tipo": tipo,
                "status": "PENDENTE", "arquivo_origem": f"{id_display}.pdf",
                "arquivo_atual": f"{id_display}.pdf", "codigo_pagamento": "DEMO",
            })
        return {"processados": len(novos), "revisao": 0,
                "mensagem": f"{len(novos)} nota(s) fiscal(is) lidas da pasta A_Pagar."}

    def _pos_processar(self, resultado: dict) -> None:
        self._finalizar_operacao()
        self._carregar_contas()
        self._lbl_status.configure(text=f"✓  {resultado['mensagem']}")
        logger.info(f"Processar Pasta concluído: {resultado}")

    # ── Enviar Lote ───────────────────────────────────────────────────────────

    def _cmd_enviar_lote(self) -> None:
        """RF-08 — Envia contas PENDENTES para o banco (real ou mock)."""
        if self._operacao_em_curso:
            return
        pendentes = db.buscar_contas_por_status("PENDENTE")
        if not pendentes:
            _Dialogo(self, titulo="Enviar Lote", tipo="info",
                     mensagem="Não há contas com status PENDENTE para enviar.")
            return
        self._iniciar_operacao(
            f"Enviando {len(pendentes)} conta(s) ao banco{'  [SIMULAÇÃO]' if MODO_SIMULACAO else ''}…")
        self._executar_em_thread(
            self._worker_enviar,
            self._pos_enviar,
            lambda e: (self._finalizar_operacao(),
                       self._mostrar_erro(f"Erro ao enviar lote:\n{e}")))

    def _worker_enviar(self) -> dict:
        from core.banco_api import enviar_lote
        return enviar_lote()

    def _pos_enviar(self, resultado: dict) -> None:
        self._finalizar_operacao()
        self._carregar_contas()
        msg = (f"✓  Lote enviado — "
               f"{resultado['enviadas']} enviada(s)  |  "
               f"{resultado['falhas']} falha(s)  |  "
               f"{resultado.get('puladas', 0)} pulada(s)")
        self._lbl_status.configure(text=msg)
        logger.info(f"Enviar Lote concluído: {resultado}")

    # ── Baixar e Imprimir ─────────────────────────────────────────────────────

    def _cmd_baixar_imprimir(self) -> None:
        """RF-09 — Confirma pagamentos, baixa comprovantes e monta lote de impressão."""
        if self._operacao_em_curso:
            return
        self._iniciar_operacao("Confirmando pagamentos e baixando comprovantes…")
        self._executar_em_thread(
            self._worker_imprimir,
            self._pos_imprimir,
            lambda e: (self._finalizar_operacao(),
                       self._mostrar_erro(f"Erro ao processar comprovantes:\n{e}")))

    def _worker_imprimir(self) -> dict:
        from core.comprovantes import fluxo_completo
        return fluxo_completo()

    def _pos_imprimir(self, resultado: dict) -> None:
        self._finalizar_operacao()
        self._carregar_contas()
        pagas    = resultado.get("pagas_novas", 0)
        baixados = resultado.get("baixados", 0)
        arquivo  = resultado.get("arquivo")
        impresso = resultado.get("impresso", False)

        if arquivo:
            msg = (f"✓  {pagas} nova(s) confirmada(s) como PAGA  |  "
                   f"{baixados} comprovante(s) baixado(s)  |  "
                   f"{'Enviado para impressora' if impresso else 'PDF pronto para impressão'}")
        else:
            msg = "Nenhuma conta pronta para gerar lote de impressão."
        self._lbl_status.configure(text=msg)
        logger.info(f"Baixar e Imprimir concluído: {resultado}")

    # ── Demo Completo ─────────────────────────────────────────────────────────

    def _cmd_demo_completo(self) -> None:
        """
        Demonstração completa do fluxo AutoPag em ~12 segundos.
        Roda em thread separada: não trava a interface em nenhum momento.
        """
        if self._operacao_em_curso:
            return
        self._iniciar_operacao("🎬  Demo em execução — acompanhe as mudanças na tabela…")
        threading.Thread(target=self._worker_demo, daemon=True).start()

    def _worker_demo(self) -> None:
        """Sequência completa do demo com pauses para visualização."""
        try:
            # Etapa 1: limpa dados demo anteriores e insere novos PDFs simulados
            self.after(0, self._lbl_progresso.configure,
                       {"text": "🎬  Passo 1/4 — Lendo PDFs da pasta A_Pagar…"})
            result_leitura = self._simular_leitura()
            self.after(0, self._carregar_contas)
            self.after(0, self._lbl_status.configure,
                       {"text": f"📂  {result_leitura['processados']} nota(s) lidas — status PENDENTE"})
            time.sleep(2.5)

            # Etapa 2: envia ao banco
            self.after(0, self._lbl_progresso.configure,
                       {"text": "🎬  Passo 2/4 — Enviando lote ao banco [SIMULAÇÃO]…"})
            from core.banco_api import enviar_lote
            result_envio = enviar_lote()
            self.after(0, self._carregar_contas)
            self.after(0, self._lbl_status.configure,
                       {"text": f"📤  {result_envio['enviadas']} conta(s) enviadas — status ENVIADO"})
            time.sleep(3.0)

            # Etapa 3: confirma pagamentos (mock amadurece após ~20s,
            # mas forçamos PAGO aqui para o demo)
            self.after(0, self._lbl_progresso.configure,
                       {"text": "🎬  Passo 3/4 — Aguardando confirmação de pagamento…"})
            enviadas = db.buscar_contas_por_status("ENVIADO")
            for conta in enviadas:
                db.atualizar_conta(conta["id"], {
                    "status": "PAGO",
                    "data_pagamento": time.strftime("%Y-%m-%d %H:%M:%S"),
                })
            self.after(0, self._carregar_contas)
            self.after(0, self._lbl_status.configure,
                       {"text": f"✅  {len(enviadas)} pagamento(s) confirmado(s) — status PAGO"})
            time.sleep(2.5)

            # Etapa 4: baixa comprovantes mock
            self.after(0, self._lbl_progresso.configure,
                       {"text": "🎬  Passo 4/4 — Baixando comprovantes e gerando lote de impressão…"})
            from core.comprovantes import baixar_comprovantes, merge_intercalado
            baixados = baixar_comprovantes()
            arquivo  = merge_intercalado()
            self.after(0, self._carregar_contas)

            resumo = (f"🎬  Demo concluído!  "
                      f"PDF lido → Enviado → Pago → "
                      f"{baixados} comprovante(s) → "
                      f"{'PDF de impressão gerado' if arquivo else 'sem arquivo de boleto físico'}")
            self.after(0, self._lbl_status.configure, {"text": resumo})

        except Exception as e:
            logger.error(f"Demo falhou: {e}", exc_info=True)
            self.after(0, self._lbl_status.configure,
                       {"text": f"❌  Demo interrompido: {e}"})
        finally:
            self.after(0, self._finalizar_operacao)

    # ── Utilitários ───────────────────────────────────────────────────────────

    def _mostrar_erro(self, mensagem: str) -> None:
        _Dialogo(self, titulo="Erro", tipo="erro", mensagem=mensagem)


# ─────────────────────────────────────────────────────────────────────────────


class _Dialogo(ctk.CTkToplevel):
    """Janela modal simples para info e erro."""

    def __init__(self, parent, titulo: str, mensagem: str, tipo: str = "info") -> None:
        super().__init__(parent)
        self.title(titulo)
        self.resizable(False, False)
        self.configure(fg_color=COR_SUPERFICIE_ELEVADA)
        self.grab_set()
        self.lift()
        self.focus()

        px = parent.winfo_x() + parent.winfo_width()  // 2
        py = parent.winfo_y() + parent.winfo_height() // 2
        self.geometry(f"420x230+{px - 210}+{py - 115}")

        icone   = "⚠️" if tipo == "erro" else "ℹ️"
        cor_btn = "#B91C1C" if tipo == "erro" else COR_ACCENT
        cor_hov = "#991B1B" if tipo == "erro" else COR_ACCENT_HOVER

        ctk.CTkLabel(self, text=icone, font=ctk.CTkFont(size=30)).pack(pady=(22, 6))
        ctk.CTkLabel(self, text=titulo,
                     font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
                     text_color=COR_TEXTO).pack()
        ctk.CTkLabel(self, text=mensagem,
                     font=ctk.CTkFont(family="Segoe UI", size=12),
                     text_color=COR_TEXTO_SECUNDARIO,
                     wraplength=370, justify="center").pack(padx=20, pady=10)
        ctk.CTkButton(self, text="OK", width=100, height=34,
                      fg_color=cor_btn, hover_color=cor_hov,
                      corner_radius=8, command=self.destroy).pack(pady=(0, 18))