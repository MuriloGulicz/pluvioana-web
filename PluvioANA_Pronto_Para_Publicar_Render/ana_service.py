"""Integração com os serviços legados da ANA (sem dependências externas).

HidroSerieHistorica (tipoDados=2) traz precipitação *diária* em Chuva01..31.
DadosHidrometeorologicos é opcional: por documentação retorna níveis/vazões,
não devendo ser confundido com medição de chuva.
"""
from __future__ import annotations

import calendar
import re
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta, timezone

HOSTS = (
    "https://telemetriaws1.ana.gov.br/ServiceANA.asmx",
    "https://www.ana.gov.br/telemetria1ws/ServiceANA.asmx",
)
MAX_RESPONSE_BYTES = 30 * 1024 * 1024
TIMEOUT_SECONDS = 22
MAX_DAYS = 365 * 3 + 1


def _hoje():
    """Dia corrente no Brasil (UTC−03), independente do fuso da hospedagem."""
    return datetime.now(timezone(timedelta(hours=-3))).date()


class ConsultaErro(Exception):
    """Erro de validação, conexão ou formato da API."""


def _tag(tag):
    return tag.rsplit("}", 1)[-1].split(":")[-1].lower()


def _numero(texto):
    """Valor ausente/dúvida não equivale a chuva de 0 mm."""
    if texto is None:
        return None
    valor = str(texto).strip().replace(" ", "")
    if valor.lower() in ("", "null", "none", "nan", "-", "--"):
        return None
    if "," in valor:
        valor = valor.replace(".", "").replace(",", ".")
    try:
        numero = float(valor)
        if 0 <= numero < float("inf"):
            return round(numero, 4)
    except ValueError:
        pass
    return None


