"""Testes da entrada web de produção (sem consultar a ANA)."""
import io
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import app


class TestarWSGI(unittest.TestCase):
    def invoke(self, method, path, payload=None):
        body = b'' if payload is None else json.dumps(payload).encode('utf-8')
        environ = {
            'REQUEST_METHOD': method,
            'PATH_INFO': path,
            'CONTENT_LENGTH': str(len(body)),
            'wsgi.input': io.BytesIO(body),
        }
        response = {}
        def start_response(status, headers):
            response['status'] = status
            response['headers'] = dict(headers)
        response['body'] = b''.join(app(environ, start_response))
        return response

    def test_public_pages(self):
        for path in ('/', '/style.css', '/app.js', '/sw.js', '/icons/icon-192.png'):
            response = self.invoke('GET', path)
            self.assertTrue(response['status'].startswith('200'), path)
            self.assertTrue(response['body'])
            self.assertEqual(response['headers']['X-Content-Type-Options'], 'nosniff')

    def test_health(self):
        response = self.invoke('GET', '/api/health')
        self.assertEqual(json.loads(response['body'])['ok'], True)

    def test_invalid_dates(self):
        response = self.invoke('POST', '/api/consultar', {
            'estacao': '1234', 'inicio': '2024-05-30', 'fim': '2024-05-01',
        })
        self.assertTrue(response['status'].startswith('422'))

    def test_valid_request_uses_api_service(self):
        example = {'registros': [{'estacao': '1234', 'data': '2024-05-01', 'hora': None, 'chuva_mm': 13.1}]}
        with patch('app.consultar', return_value=example) as mock:
            response = self.invoke('POST', '/api/consultar', {
                'estacao': '1234', 'inicio': '2024-05-01', 'fim': '2024-05-01',
            })
        self.assertTrue(response['status'].startswith('200'))
        self.assertEqual(json.loads(response['body'])['registros'][0]['chuva_mm'], 13.1)
        self.assertEqual(mock.call_count, 1)


if __name__ == '__main__':
    unittest.main()
