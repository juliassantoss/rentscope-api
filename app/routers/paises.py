from fastapi import APIRouter
from app.db import get_conn

router = APIRouter(prefix="/paises", tags=["paises"])


@router.get("")
def listar_paises():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "select codigo, nome from public.paises order by nome asc;")
            rows = cur.fetchall()
            return [dict(row) for row in rows]
