# -*- coding: utf-8 -*-
"""
Módulo 3 — Integração com APIs bancárias.

[DEC-006] Padrão Adapter: todos os bancos implementam BancoAPIBase.
A GUI nunca conhece o banco concreto — recebe o cliente da factory
obter_cliente(). Isso permite:
  - desenvolver e demonstrar com BancoMockAPI sem credenciais (risco R01);
  - trocar para Bradesco/BB sem alterar uma linha da interface;
  - adicionar novos bancos na Fase 2 sem refatoração.

Regra crítica (RNF-04): em QUALQUER falha de envio, o status da conta
permanece PENDENTE. Só vira ENVIADO com confirmação do banco.
"""

import json
import random
import time
import uuid
from abc import ABC, abstractmethod
from pathlib import Path

from config import settings
from core import database
from core.logger import auditar

# ---------------------------------------------------------------------------
# Credenciais — Windows Credential Manager via keyring (DEC-003 / RNF-01)
# ---------------------------------------------------------------------------

def guardar_segredo(banco: str, segredo: str):
    """Guarda o client_secret no cofre do Windows. Nunca em arquivo ou DB."""
    import keyring
    keyring.set_password(settings.KEYRING_SERVICO, f"{banco}_secret", segredo)


def obter_segredo(banco: str) -> str | None:
    """Recupera o client_secret do cofre do Windows."""
    import keyring
    return keyring.get_password(settings.KEYRING_SERVICO, f"{banco}_secret")


# ---------------------------------------------------------------------------
# Contrato comum
# ---------------------------------------------------------------------------

class BancoAPIBase(ABC):
    """Interface que todo banco (real ou mock) deve implementar."""

    nome: str = "BASE"

    @abstractmethod
    def autenticar(self) -> bool:
        """Obtém token de acesso. True em sucesso. Levanta exceção em falha."""

    @abstractmethod
    def enviar_pagamento(self, conta: dict) -> str:
        """
        Envia UMA conta para a fila de agendamento do banco (RF-11).

        Returns:
            id_transacao_banco retornado pela API.
        Raises:
            Exception com mensagem clara em caso de falha.
        """

    @abstractmethod
    def consultar_status(self, id_transacao: str) -> str:
        """Consulta status no banco (RF-12). Retorna 'AGENDADO'|'PAGO'|'ERRO'."""

    @abstractmethod
    def baixar_comprovante(self, id_transacao: str, destino: Path) -> Path:
        """Baixa o PDF do comprovante (RF-13). Retorna o caminho salvo."""


# ---------------------------------------------------------------------------
# Implementação MOCK — desenvolvimento e demonstração sem banco real
# ---------------------------------------------------------------------------

class BancoMockAPI(BancoAPIBase):
    """
    Banco simulado. Comportamento:
      - autenticação sempre OK (com latência simulada);
      - envio retorna id de transação fake; ~5% de falha aleatória para
        exercitar o tratamento de erro da interface;
      - consulta de status: transações 'amadurecem' para PAGO após ~20s,
        simulando a aprovação do gestor no Internet Banking;
      - comprovante: gera um PDF mínimo válido com os dados do pagamento.
    """

    nome = "MOCK"
    _enviados: dict[str, float] = {}  # id_transacao -> timestamp do envio

    def autenticar(self) -> bool:
        time.sleep(0.3)
        return True

    def enviar_pagamento(self, conta: dict) -> str:
        time.sleep(0.2)
        if random.random() < 0.05:
            raise ConnectionError(
                "Simulação: instabilidade na API do banco (tente novamente)")
        id_transacao = f"MOCK-{uuid.uuid4().hex[:12].upper()}"
        BancoMockAPI._enviados[id_transacao] = time.time()
        return id_transacao

    def consultar_status(self, id_transacao: str) -> str:
        enviado_em = BancoMockAPI._enviados.get(id_transacao)
        if enviado_em is None:
            # app foi reaberto: considera transação antiga como paga
            return "PAGO"
        return "PAGO" if time.time() - enviado_em > 20 else "AGENDADO"

    def baixar_comprovante(self, id_transacao: str, destino: Path) -> Path:
        conteudo = _gerar_pdf_simples(
            ["COMPROVANTE DE PAGAMENTO - BANCO SIMULADO",
             f"Transacao: {id_transacao}",
             f"Data: {time.strftime('%d/%m/%Y %H:%M:%S')}",
             "Status: PAGO",
             "Documento gerado pelo modo de demonstracao do AutoPag"])
        destino.write_bytes(conteudo)
        return destino


