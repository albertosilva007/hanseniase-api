# API Questões de Hanseníase

Back end em **FastAPI + PostgreSQL** para o banco de questões sobre hanseníase. Um único serviço entrega a API e as três páginas:

| Rota | O que é |
|---|---|
| `/` | Página pública: praticar ou ler as questões |
| `/admin` | Painel da equipe: login e cadastro/edição de questões |
| `/dashboard` | Estatísticas de acerto e exportação CSV |
| `/docs` | Documentação interativa da API (Swagger) |

Na primeira subida, o sistema cria o usuário admin (a partir das variáveis de ambiente) e carrega as 42 questões iniciais de `app/data/questoes_seed.json`.

## Deploy no Render

1. Suba esta pasta para um repositório no GitHub.
2. No Render, clique em **New → Blueprint** e selecione o repositório. O `render.yaml` cria:
   - `hanseniase-api`: serviço web (Docker)
   - `hanseniase-db`: PostgreSQL
3. O Render vai pedir `ADMIN_EMAIL` e `ADMIN_PASSWORD`. A `SECRET_KEY` é gerada automaticamente.
4. Quando terminar, acesse `https://<seu-servico>.onrender.com/admin`.

Fique atento a dois limites do plano free do Render. O serviço "dorme" depois de um tempo sem acesso, e a primeira requisição leva uns 30 a 60 s. O banco free também tem prazo de validade. Para uso contínuo na pesquisa, confira os planos pagos.

## Rodar localmente

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env          # ajuste e-mail e senha do admin
uvicorn app.main:app --reload # http://localhost:8000
pytest -q                     # testes
```

Com PostgreSQL via Docker:

```bash
cp .env.example .env
docker compose up --build
```

## Endpoints

**Públicos**
- `GET /api/questoes?publico=prof|pac&tema=&busca=&gabarito=true|false`: sem `gabarito=true`, a resposta certa não é enviada.
- `GET /api/temas?publico=`
- `POST /api/respostas` `{questao_id, escolha, sessao}`: o servidor corrige, salva e devolve `{acertou, correta, explicacao}`.

**Admin** (header `Authorization: Bearer <token>`)
- `POST /api/auth/login` `{email, senha}` → `{access_token}`
- `GET/POST /api/admin/questoes`, `PUT/DELETE /api/admin/questoes/{id}`
- `GET /api/admin/stats`: totais, por público, por tema, por questão e por dia
- `GET /api/admin/respostas.csv`: todas as respostas, para análise em pandas ou Power BI

## Dados coletados

Cada resposta grava a questão, a alternativa escolhida, se acertou, a data e um **identificador anônimo de sessão** gerado no navegador. Não há nome, e-mail nem IP. Se os dados entrarem na pesquisa, confirme com o comitê de ética se o TCLE precisa cobrir essa coleta.

## Estrutura

```
app/
  main.py          # app, páginas e startup (cria tabelas, admin e seed)
  config.py        # variáveis de ambiente
  database.py      # engine SQLAlchemy (SQLite local / PostgreSQL)
  models.py        # Usuario, Questao, Resposta
  schemas.py       # validação Pydantic
  auth.py          # bcrypt + JWT
  seed.py
  routers/publico.py, routers/admin.py
  static/          # index.html, admin.html, dashboard.html, app.css
  data/questoes_seed.json
tests/test_api.py
Dockerfile · docker-compose.yml · render.yaml
```

As tabelas são criadas com `create_all`. Se o modelo mudar depois que já houver dados em produção, vale adicionar o Alembic para as migrações.
