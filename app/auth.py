from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import get_settings
from .database import get_db
from .models import Usuario

ALG = "HS256"
_bearer = HTTPBearer(auto_error=False)


def hash_senha(senha: str) -> str:
    return bcrypt.hashpw(senha.encode(), bcrypt.gensalt()).decode()


def confere_senha(senha: str, hash_: str) -> bool:
    try:
        return bcrypt.checkpw(senha.encode(), hash_.encode())
    except ValueError:
        return False


def cria_token(email: str) -> str:
    s = get_settings()
    exp = datetime.now(timezone.utc) + timedelta(minutes=s.access_token_minutes)
    return jwt.encode({"sub": email, "exp": exp}, s.secret_key, algorithm=ALG)


def admin_atual(
    cred: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> Usuario:
    erro = HTTPException(status.HTTP_401_UNAUTHORIZED, "Sessão inválida ou expirada. Faça login de novo.",
                         headers={"WWW-Authenticate": "Bearer"})
    if not cred:
        raise erro
    try:
        email = jwt.decode(cred.credentials, get_settings().secret_key, algorithms=[ALG]).get("sub")
    except jwt.PyJWTError:
        raise erro
    user = db.scalar(select(Usuario).where(Usuario.email == email))
    if not user:
        raise erro
    return user
