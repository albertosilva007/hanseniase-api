import pytest
from fastapi.testclient import TestClient

from app.main import app

S = "sessao-jogo-0001"


@pytest.fixture(scope="module")
def c():
    with TestClient(app) as client:
        yield client


@pytest.fixture(scope="module")
def auth(c):
    r = c.post("/api/auth/login", json={"email": "admin@teste.com", "senha": "senha-teste"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture(scope="module")
def gabarito(c):
    return {q["id"]: q["correta"] for q in c.get("/api/questoes?gabarito=true").json()}


def _trilha(c, publico):
    return next(t for t in c.get(f"/api/jogo/trilhas?publico={publico}&sessao={S}").json())


def _joga(c, mid, gabarito, errar=0, sessao=S):
    """Joga a missão inteira; erra as `errar` primeiras etapas. Devolve a última resposta."""
    r = c.post(f"/api/jogo/missoes/{mid}/iniciar", json={"sessao": sessao})
    assert r.status_code == 200, r.text
    etapa = r.json()["etapa"]
    assert "correta" not in etapa  # gabarito nunca vai na etapa
    n = 0
    while True:
        certa = gabarito[etapa["questao_id"]]
        escolha = (certa + 1) % len(etapa["opcoes"]) if n < errar else certa
        out = c.post(f"/api/jogo/missoes/{mid}/responder", json={"sessao": sessao, "escolha": escolha}).json()
        n += 1
        if out["resultado"]:
            return out
        etapa = out["proxima_etapa"]


def test_trilhas_geradas(c):
    ts = c.get("/api/jogo/trilhas").json()
    assert {t["publico"] for t in ts} == {"prof", "pac"}
    prof = _trilha(c, "prof")
    ms = c.get(f"/api/jogo/trilhas/{prof['id']}/missoes").json()
    assert ms[0]["tema"] == "Etiologia e transmissão" and ms[0]["status"] == "disponivel"
    assert all(m["status"] == "bloqueada" for m in ms[1:])
    assert ms[-1]["tipo"] == "chefe" and ms[-1]["total_etapas"] == 7  # 1 por tema
    assert all(m["total_etapas"] <= 4 for m in ms[:-1])
    # Tratamento (6 questões) vira 2 partes
    assert sum(1 for m in ms if m["tema"] == "Tratamento") == 2


def test_pagina_jogo_e_pct_minimo(c):
    assert c.get("/jogo").status_code == 200
    pac = _trilha(c, "pac")
    ms = c.get(f"/api/jogo/trilhas/{pac['id']}/missoes").json()
    assert all(m["pct_minimo"] == 0.6 for m in ms if m["tipo"] == "quiz")
    assert ms[-1]["pct_minimo"] == 0.8


def test_bloqueio_e_fluxo(c, gabarito):
    pac = _trilha(c, "pac")
    ms = c.get(f"/api/jogo/trilhas/{pac['id']}/missoes?sessao={S}").json()
    assert c.post(f"/api/jogo/missoes/{ms[1]['id']}/iniciar", json={"sessao": S}).status_code == 403
    assert c.post(f"/api/jogo/missoes/{ms[0]['id']}/responder",
                  json={"sessao": S, "escolha": 0}).status_code == 409  # sem iniciar

    # falha: erra tudo
    out = _joga(c, ms[0]["id"], gabarito, errar=99)
    assert out["resultado"]["status"] == "falhou" and out["xp_total"] == 0
    assert c.post(f"/api/jogo/missoes/{ms[1]['id']}/iniciar", json={"sessao": S}).status_code == 403

    # vence: acerta tudo
    out = _joga(c, ms[0]["id"], gabarito)
    r = out["resultado"]
    n = r["total_etapas"]
    assert r["status"] == "concluida" and r["pct"] == 1.0
    assert r["insignia_nova"] == "Transmissão" and r["proxima_missao_id"] == ms[1]["id"]
    assert out["xp_total"] == 10 * n + 50

    ms = c.get(f"/api/jogo/trilhas/{pac['id']}/missoes?sessao={S}").json()
    assert ms[0]["status"] == "concluida" and ms[1]["status"] == "disponivel"

    # rejogar não dá XP de novo
    out = _joga(c, ms[0]["id"], gabarito)
    assert out["xp_total"] == 10 * n + 50 and out["resultado"]["insignia_nova"] is None


def test_dois_de_tres_passa(c, gabarito):
    s2 = "sessao-jogo-0002"
    prof = _trilha(c, "prof")
    m1 = c.get(f"/api/jogo/trilhas/{prof['id']}/missoes").json()[0]
    assert m1["total_etapas"] == 3
    out = _joga(c, m1["id"], gabarito, errar=1, sessao=s2)
    assert out["resultado"]["status"] == "concluida" and out["resultado"]["acertos"] == 2


def test_etapa_atual_e_validacoes(c, gabarito):
    pac = _trilha(c, "pac")
    m2 = c.get(f"/api/jogo/trilhas/{pac['id']}/missoes?sessao={S}").json()[1]
    e1 = c.post(f"/api/jogo/missoes/{m2['id']}/iniciar", json={"sessao": S}).json()["etapa"]
    assert c.get(f"/api/jogo/missoes/{m2['id']}/etapa?sessao={S}").json() == e1
    assert c.post(f"/api/jogo/missoes/{m2['id']}/responder", json={"sessao": S, "escolha": 9}).status_code == 422
    c.post(f"/api/jogo/missoes/{m2['id']}/responder", json={"sessao": S, "escolha": gabarito[e1["questao_id"]]})
    assert c.get(f"/api/jogo/missoes/{m2['id']}/etapa?sessao={S}").json()["etapa"] == 2


def test_perfil(c):
    p = c.get(f"/api/jogo/jogador/{S}").json()
    assert p["xp_total"] > 0 and p["sequencia_dias"] == 1
    assert p["insignias"] == ["Transmissão"] and p["missoes_concluidas"] == 1
    assert p["xp_proximo_nivel"] == p["nivel"] * 200 - p["xp_total"]
    novo = c.get("/api/jogo/jogador/sessao-nova-123").json()
    assert novo["xp_total"] == 0 and novo["nivel"] == 1


def test_resposta_do_jogo_entra_nas_stats(c, auth):
    s = c.get("/api/admin/stats", headers=auth).json()
    assert s["total_respostas"] > 0


def test_admin_regenera(c, auth):
    assert c.post("/api/admin/missoes/gerar").status_code == 401
    assert c.post("/api/admin/missoes/gerar", headers=auth).json()["trilhas"] == 0  # já existe
    r = c.post("/api/admin/missoes/gerar?recriar=true", headers=auth).json()
    assert r["trilhas"] == 2 and r["missoes"] > 10
    # progresso de missão zera, XP e insígnias ficam
    assert c.get(f"/api/jogo/jogador/{S}").json()["insignias"] == ["Transmissão"]


def test_banco_cru(c, auth):
    assert c.get("/admin/banco").status_code == 200
    assert c.get("/api/admin/banco").status_code == 401
    ts = {t["tabela"]: t for t in c.get("/api/admin/banco", headers=auth).json()}
    assert {"questoes", "respostas", "missoes", "jogadores", "usuarios"} <= set(ts)
    assert "senha_hash" not in ts["usuarios"]["colunas"]
    d = c.get("/api/admin/banco/missoes?limite=5", headers=auth).json()
    assert d["total"] == ts["missoes"]["linhas"] and len(d["linhas"]) == 5
    assert len(d["linhas"][0]) == len(d["colunas"])
    q = c.get("/api/admin/banco/questoes?limite=1", headers=auth).json()
    assert isinstance(q["linhas"][0][q["colunas"].index("opcoes")], list)  # JSON sai como lista
    assert c.get("/api/admin/banco/pg_user", headers=auth).status_code == 404  # fora da lista
    csv = c.get("/api/admin/banco/questoes/csv", headers=auth)
    assert csv.status_code == 200 and csv.text.splitlines()[0].startswith("id,")
    assert "senha_hash" not in c.get("/api/admin/banco/usuarios/csv", headers=auth).text
