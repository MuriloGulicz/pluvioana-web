# Publicar o PluvioANA sem CMD — GitHub + Render

Você fará a publicação **uma única vez** usando somente o navegador. O ZIP já inclui o servidor, a configuração de implantação e o site.

## Parte 1 — Colocar os arquivos no GitHub

1. Crie uma conta ou entre em https://github.com/.
2. Use o botão **New repository** (ou `+` > **New repository**).
3. Nome: `pluvioana-web`. Pode escolher **Public** para simplificar o acesso. Não marque a criação de README, porque o projeto já tem um.
4. Clique **Create repository**.
5. No computador, **extraia o ZIP**. No GitHub, clique **uploading an existing file** (ou **Add file** > **Upload files**).
6. Arraste todos os itens **de dentro da pasta extraída** para o upload (incluindo `app.py`, `ana_service.py`, `render.yaml`, `.python-version`, `requirements.txt`, `static/` e `testes/`). Não envie o ZIP fechado. Confira que `app.py` e `render.yaml` estão na **raiz do repositório**.
7. Confirme em **Commit changes**.

## Parte 2 — Hospedar no Render

1. Entre em https://dashboard.render.com/ e faça login (pode usar a conta GitHub).
2. Clique **New** > **Blueprint**.
3. Conecte o repositório `pluvioana-web` que acabou de criar.
4. O Render lerá o arquivo `render.yaml`. Revise: serviço web Python, plano **Free**, nome `pluvioana-web`. Confirme a criação/aplicação do Blueprint.
5. Depois de o deploy terminar com sucesso e o serviço ficar **Live**, abra o endereço HTTPS mostrado no painel, semelhante a `https://pluvioana-web-xxxx.onrender.com`.

**Esse endereço é apenas ilustrativo:** a URL real será criada pelo Render e precisa ser copiada do seu painel.

## Parte 3 — Confirmar que tudo funciona

1. Abra `https://SEU-ENDERECO.onrender.com/api/health` substituindo pelo link real. Deve aparecer `{"ok":true,"aplicacao":"PluvioANA Web"}`.
2. Abra a raiz do seu link. A interface deverá aparecer.
3. Faça uma consulta à **mesma estação e mesmo período** que funcionaram no seu computador.
4. Exporte CSV e teste em outra máquina/celular. Se a interface abre mas consulta falha, procure **Logs** no Render: isso pode indicar indisponibilidade da ANA a partir da nuvem, não erro do frontend.

## Como atualizar depois

Altere os arquivos no GitHub. O Render fará um novo deploy do serviço, sem precisar recompilar ou enviar `.exe`.

## Se você preferir configurar como Web Service (em vez de Blueprint)

Em Render, **New > Web Service** e conecte o mesmo repositório. Use os valores:

| Campo | Preencher |
|---|---|
| Language | Python |
| Instance | Free |
| Build Command | `pip install -r requirements.txt` |
| Start Command | `gunicorn app:app --bind 0.0.0.0:$PORT --workers 1 --threads 4 --timeout 180` |
| Health Check Path | `/api/health` |

Não escolha **Static Site**: a consulta precisa do Python no servidor.

## Observações

- Quem recebe o link não precisa criar conta, instalar Python ou baixar qualquer arquivo.
- A hospedagem gratuita Render pode suspender o serviço após 15 minutos sem visitas e demorar aproximadamente um minuto para voltar.
- Não compartilhe senha ou token do GitHub/Render. Para receber ajuda com a implantação basta enviar a **URL pública do repositório** ou uma captura da configuração/erro.
