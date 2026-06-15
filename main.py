# -*- coding: utf-8 -*-
"""
AutoPag — Ponto de entrada da aplicação.

Sequência de inicialização:
  1. Adiciona raiz ao PYTHONPATH
  2. Cria estrutura de diretórios (idempotente)
  3. Cria/migra banco SQLite
  4. Popula dados de demonstração (se banco vazio)
  5. Configura tema CustomTkinter
  6. Abre janela principal
"""
import sys
from pathlib import Path

# Garante importações corretas a partir de qualquer diretório de trabalho
sys.path.insert(0, str(Path(__file__).resolve().parent))

import customtkinter as ctk
from config.settings import APP_TEMA, APP_COR, BASE_DIR
from core.utils import criar_diretorios
from core.database import inicializar_banco, popular_dados_demo
from core.logger import logger
from gui.app import JanelaPrincipal


def main() -> None:
    logger.info("═══════════════════════════════")
    logger.info("  AutoPag iniciando            ")
    logger.info("═══════════════════════════════")

    criar_diretorios(BASE_DIR)
    logger.info("Diretórios verificados.")

    inicializar_banco()
    logger.info("Banco de dados pronto.")

    popular_dados_demo()

    ctk.set_appearance_mode(APP_TEMA)
    ctk.set_default_color_theme(APP_COR)

    app = JanelaPrincipal()
    logger.info("Janela principal aberta. Aguardando interação.")
    app.mainloop()

    logger.info("AutoPag encerrado.")


if __name__ == "__main__":
    main()
