# PluvioANA Web — pronto para publicar na Internet

Versão do projeto de consulta de precipitação da ANA preparada para hospedar **site + API** num único endereço HTTPS. Não exige Python instalado nos celulares/computadores visitantes.

> A hospedagem não está criada automaticamente. É necessário publicar o código numa conta própria do GitHub e ativar o serviço em Render. **Veja `PUBLICAR_SEM_CMD.md` para o passo a passo sem terminal.**

## Estrutura

- `static/`: interface HTML/CSS/JavaScript, tabela, datas, CSV, gráfico, PWA.
- `ana_service.py`: requisições reais à ANA, validação e interpretação de XML.
- `app.py`: servidor WSGI para Render; endpoint `/api/consultar` e `/api/health`.
- `render.yaml`: configuração pronta de hospedagem gratuita (Blueprint).
- `requirements.txt`: Gunicorn (servidor HTTP para a nuvem).
- `.python-version`: Python 3.12 na nuvem.
- `servidor.py` e `INICIAR_WEB_WINDOWS.bat`: funcionamento local antigo preservado.
- `testes/`: testes que não dependem da rede da ANA.

## Consulta

Enviar `POST /api/consultar` com JSON do tipo:

```json
{"estacao":"60478482", "inicio":"2024-05-01", "fim":"2024-05-31", "modo":"historico", "consistencia":"1"}
```

O código é apenas um exemplo usado nos testes, não garantia de uma estação ativa.

A API ANA é consumida **no servidor** para evitar problemas de CORS. O app continua usando a operação `HidroSerieHistorica` para chuvas diárias (sem horário por dia) ou, se o usuário selecionar a outra fonte, `DadosHidrometeorologicos`. Exportação CSV no navegador. O servidor retorna erro se a API real não responder: não gera precipitações inventadas.

## Testes

Em um computador com Python (opcional):

```bash
python -m unittest discover -s testes -v
```

A implantação pública requer acesso de saída do Render aos domínios da ANA. Os testes cobrem o servidor e o parser com XML simulado, **mas não validam a disponibilidade da ANA a partir da hospedagem**. Após publicar, teste uma estação e um período que já funcionam na versão local.

## Limitações da hospedagem gratuita

Serviços gratuitos Render podem desligar após 15 minutos de inatividade e levar cerca de um minuto para reiniciar. O endereço `onrender.com` é concedido apenas quando o deploy é concluído na conta do proprietário. Recomenda-se uso acadêmico ou demonstração, não produção crítica.