def _datahora(texto):
    if not texto:
        return None
    texto = texto.strip()
    if texto.endswith("Z"):
        texto = texto[:-1]
    try:
        return datetime.fromisoformat(texto).replace(tzinfo=None)
    except ValueError:
        pass
    for formato in ("%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M", "%d/%m/%Y",
                    "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(texto, formato)
        except ValueError:
            continue
    return None


def _linhas_xml(xml_bytes):
    """Retorna dicionários de filhos XML, inclusive em payload SOAP aninhado."""
    def coletar(conteudo, profundidade=0):
        if profundidade > 2:
            return []
        try:
            root = ET.fromstring(conteudo)
        except ET.ParseError as exc:
            raise ConsultaErro("A ANA retornou uma resposta inválida (não é XML).") from exc
        for ele in root.iter():
            if _tag(ele.tag) == "fault":
                raise ConsultaErro("Erro retornado pelo serviço ANA: " +
                                   " ".join(ele.itertext()).strip()[:240])
        linhas = []
        for ele in root.iter():
            filhos = list(ele)
            if not filhos:
                continue
            campos = {_tag(f.tag): (f.text or "").strip() for f in filhos if not list(f)}
            if "datahora" in campos or "data" in campos:
                linhas.append(campos)
        if not linhas:
            for ele in root.iter():
                texto = (ele.text or "").strip()
                if texto.startswith("<") and len(texto) < MAX_RESPONSE_BYTES:
                    try:
                        linhas.extend(coletar(texto, profundidade + 1))
                    except ConsultaErro:
                        continue
        return linhas
    return coletar(xml_bytes)


def interpretar_historico(xml_bytes, estacao, inicio, fim):
    """Desdobra os dados *mensais* Chuva01..Chuva31 em leituras *diárias*.

    A hora registrada em DataHora da linha mensal NÃO é a hora da chuva diária.
    Por isso 'hora' fica nula: não se deve inventar um horário.
    """
    saida = []
    for linha in _linhas_xml(xml_bytes):
        momento = _datahora(linha.get("datahora") or linha.get("data"))
        if not momento or not any(re.fullmatch(r"chuva\d{2}", k) for k in linha):
            continue
        ano, mes = momento.year, momento.month
        quantidade_dias = calendar.monthrange(ano, mes)[1]
        codigo = linha.get("estacaocodigo") or linha.get("codestacao") or estacao
        nivel = linha.get("nivelconsistencia") or None
        for dia in range(1, quantidade_dias + 1):
            chave = f"chuva{dia:02d}"
            if chave not in linha:
                continue
            data_dia = date(ano, mes, dia)
            if not inicio <= data_dia <= fim:
                continue
            saida.append({
                "estacao": codigo,
                "data": data_dia.isoformat(),
                "hora": None,
                "chuva_mm": _numero(linha[chave]),
                "consistencia": nivel,
            })
    return saida


def interpretar_telemetria(xml_bytes, estacao, inicio, fim):
    """Só devolve registros que possuem *campo Chuva*, se o serviço fornecer."""
    saida = []
    for linha in _linhas_xml(xml_bytes):
        if "chuva" not in linha:
            continue
        momento = _datahora(linha.get("datahora") or linha.get("data"))
        if momento is None or not inicio <= momento.date() <= fim:
            continue
        saida.append({
            "estacao": linha.get("codestacao") or linha.get("estacaocodigo") or estacao,
            "data": momento.date().isoformat(),
            "hora": momento.strftime("%H:%M:%S"),
            "chuva_mm": _numero(linha["chuva"]),
            "consistencia": None,
        })
    return saida


def validar_filtros(codigo, inicio_texto, fim_texto, modo="historico", consistencia="1"):
    codigo = str(codigo or "").strip()
    if not re.fullmatch(r"\d{1,12}", codigo):
        raise ConsultaErro("O código da estação deve conter apenas números (até 12 dígitos).")
    try:
        inicio = date.fromisoformat(str(inicio_texto))
        fim = date.fromisoformat(str(fim_texto))
    except (ValueError, TypeError) as exc:
        raise ConsultaErro("Informe datas válidas nos campos de data inicial e final.") from exc
    if inicio > fim:
        raise ConsultaErro("A data inicial não pode ser posterior à data final.")
    if fim > _hoje():
        raise ConsultaErro("A data final não pode ser posterior a hoje: só existem leituras passadas.")
    if (fim - inicio).days >= MAX_DAYS:
        raise ConsultaErro("O período máximo por consulta é de três anos. Divida a pesquisa em períodos menores.")
    if modo not in ("historico", "telemetria"):
        raise ConsultaErro("A fonte selecionada não é válida.")
    if str(consistencia) not in ("1", "2"):
        raise ConsultaErro("Selecione dados brutos ou consistidos.")
    return codigo, inicio, fim, modo, str(consistencia)


def _pedir_api(operacao, parametros):
    falhas = []
    for base in HOSTS:
        url = f"{base}/{operacao}?{urllib.parse.urlencode(parametros)}"
        requisicao = urllib.request.Request(url, headers={
            "User-Agent": "PluvioANA-Web/2.0 (pesquisa educacional)",
            "Accept": "application/xml,text/xml,*/*",
        })
        try:
            with urllib.request.urlopen(requisicao, timeout=TIMEOUT_SECONDS) as resposta:
                resultado = resposta.read(MAX_RESPONSE_BYTES + 1)
            if len(resultado) > MAX_RESPONSE_BYTES:
                raise ConsultaErro("A resposta ultrapassou 30 MB. Reduza o período consultado.")
            # Diferencia acesso válido com XML de resposta vazia/HTML.
            _linhas_xml(resultado)
            return resultado, base
        except (urllib.error.URLError, OSError, ConsultaErro) as exc:
            falhas.append(f"{urllib.parse.urlsplit(base).hostname}: {str(exc)[:100]}")
    raise ConsultaErro("Não foi possível consultar o serviço da ANA. A API antiga pode estar "
                       "temporariamente indisponível ou descontinuada. " + " / ".join(falhas))


def _periodos(inicio, fim, modo):
    """Histórico da ANA é indexado por MÊS, mesmo com valores por dia.

    Consultar a partir do dia 15 pode omitir a linha do dia 1 que contém
    Chuva01...Chuva31. Busca por meses completos e depois filtra os dias
    exatamente pelo intervalo pedido. Divide em blocos de até três meses.
    """
    if modo == "telemetria":
        atual = inicio
        while atual <= fim:
            ultima = min(atual + timedelta(days=29), fim)
            yield atual, ultima
            atual = ultima + timedelta(days=1)
        return

    primeiro_mes = date(inicio.year, inicio.month, 1)
    ultimo_mes = date(fim.year, fim.month, 1)
    atual = primeiro_mes
    while atual <= ultimo_mes:
        ano_final = atual.year + (atual.month - 1 + 2) // 12
        mes_final = (atual.month - 1 + 2) % 12 + 1
        mes_ultima = min(date(ano_final, mes_final, 1), ultimo_mes)
        data_fim = date(mes_ultima.year, mes_ultima.month,
                        calendar.monthrange(mes_ultima.year, mes_ultima.month)[1])
        yield atual, min(data_fim, _hoje())
        ano_seguinte = mes_ultima.year + (mes_ultima.month // 12)
        mes_seguinte = mes_ultima.month % 12 + 1
        atual = date(ano_seguinte, mes_seguinte, 1)


def consultar(codigo, inicio, fim, modo="historico", consistencia="1"):
    """Consulta somente dados reais; sem fallback silencioso a conteúdo fictício."""
    resultados = []
    base_utilizada = ""
    for ini, end in _periodos(inicio, fim, modo):
        parametros = {
            "codEstacao": codigo,
            "dataInicio": ini.strftime("%d/%m/%Y"),
            "dataFim": end.strftime("%d/%m/%Y"),
        }
        if modo == "historico":
            parametros.update({"tipoDados": "2", "nivelConsistencia": consistencia})
            nome_operacao = "HidroSerieHistorica"
        else:
            nome_operacao = "DadosHidrometeorologicos"
        xml_bytes, base_utilizada = _pedir_api(nome_operacao, parametros)
        if modo == "historico":
            resultados.extend(interpretar_historico(xml_bytes, codigo, inicio, fim))
        else:
            resultados.extend(interpretar_telemetria(xml_bytes, codigo, inicio, fim))

    # A ANA pode devolver dias/meses repetidos: evita contagem e soma em duplicidade.
    # Prioriza valor válido e série consistida ao resolver duplicações.
    unicos = {}
    for registro in resultados:
        chave = (registro["estacao"], registro["data"], registro["hora"])
        anterior = unicos.get(chave)
        if anterior is None or (
            (registro["chuva_mm"] is not None, registro["consistencia"] == "2") >
            (anterior["chuva_mm"] is not None, anterior["consistencia"] == "2")
        ):
            unicos[chave] = registro
    registros = sorted(unicos.values(), key=lambda r: (r["data"], r["hora"] or "", r["estacao"]))
    total = sum((r["chuva_mm"] or 0) for r in registros)
    return {
        "estacao": codigo,
        "inicio": inicio.isoformat(),
        "fim": fim.isoformat(),
        "modo": modo,
        "fonte": "ANA · HidroSerieHistorica (chuva diária)" if modo == "historico" else
                 "ANA · DadosHidrometeorologicos (telemetria)",
        "url_origem": base_utilizada + ("/HidroSerieHistorica" if modo == "historico" else "/DadosHidrometeorologicos"),
        "reais": True,
        "registros": registros,
        "resumo": {
            "total_registros": len(registros),
            "leituras_validas": sum(r["chuva_mm"] is not None for r in registros),
            "sem_leitura": sum(r["chuva_mm"] is None for r in registros),
            "maior_chuva_mm": max((r["chuva_mm"] for r in registros if r["chuva_mm"] is not None), default=None),
            "chuva_total_mm": round(total, 4),
            "dias_com_chuva": len({r["data"] for r in registros if r["chuva_mm"] is not None and r["chuva_mm"] > 0}),
        },
    }
