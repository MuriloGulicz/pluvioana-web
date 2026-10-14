"""Adaptador WSGI do PluvioANA para a Internet (Render + Gunicorn).

Reutiliza ana_service.py e a mesma interface da versão desktop.
Nenhuma API ou leitura de chuva é simulada neste servidor.
"""
from __future__ import annotations

import json
import mimetypes
from pathlib import Path
from urllib.parse import unquote

from ana_service import ConsultaErro, consultar, validar_filtros

STATIC = Path(__file__).resolve().parent / "static"
FILES = {
    "/": "index.html",
    "/index.html": "index.html",
    "/style.css": "style.css",
    "/app.js": "app.js",
    "/manifest.webmanifest": "manifest.webmanifest",
    "/sw.js": "sw.js",
    "/icons/icon-192.png": "icons/icon-192.png",
    "/icons/icon-512.png": "icons/icon-512.png",
}


def respond(start_response, status, body, content_type):
    headers = [
        ("Content-Type", content_type),
        ("Content-Length", str(len(body))),
        ("Cache-Control", "no-store"),
        ("X-Content-Type-Options", "nosniff"),
        ("X-Frame-Options", "DENY"),
        ("Referrer-Policy", "no-referrer"),
    ]
    start_response(status, headers)
    return [body]


def jresponse(start_response, status, info):
    return respond(start_response, status,
                   json.dumps(info, ensure_ascii=False).encode("utf-8"),
                   "application/json; charset=utf-8")


def app(environ, start_response):
    """Aplicação WSGI executada por gunicorn: app:app."""
    method = environ.get("REQUEST_METHOD", "GET")
    path = unquote(environ.get("PATH_INFO", "/"))
    if method == "GET":
        if path == "/api/health":
            return jresponse(start_response, "200 OK", {"ok": True, "aplicacao": "PluvioANA Web"})
        nome = FILES.get(path)
        if not nome:
            return jresponse(start_response, "404 Not Found", {"erro": "Página não encontrada."})
        try:
            data = (STATIC / nome).read_bytes()
        except OSError:
            return jresponse(start_response, "500 Internal Server Error", {"erro": "Interface indisponível."})
        tipo = ("application/manifest+json" if path == "/manifest.webmanifest"
                else (mimetypes.guess_type(nome)[0] or "application/octet-stream"))
        if tipo.startswith("text/") or tipo in ("application/javascript", "application/manifest+json"):
            tipo += "; charset=utf-8"
        return respond(start_response, "200 OK", data, tipo)

    if method == "POST" and path == "/api/consultar":
        try:
            tam = int(environ.get("CONTENT_LENGTH", "0"))
            if not 2 <= tam <= 8192:
                raise ConsultaErro("Requisição inválida ou muito grande.")
            data = json.loads(environ["wsgi.input"].read(tam).decode("utf-8"))
            if not isinstance(data, dict):
                raise ConsultaErro("Os filtros devem estar em formato JSON.")
            codigo, inicio, fim, modo, consistencia = validar_filtros(
                data.get("estacao"), data.get("inicio"), data.get("fim"),
                data.get("modo", "historico"), data.get("consistencia", "1"),
            )
            return jresponse(start_response, "200 OK", consultar(codigo, inicio, fim, modo, consistencia))
        except (ConsultaErro, ValueError, UnicodeError, json.JSONDecodeError) as exc:
            return jresponse(start_response, "422 Unprocessable Entity", {"erro": str(exc)})
        except Exception:
            return jresponse(start_response, "500 Internal Server Error",
                             {"erro": "Erro inesperado no servidor. Tente novamente."})

    return jresponse(start_response, "404 Not Found", {"erro": "Operação não encontrada."})
