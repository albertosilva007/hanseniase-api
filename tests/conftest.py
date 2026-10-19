import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
DB = ROOT / "tests" / "_test.db"
if DB.exists():
    DB.unlink()
os.environ.update(DATABASE_URL=f"sqlite:///{DB}", ADMIN_EMAIL="Admin@Teste.com",
                  ADMIN_PASSWORD="senha-teste", SECRET_KEY="x" * 40)
