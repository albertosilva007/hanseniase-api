import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="module")
def c():
    with TestClient(app) as client:
        yield client


@pytest.fixture(scope="module")
def auth(c):
    r = c.post("/api/auth/login", json={"email": "admin@teste.com", "senha": "senha-teste"})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_health_e_paginas(c):
    assert c.get("/api/health").json() == {"status": "ok"}
    for p in ["/", "/admin", "/dashboard", "/static/app.css"]:
        assert c.get(p).status_code == 200


def test_seed_e_listagem_sem_gabarito(c):
    qs = c.get("/api/questoes").json()
    assert len(qs) == 42
    assert all(q["correta"] is None for q in qs)
    assert all(q["correta"] is not None for q in c.get("/api/questoes?gabarito=true").json())
    assert len(c.get("/api/questoes?publico=pac").json()) == 17
    assert "Reações hansênicas" in c.get("/api/temas").json()
    assert len(c.get("/api/questoes?busca=dapsona").json()) >= 1


def test_resposta_corrigida_no_servidor(c):
    q = c.get("/api/questoes?gabarito=true").json()[0]
    r = c.post("/api/respostas", json={"questao_id": q["id"], "escolha": q["correta"], "sessao": "sessao-teste-1"})
    assert r.status_code == 201 and r.json()["acertou"] is True
    errada = (q["correta"] + 1) % len(q["opcoes"])
    assert c.post("/api/respostas", json={"questao_id": q["id"], "escolha": errada, "sessao": "sessao-teste-2"}).json()["acertou"] is False
    assert c.post("/api/respostas", json={"questao_id": q["id"], "escolha": 9, "sessao": "sessao-teste-1"}).status_code == 422
    assert c.post("/api/respostas", json={"questao_id": 99999, "escolha": 0, "sessao": "sessao-teste-1"}).status_code == 404


def test_admin_protegido(c):
    assert c.get("/api/admin/questoes").status_code == 401
    assert c.post("/api/auth/login", json={"email": "admin@teste.com", "senha": "errada"}).status_code == 401


def test_crud(c, auth):
    nova = {"publico": "pac", "tema": "Teste", "enunciado": "Pergunta de teste?", "opcoes": ["Sim", "Não"],
            "correta": 0, "explicacao": "Porque sim.", "ativo": True}
    assert c.post("/api/admin/questoes", json={**nova, "correta": 5}, headers=auth).status_code == 422
    q = c.post("/api/admin/questoes", json=nova, headers=auth).json()
    q2 = c.put(f"/api/admin/questoes/{q['id']}", json={**nova, "ativo": False}, headers=auth).json()
    assert q2["ativo"] is False
    assert all(x["id"] != q["id"] for x in c.get("/api/questoes").json())  # inativa some do público
    assert c.delete(f"/api/admin/questoes/{q['id']}", headers=auth).status_code == 204
    assert c.delete(f"/api/admin/questoes/{q['id']}", headers=auth).status_code == 404


def test_stats_e_csv(c, auth):
    s = c.get("/api/admin/stats", headers=auth).json()
    assert s["total_respostas"] == 2 and s["total_acertos"] == 1 and s["taxa_geral"] == 50.0
    assert s["sessoes"] == 2 and len(s["por_dia"]) == 1
    csv = c.get("/api/admin/respostas.csv", headers=auth)
    assert csv.status_code == 200 and csv.text.count("\n") == 3
