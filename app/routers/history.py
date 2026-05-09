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
            # Os filtros_salvos passaram a ser apenas histórico de pesquisas.
            # Favoritos são por município (tabela `favoritos`), não por filtro.
            cur.execute("""
                select fs.*, false as favorito
                from filtros_salvos fs
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
    """
    Marca um município como favorito do utilizador autenticado.

    Body esperado: {"codigo_municipio": <int>}
    """
    codigo_municipio = body.get("codigo_municipio")
    if codigo_municipio is None:
        raise HTTPException(status_code=400, detail="codigo_municipio em falta.")

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                insert into public.favoritos (usuario_id, codigo_municipio)
                values (%s, %s)
                on conflict (usuario_id, codigo_municipio) do nothing
            """, (
                current_user["id"],
                codigo_municipio
            ))
        conn.commit()

    return {"ok": True}



@router.get("/favoritos")
def listar_favoritos(current_user=Depends(get_current_user)):
    """
    Devolve a lista de municípios favoritos do utilizador, com os dados
    necessários para mostrar diretamente nos cartões de cidade.
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                select
                    f.id              as favorito_id,
                    f.criado_em       as favoritado_em,
                    m.codigo_municipio,
                    m.municipio_localidade,
                    m.regiao,
                    m.grande_regiao
                from public.favoritos f
                join public.municipios m
                    on m.codigo_municipio = f.codigo_municipio
                where f.usuario_id = %s
                order by f.criado_em desc
            """, (current_user["id"],))

            return cur.fetchall()



@router.delete("/favoritos/{codigo_municipio}")
def remover_favorito(
    codigo_municipio: int,
    current_user=Depends(get_current_user)
):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                delete from public.favoritos
                where usuario_id = %s and codigo_municipio = %s
            """, (current_user["id"], codigo_municipio))
        conn.commit()

    return {"ok": True}