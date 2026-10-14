"""Testes sem acesso à ANA: XML e resultado são fixtures de teste."""
import http.client
import json
import sys
import threading
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ana_service import (ConsultaErro, _numero, _periodos, consultar,
                         interpretar_historico, interpretar_telemetria,
                         validar_filtros)
from servidor import Handler, ThreadingHTTPServer

HISTORICO = b'''<?xml version="1.0" encoding="utf-8"?>
<DataTable xmlns="http://MRCS/"><Table><EstacaoCodigo>60478482</EstacaoCodigo>
<DataHora>2024-05-01T00:00:00</DataHora><NivelConsistencia>1</NivelConsistencia>
<Chuva01>12,50</Chuva01><Chuva02>0</Chuva02><Chuva03></Chuva03>
<Chuva15>4.3</Chuva15><Chuva16>2.5</Chuva16><Chuva20>0</Chuva20>
</Table></DataTable>'''
TELEMETRIA = b'''<DataTable xmlns="http://MRCS/"><Table>
<CodEstacao>60478482</CodEstacao><DataHora>2024-05-15T08:30:00</DataHora>
<Chuva>1,2</Chuva></Table><Table><DataHora>2024-05-15T09:00:00</DataHora>
<CodEstacao>60478482</CodEstacao><Chuva></Chuva></Table></DataTable>'''

class APITests(unittest.TestCase):
    def test_valores_ausentes_nao_sao_zeros(self):
        self.assertIsNone(_numero(''))
        self.assertIsNone(_numero('-'))
        self.assertEqual(_numero('0'), 0)
        self.assertEqual(_numero('1,25'), 1.25)

    def test_leitura_diaria_filtra_intervalo_parcial(self):
        regs = interpretar_historico(HISTORICO, '60478482', date(2024,5,15), date(2024,5,20))
        self.assertEqual([r['data'] for r in regs], ['2024-05-15','2024-05-16','2024-05-20'])
        self.assertEqual([r['chuva_mm'] for r in regs], [4.3,2.5,0.0])
        self.assertTrue(all(r['hora'] is None for r in regs))

    def test_telemetria_tem_horario_real(self):
        regs=interpretar_telemetria(TELEMETRIA,'60478482',date(2024,5,15),date(2024,5,15))
        self.assertEqual(regs[0]['hora'], '08:30:00')
        self.assertEqual(regs[0]['chuva_mm'],1.2)
        self.assertIsNone(regs[1]['chuva_mm'])

    def test_data_futura_e_data_invertida_sao_bloqueadas(self):
        with self.assertRaises(ConsultaErro):
            validar_filtros('60478482','2030-01-01','2030-01-03')
        with self.assertRaises(ConsultaErro):
            validar_filtros('60478482','2024-02-02','2024-02-01')
        with self.assertRaises(ConsultaErro):
            validar_filtros('ABC','2024-02-01','2024-02-02')

    def test_periodo_historico_abrange_mes_completo(self):
        self.assertEqual(list(_periodos(date(2024,5,15),date(2024,5,20),'historico')),
                         [(date(2024,5,1),date(2024,5,31))])
        self.assertEqual(list(_periodos(date(2024,1,15),date(2024,4,10),'historico')),
                         [(date(2024,1,1),date(2024,3,31)),
                          (date(2024,4,1),date(2024,4,30))])

    def test_consulta_fake_preserva_valores_e_calculos(self):
        with patch('ana_service._pedir_api', return_value=(HISTORICO,'https://ana.exemplo/ServiceANA.asmx')) as mock:
            result=consultar('60478482',date(2024,5,1),date(2024,5,3))
        self.assertEqual(result['resumo']['chuva_total_mm'],12.5)
        self.assertEqual(result['resumo']['dias_com_chuva'],1)
        self.assertEqual(result['resumo']['sem_leitura'],1)
        self.assertEqual(result['resumo']['total_registros'],3)
        self.assertEqual(mock.call_args.args[1]['dataInicio'],'01/05/2024')

    def test_xml_soap_com_escape(self):
        soap = b'<Envelope><Body><Result>&lt;DataTable&gt;&lt;Table&gt;&lt;DataHora&gt;2024-05-15&lt;/DataHora&gt;&lt;Chuva&gt;4.2&lt;/Chuva&gt;&lt;/Table&gt;&lt;/DataTable&gt;</Result></Body></Envelope>'
        regs=interpretar_telemetria(soap,'1',date(2024,5,15),date(2024,5,15))
        self.assertEqual(regs[0]['chuva_mm'],4.2)

class ServidorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.httpd = ThreadingHTTPServer(('127.0.0.1',0),Handler)
        cls.port=cls.httpd.server_address[1]
        cls.thread=threading.Thread(target=cls.httpd.serve_forever,daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown();cls.httpd.server_close();cls.thread.join(timeout=3)

    def request(self,method,path,payload=None):
        conn=http.client.HTTPConnection('127.0.0.1',self.port,timeout=4)
        body=None if payload is None else json.dumps(payload).encode()
        conn.request(method,path,body,{'Content-Type':'application/json'})
        response=conn.getresponse(); b=response.read(); status=response.status; conn.close()
        return status,b

    def test_html_manifest_e_icons(self):
        for path in ('/','/app.js','/style.css','/manifest.webmanifest','/icons/icon-192.png','/sw.js'):
            status,body=self.request('GET',path)
            self.assertEqual(status,200,(path,body[:80]))
            self.assertTrue(body)

    def test_rejeita_data_errada_sem_consultar_ana(self):
        status,body=self.request('POST','/api/consultar',
             {'estacao':'!', 'inicio':'2024-05-01','fim':'2024-05-10'})
        self.assertEqual(status,422)
        self.assertIn('erro',json.loads(body))

    def test_consulta_json_com_resultado_simulado(self):
        fixture={'estacao':'60478482','inicio':'2024-05-01','fim':'2024-05-03',
                 'registros':[{'estacao':'60478482','data':'2024-05-01',
                               'hora':None,'chuva_mm':12.5}],
                 'resumo':{'chuva_total_mm':12.5,'total_registros':1,'dias_com_chuva':1,'sem_leitura':0}}
        with patch('servidor.consultar',return_value=fixture):
            status,body=self.request('POST','/api/consultar',
                 {'estacao':'60478482','inicio':'2024-05-01','fim':'2024-05-03'})
        self.assertEqual(status,200)
        self.assertEqual(json.loads(body)['resumo']['chuva_total_mm'],12.5)

if __name__=='__main__':unittest.main()
