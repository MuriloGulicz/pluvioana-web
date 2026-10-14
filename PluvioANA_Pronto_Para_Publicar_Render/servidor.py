"""Servidor web local (biblioteca padrão, nenhum pip install necessário).

Iniciar com: python servidor.py
Abre o navegador e mantém acesso restrito ao próprio computador.
"""
from __future__ import annotations

import argparse
import json
import mimetypes
import os
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from ana_service import ConsultaErro, consultar, validar_filtros

ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
STATIC = ROOT / "static"
ROUTES = {"/": "index.html", "/index.html": "index.html",
          "/style.css": "style.css", "/app.js": "app.js",
          "/manifest.webmanifest": "manifest.webmanifest",
          "/sw.js": "sw.js",
          "/icons/icon-192.png": "icons/icon-192.png",
          "/icons/icon-512.png": "icons/icon-512.png"}


class Handler(BaseHTTPRequestHandler):
    server_version = "PluvioANA/2.0"

    def _headers(self, status, content_type, length):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(length))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.end_headers()

    def _json(self, status, obj):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self._headers(status, "application/json; charset=utf-8", len(body))
        self.wfile.write(body)

    def do_GET(self):
        path = urlsplit(self.path).path
        if path == "/api/health":
            return self._json(200, {"ok": True, "aplicacao": "PluvioANA Web"})
        if path not in ROUTES:
            return self._json(404, {"erro": "Página não encontrada."})
        arquivo = STATIC / ROUTES[path]
        try:
            corpo = arquivo.read_bytes()
            tipo = "application/manifest+json" if path == "/manifest.webmanifest" else (mimetypes.guess_type(str(arquivo))[0] or "application/octet-stream")
            tipo = tipo + "; charset=utf-8" if tipo.startswith(("text/", "application/javascript", "application/manifest")) else tipo
            self._headers(200, tipo, len(corpo))
            self.wfile.write(corpo)
        except OSError:
            self._json(500, {"erro": "Arquivo da interface não encontrado."})

    def do_POST(self):
        if urlsplit(self.path).path != "/api/consultar":
            return self._json(404, {"erro": "Operação não encontrada."})
        try:
            tamanho = int(self.headers.get("Content-Length", "0"))
            if tamanho < 2 or tamanho > 8192:
                raise ConsultaErro("Requisição inválida ou muito grande.")
            payload = json.loads(self.rfile.read(tamanho).decode("utf-8"))
            if not isinstance(payload, dict):
                raise ConsultaErro("A consulta deve conter os filtros em formato JSON.")
            codigo, inicio, fim, modo, consistencia = validar_filtros(
                payload.get("estacao"), payload.get("inicio"), payload.get("fim"),
                payload.get("modo", "historico"), payload.get("consistencia", "1"),
            )
            retorno = consultar(codigo, inicio, fim, modo, consistencia)
            self._json(200, retorno)
        except (ConsultaErro, json.JSONDecodeError, UnicodeDecodeError, ValueError) as exc:
            self._json(422, {"erro": str(exc)})
        except (BrokenPipeError, ConnectionResetError):
            return
        except Exception:
            # Não revela traceback/credenciais internos ao navegador.
            self._json(500, {"erro": "Erro inesperado na consulta. Verifique o terminal do servidor."})


def iniciar(porta=8765, abrir=True, host="127.0.0.1"):
    ThreadingHTTPServer.allow_reuse_address = True
    servidor = ThreadingHTTPServer((host, porta), Handler)
    endereco = f"http://127.0.0.1:{porta}"
    print(f"\nPluvioANA Web pronto: {endereco}\nPara encerrar, feche esta janela.\n", flush=True)
    if abrir:
        threading.Timer(0.8, lambda: webbrowser.open(endereco)).start()
    try:
        servidor.serve_forever(poll_interval=.25)
    except KeyboardInterrupt:
        pass
    finally:
        servidor.server_close()


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description="Servidor local do PluvioANA Web")
    cli.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8765")))
    cli.add_argument("--no-browser", action="store_true")
    cli.add_argument("--host", default=os.environ.get("HOST", "127.0.0.1"),
                     help="127.0.0.1 para uso local (padrão), 0.0.0.0 para rede/deploy")
    args = cli.parse_args()
    iniciar(args.port, not args.no_browser, args.host)