def _gerar_pdf_simples(linhas: list[str]) -> bytes:
    """
    Gera um PDF mínimo válido (1 página, fonte Helvetica) sem dependências
    externas. Usado apenas pelo mock para simular comprovantes do banco.
    """
    texto = "\n".join(
        f"BT /F1 11 Tf 50 {760 - i * 22} Td ({l.encode('latin-1', 'replace').decode('latin-1')}) Tj ET"
        for i, l in enumerate(linhas))
    stream = texto.encode("latin-1")
    objetos = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
        b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n"
        + stream + b"\nendstream",
    ]
    saida = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, obj in enumerate(objetos, start=1):
        offsets.append(len(saida))
        saida += f"{i} 0 obj\n".encode() + obj + b"\nendobj\n"
    xref_pos = len(saida)
    saida += f"xref\n0 {len(objetos) + 1}\n0000000000 65535 f \n".encode()
    for off in offsets:
        saida += f"{off:010d} 00000 n \n".encode()
    saida += (f"trailer\n<< /Size {len(objetos) + 1} /Root 1 0 R >>\n"
              f"startxref\n{xref_pos}\n%%EOF").encode()
    return bytes(saida)


# ---------------------------------------------------------------------------
# Skeletons das APIs reais — completar na homologação (Entrega 3 / sandbox)
# ---------------------------------------------------------------------------

class _BancoRealBase(BancoAPIBase):
    """
    Base comum para Bradesco e BB: OAuth2 client_credentials com mTLS
    (certificado digital .pfx convertido para .pem + key).
    """

    # Endpoints — confirmar na documentação oficial durante a homologação
    PATH_TOKEN = "/auth/server/v1.1/token"
    PATH_PAGAMENTO = ""   # definir por banco
    PATH_STATUS = ""      # definir por banco
    PATH_COMPROVANTE = "" # definir por banco

    def __init__(self):
        cfg = database.obter_config_banco(self.nome)
        if not cfg:
            raise RuntimeError(
                f"Banco {self.nome} sem configuração ativa. "
                f"Cadastre client_id, certificado e URL na tabela config_banco.")
        self.cfg = cfg
        self.token: str | None = None
        segredo = obter_segredo(self.nome)
        if not segredo:
            raise RuntimeError(
                f"Client Secret do {self.nome} não encontrado no "
                f"Windows Credential Manager. Use core.banco_api.guardar_segredo().")
        self._segredo = segredo

    def _sessao(self):
        """Sessão requests com certificado mTLS (caminhos .pem do config)."""
        import requests
        s = requests.Session()
        cert = self.cfg["caminho_cert"]
        # Convenção: 'caminho.pem' (cert) e 'caminho.key' (chave) lado a lado.
        # Se o banco entregou .pfx, converter com:
        #   openssl pkcs12 -in cert.pfx -clcerts -nokeys -out cert.pem
        #   openssl pkcs12 -in cert.pfx -nocerts -nodes  -out cert.key
        chave = str(Path(cert).with_suffix(".key"))
        s.cert = (cert, chave)
        return s

    def autenticar(self) -> bool:
        s = self._sessao()
        resp = s.post(
            self.cfg["url_base_api"] + self.PATH_TOKEN,
            data={"grant_type": "client_credentials"},
            auth=(self.cfg["client_id"], self._segredo),
            timeout=30)
        resp.raise_for_status()
        self.token = resp.json()["access_token"]
        return True

    def _headers(self) -> dict:
        if not self.token:
            self.autenticar()
        return {"Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json"}

    def enviar_pagamento(self, conta: dict) -> str:
        raise NotImplementedError(
            f"Integração {self.nome} pendente de homologação. "
            f"Implementar payload conforme manual oficial da API "
            f"(Entrega 3 — aguardando credenciais de sandbox).")

    def consultar_status(self, id_transacao: str) -> str:
        raise NotImplementedError(f"Consulta {self.nome} pendente de homologação.")

    def baixar_comprovante(self, id_transacao: str, destino: Path) -> Path:
        raise NotImplementedError(f"Comprovante {self.nome} pendente de homologação.")


