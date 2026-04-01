from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.db import get_conn
from app.services.auth_service import get_current_user_from_token

router = APIRouter(prefix="/historico", tags=["historico"])

bearer_scheme = HTTPBearer()


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)):
    try:
        token = credentials.credentials
        return get_current_user_from_token(token)
    except Exception:
        raise HTTPException(status_code=401, detail="Token inválido")



@router.post("/filtros")
def salvar_filtro(
    body: dict,
    current_user=Depends(get_current_user)
):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                insert into public.filtros_salvos (
                    usuario_id,
                    country_code,
                    country_name,
                    renda_min,
                    renda_max,
                    peso_renda,
                    peso_escolas,
                    peso_hospitais,
                    peso_criminalidade
                )
                values (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                returning *
            """, (
                current_user["id"],
                body["country_code"],
                body["country_name"],
                body.get("renda_min"),
                body.get("renda_max"),
                body["peso_renda"],
                body["peso_escolas"],
                body["peso_hospitais"],
                body["peso_criminalidade"]
            ))

            row = cur.fetchone()
        conn.commit()

    row["favorito"] = False
    return row



@router.get("/filtros")
def listar_filtros(current_user=Depends(get_current_user)):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                select
                    fs.*,
                    case when f.id is not null then true else false end as favorito
                from filtros_salvos fs
                left join favoritos f
                  on f.filtro_id = fs.id
                 and f.usuario_id = fs.usuario_id
                where fs.usuario_id = %s
                order by fs.criado_em desc
            """, (current_user["id"],))

            return cur.fetchall()



@router.delete("/filtros/{filtro_id}")
def remover_filtro(filtro_id: str, current_user=Depends(get_current_user)):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                delete from filtros_salvos
                where id = %s and usuario_id = %s
            """, (filtro_id, current_user["id"]))
        conn.commit()

    return {"ok": True}



@router.post("/favoritos")
def adicionar_favorito(
    body: dict,
    current_user=Depends(get_current_user)
):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                insert into favoritos (usuario_id, filtro_id)
                values (%s,%s)
                on conflict do nothing
            """, (
                current_user["id"],
                body["filtro_id"]
            ))
        conn.commit()

    return {"ok": True}



@router.get("/favoritos")
def listar_favoritos(current_user=Depends(get_current_user)):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                select fs.*, true as favorito
                from favoritos f
                join filtros_salvos fs on fs.id = f.filtro_id
                where f.usuario_id = %s
                order by f.criado_em desc
            """, (current_user["id"],))

            return cur.fetchall()



@router.delete("/favoritos/{filtro_id}")
def remover_favorito(filtro_id: str, current_user=Depends(get_current_user)):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                delete from favoritos
                where usuario_id = %s and filtro_id = %s
            """, (current_user["id"], filtro_id))
        conn.commit()

    return {"ok": True}