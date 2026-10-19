import json
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .auth import hash_senha
from .config import get_settings
from .models import Questao, Usuario

SEED = Path(__file__).parent / "data" / "questoes_seed.json"


def garante_admin(db: Session) -> None:
    s = get_settings()
    email = s.admin_email.strip().lower()
    if not db.scalar(select(Usuario).where(Usuario.email == email)):
        db.add(Usuario(email=email, senha_hash=hash_senha(s.admin_password)))
        db.commit()


def carrega_questoes(db: Session) -> int:
    if db.scalar(select(func.count(Questao.id))):
        return 0  # banco já tem questões: não duplica
    dados = json.loads(SEED.read_text(encoding="utf-8"))
    db.add_all(Questao(**q) for q in dados)
    db.commit()
    return len(dados)