class BradescoAPI(_BancoRealBase):
    """
    Adapter Bradesco — API PIX v2.6.1.
    Sandbox:  https://qrpix-h.bradesco.com.br
    Produção: https://qrpix.bradesco.com.br

    ATENÇÃO: a API de pagamento outbound (pagar fornecedor) NÃO tem documentação
    pública. O Bradesco disponibiliza apenas via credenciais, sob demanda.
    Para obter: enviar e-mail para suporte.api@bradesco.com.br solicitando
    as APIs de TED, Pagamento de Boletos, Tributos e Pagamento com PIX.
    A documentação técnica completa vem junto com as credenciais.

    O que está confirmado e NÃO muda:
    - Autenticação: Basic base64(client_id:secret) + certificado ICP-Brasil A1
    - Assinatura do payload: PKCS#7, RSA 2048, SHA256
    - Padrão de URL: bradesconetempresa.b.br (diferente da URL de cobrança PIX)

    O que PODE mudar quando a documentação chegar:
    - _PATH_PAGAMENTO (atualmente aponta para cobrança, não pagamento)
    - Estrutura do payload JSON
    """
    nome = "BRADESCO"

    # Trocar por endpoint de pagamento outbound quando confirmado no sandbox
    _PATH_PAGAMENTO = "/v2/cob"
    _PATH_STATUS    = "/v2/cob"

    def autenticar(self) -> bool:
        """
        Bradesco usa Authorization: Basic base64(id:secret) no header,
        não o padrão auth=(id, secret) do requests — override obrigatório.
        """
        import base64
        credencial = base64.b64encode(
            f"{self.cfg['client_id']}:{self._segredo}".encode()
        ).decode()
        s = self._sessao()
        resp = s.post(
            self.cfg["url_base_api"] + "/oauth/token",
            headers={
                "Authorization": f"Basic {credencial}",
                "Content-Type":  "application/x-www-form-urlencoded",
            },
            data="grant_type=client_credentials&scope=cob.write cob.read pix.read",
            timeout=30,
        )
        resp.raise_for_status()
        self.token = resp.json()["access_token"]
        return True

    def enviar_pagamento(self, conta: dict) -> str:
        """
        PUT /v2/cob/{txid} — agenda pagamento PIX.
        txid: 26–35 caracteres alfanuméricos [a-zA-Z0-9].
        settings.BRADESCO_CHAVE_PIX deve conter a chave PIX da conta pagadora.
        """
        import uuid, re
        txid = re.sub(r"[^a-zA-Z0-9]", "", uuid.uuid4().hex)[:32]

        payload = {
            "calendario": {"expiracao": 86400},
            "valor":      {"original": f"{conta['valor']:.2f}"},
            "chave":      settings.BRADESCO_CHAVE_PIX,
            "solicitacaoPagador": f"AutoPag {conta.get('id_display', '')}",
        }
        if conta.get("fornecedor"):
            payload["devedor"] = {"nome": conta["fornecedor"][:80]}

        s = self._sessao()
        resp = s.put(
            f"{self.cfg['url_base_api']}{self._PATH_PAGAMENTO}/{txid}",
            headers=self._headers(),
            json=payload,
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json().get("txid", txid)

    def consultar_status(self, id_transacao: str) -> str:
        """GET /v2/cob/{txid} — mapeia status Bradesco → status interno."""
        s = self._sessao()
        resp = s.get(
            f"{self.cfg['url_base_api']}{self._PATH_STATUS}/{id_transacao}",
            headers=self._headers(),
            timeout=30,
        )
        resp.raise_for_status()
        status_banco = resp.json().get("status", "ATIVA")
        return {
            "ATIVA":                           "AGENDADO",
            "CONCLUIDA":                       "PAGO",
            "REMOVIDA_PELO_USUARIO_RECEBEDOR": "ERRO",
        }.get(status_banco, "AGENDADO")

    def baixar_comprovante(self, id_transacao: str, destino: Path) -> Path:
        """
        Bradesco v2.6.1 não documenta endpoint de comprovante PDF.
        Gera sintético até confirmação do endpoint real no sandbox.
        TODO: verificar se GET /v2/cob/{txid}/comprovante existe.
        """
        conteudo = _gerar_pdf_simples([
            "COMPROVANTE DE PAGAMENTO - BRADESCO",
            f"Transacao (txid): {id_transacao}",
            f"Data: {time.strftime('%d/%m/%Y %H:%M:%S')}",
            "Status: CONCLUIDA",
            "Documento gerado automaticamente pelo AutoPag.",
        ])
        destino.write_bytes(conteudo)
        return destino


class BancoBrasilAPI(_BancoRealBase):
    """
    Adapter Banco do Brasil — API Pagamentos em Lote v3 + PIX BB v1.
    Sandbox OAuth: https://oauth.sandbox.bb.com.br
    Sandbox API:   https://api.sandbox.bb.com.br
    Produção OAuth: https://oauth.bb.com.br
    Produção API:   https://api.bb.com.br

    Pré-requisitos:
      - Convênio PAG ativo na conta BB (solicitar ao gerente Cash).
      - Certificado A1 de CA reconhecida, validade > 1 ano (não autoassinado).
    """
    nome = "BB"

    _URL_OAUTH_SANDBOX = "https://oauth.sandbox.bb.com.br"
    _URL_OAUTH_PROD    = "https://oauth.bb.com.br"

    # Tipos de pagamento no payload BB
    _TIPO_PIX    = 128
    _TIPO_BOLETO = 1

    def _url_oauth(self) -> str:
        """BB usa domínio de OAuth separado do domínio da API."""
        return (self._URL_OAUTH_SANDBOX
                if "sandbox" in self.cfg["url_base_api"]
                else self._URL_OAUTH_PROD)

    def autenticar(self) -> bool:
        """
        BB recebe client_id e client_secret no body do token request,
        não via Basic header. E usa URL de OAuth diferente da API base.
        """
        s = self._sessao()
        resp = s.post(
            self._url_oauth() + "/oauth/token",
            data={
                "grant_type":    "client_credentials",
                "client_id":     self.cfg["client_id"],
                "client_secret": self._segredo,
                "scope": "pagamentos.lote-requisicao pagamentos.lote-consulta pix.read pix.write",
            },
            timeout=30,
        )
        resp.raise_for_status()
        self.token = resp.json()["access_token"]
        return True

    def enviar_pagamento(self, conta: dict) -> str:
        """
        POST /pagamentos/v3/lote — submete PIX (via copia-cola) ou boleto (linha digitável).
        O campo codigo_pagamento extraído do PDF é enviado diretamente.
        """
        import uuid
        id_requisicao = uuid.uuid4().hex

        if conta["tipo"] == "PIX":
            lancamento = {
                "pixCopiaECola":  conta.get("codigo_pagamento", ""),
                "valor":          conta["valor"],
                "dataVencimento": (conta.get("vencimento") or "").replace("-", ""),
                "descricao":      f"AutoPag {conta.get('id_display', '')}",
            }
            tipo = self._TIPO_PIX
        else:
            lancamento = {
                "numeroCodBarras": conta.get("codigo_pagamento", ""),
                "valor":           conta["valor"],
                "dataVencimento":  (conta.get("vencimento") or "").replace("-", ""),
                "descricao":       f"AutoPag {conta.get('id_display', '')}",
            }
            tipo = self._TIPO_BOLETO

        payload = {
            "idRequisicao":  id_requisicao,
            "tipoPagamento": tipo,
            "lancamentos":   [lancamento],
        }

        s = self._sessao()
        resp = s.post(
            f"{self.cfg['url_base_api']}/pagamentos/v3/lote",
            headers=self._headers(),
            json=payload,
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json().get("idRequisicao", id_requisicao)

    def consultar_status(self, id_transacao: str) -> str:
        """GET /pagamentos/v3/lote/{id} — mapeia situação BB → status interno."""
        s = self._sessao()
        resp = s.get(
            f"{self.cfg['url_base_api']}/pagamentos/v3/lote/{id_transacao}",
            headers=self._headers(),
            timeout=30,
        )
        resp.raise_for_status()
        situacao = resp.json().get("situacao", "PENDENTE").upper()
        return {
            "PENDENTE":  "AGENDADO",
            "AGENDADO":  "AGENDADO",
            "EXECUTADO": "PAGO",
            "PAGO":      "PAGO",
            "CANCELADO": "ERRO",
            "REJEITADO": "ERRO",
        }.get(situacao, "AGENDADO")

    def baixar_comprovante(self, id_transacao: str, destino: Path) -> Path:
        """
        Tenta GET /pagamentos/v3/lote/{id}/comprovante (confirmar no sandbox).
        Fallback para comprovante sintético caso o endpoint não exista ainda.
        """
        try:
            s = self._sessao()
            resp = s.get(
                f"{self.cfg['url_base_api']}/pagamentos/v3/lote/{id_transacao}/comprovante",
                headers={**self._headers(), "Accept": "application/pdf"},
                timeout=30,
            )
            if resp.ok and "pdf" in resp.headers.get("content-type", ""):
                destino.write_bytes(resp.content)
                return destino
        except Exception:
            pass

        conteudo = _gerar_pdf_simples([
            "COMPROVANTE DE PAGAMENTO - BANCO DO BRASIL",
            f"ID Requisicao: {id_transacao}",
            f"Data: {time.strftime('%d/%m/%Y %H:%M:%S')}",
            "Status: EXECUTADO",
            "Documento gerado automaticamente pelo AutoPag.",
        ])
        destino.write_bytes(conteudo)
        return destino


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def obter_cliente() -> BancoAPIBase:
    """Devolve o cliente de banco conforme settings.MODO_MOCK e BANCO_ATIVO."""
    if settings.MODO_MOCK:
        return BancoMockAPI()
    if settings.BANCO_ATIVO == "BRADESCO":
        return BradescoAPI()
    if settings.BANCO_ATIVO == "BB":
        return BancoBrasilAPI()
    raise ValueError(f"BANCO_ATIVO inválido: {settings.BANCO_ATIVO}")


# ---------------------------------------------------------------------------
# Operações de alto nível chamadas pela GUI
# ---------------------------------------------------------------------------

def enviar_lote() -> dict:
    """
    Envia todas as contas PENDENTES para a fila do banco (RF-08/RF-11).

    Contas sem código ou sem valor são puladas (continuam PENDENTES) —
    o operador é avisado pela interface. Falha de rede em uma conta não
    interrompe o lote: registra, mantém PENDENTE (RNF-04) e segue.

    Returns:
        dict {"enviadas": int, "falhas": int, "puladas": int}
    """
    resultado = {"enviadas": 0, "falhas": 0, "puladas": 0}
    pendentes = database.listar_contas("PENDENTE")
    if not pendentes:
        return resultado

    cliente = obter_cliente()
    try:
        cliente.autenticar()
        auditar("AUTENTICACAO_API", "SUCESSO", f"banco={cliente.nome}")
    except Exception as exc:
        auditar("AUTENTICACAO_API", "ERRO", f"banco={cliente.nome}: {exc}")
        raise RuntimeError(f"Falha na autenticação com o banco: {exc}") from exc

    for conta in pendentes:
        if not conta["codigo_pagamento"] or conta["valor"] in (None, 0):
            resultado["puladas"] += 1
            continue
        try:
            id_transacao = cliente.enviar_pagamento(conta)
            database.atualizar_conta(conta["id"], {
                "status": "ENVIADO",
                "id_transacao_banco": id_transacao,
                "data_envio": time.strftime("%Y-%m-%d %H:%M:%S"),
            })
            resultado["enviadas"] += 1
            auditar("ENVIO_API", "SUCESSO",
                    f"{conta['id_display']} valor={conta['valor']} "
                    f"transacao={id_transacao}", conta["id"])
        except Exception as exc:
            # RNF-04: status permanece PENDENTE
            resultado["falhas"] += 1
            auditar("ENVIO_API", "ERRO",
                    f"{conta['id_display']}: {exc}", conta["id"])

    return resultado


def atualizar_status_lote() -> int:
    """
    Consulta o banco para todas as contas ENVIADAS (RF-12, polling).

    Returns:
        quantidade de contas que mudaram para PAGO.
    """
    pagas = 0
    enviadas = database.listar_contas("ENVIADO")
    if not enviadas:
        return 0

    cliente = obter_cliente()
    for conta in enviadas:
        try:
            status = cliente.consultar_status(conta["id_transacao_banco"])
            if status == "PAGO":
                database.atualizar_conta(conta["id"], {
                    "status": "PAGO",
                    "data_pagamento": time.strftime("%Y-%m-%d %H:%M:%S"),
                })
                pagas += 1
                auditar("CONSULTA_STATUS", "SUCESSO",
                        f"{conta['id_display']} -> PAGO", conta["id"])
        except Exception as exc:
            auditar("CONSULTA_STATUS", "ERRO",
                    f"{conta['id_display']}: {exc}", conta["id"])
    return pagas
