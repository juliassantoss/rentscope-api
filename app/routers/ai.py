"""
Endpoint do assistente inteligente do RentScope (Scopey).

A camada que serve este endpoint cumpre dois papéis:

1.  Enriquecer o contexto que vai para o modelo de linguagem com dados reais
    da base de dados — métricas do município mencionado (quando aplicável) e
    uma visão geral agregada do conjunto de concelhos. Sem este enriquecimento
    o modelo só consegue inferir a partir do nome das funcionalidades, o que
    leva a respostas plausíveis mas factualmente erradas.

2.  Fornecer ao modelo um bloco "App reference" estável com a documentação
    técnica do RentScope (cálculo do score, telas, fontes de dados, cobertura
    parcial da renda). Este bloco é usado como ground truth para que o modelo
    não invente regras nem unidades.
"""

import os
from typing import Optional, Any

from fastapi import APIRouter, HTTPException
from openai import OpenAI
from pydantic import BaseModel

from app.db import get_conn

router = APIRouter(prefix="/ai", tags=["ai"])

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


class AiQuestionRequest(BaseModel):
    pais: str
    municipio: Optional[str] = None
    pergunta: str
    idioma_app: str
    renda_min: Optional[float] = None
    renda_max: Optional[float] = None
    peso_renda: Optional[float] = None
    peso_escolas: Optional[float] = None
    peso_hospitais: Optional[float] = None
    peso_criminalidade: Optional[float] = None
    renda: Optional[float] = None
    escolas: Optional[float] = None
    hospitais: Optional[float] = None
    criminalidade: Optional[float] = None
    score: Optional[float] = None


class AiQuestionResponse(BaseModel):
    resposta: str


def resolve_language_name(language_code: str) -> str:
    normalized = (language_code or "pt").strip().lower()
    return {
        "pt": "Portuguese",
        "en": "English",
        "es": "Spanish",
    }.get(normalized, "Portuguese")


def _fmt(value: Any) -> str:
    """Formata valores para o contexto enviado ao modelo."""
    if value is None:
        return "no data"
    if isinstance(value, float):
        # Evita ruído como 7.450000004
        return f"{value:.2f}"
    return str(value)


def fetch_municipio_data(nome: str) -> Optional[dict]:
    """
    Procura um município pelo nome (case-insensitive, com tolerância de
    acentos via ilike) e devolve as métricas mais recentes disponíveis.

    Devolve None se o nome não corresponder a nenhum município.
    """
    if not nome or not nome.strip():
        return None

    sql = """
        with latest_renda as (
            select
                r.codigo_municipio,
                r.trimestre,
                r.valor_medio_m2,
                row_number() over (
                    partition by r.codigo_municipio
                    order by
                        cast(substring(r.trimestre from '(\\d{4})') as int) desc,
                        cast(substring(r.trimestre from '^(\\d)') as int) desc
                ) as rn
            from public.renda r
        ),
        latest_escolas as (
            select
                e.codigo_municipio,
                e.ano,
                e.valor,
                row_number() over (
                    partition by e.codigo_municipio
                    order by cast(split_part(e.ano, '/', 1) as int) desc
                ) as rn
            from public.escolas e
        )
        select
            m.codigo_municipio,
            m.municipio_localidade,
            m.regiao,
            m.grande_regiao,
            lr.valor_medio_m2 as renda_eur_m2,
            lr.trimestre as renda_trimestre,
            coalesce(le.valor, 0) as escolas,
            coalesce(h.hospitais_2024, 0) as hospitais,
            coalesce(c.crimes_2024, 0) as crimes
        from public.municipios m
        left join latest_renda lr
            on lr.codigo_municipio = m.codigo_municipio
           and lr.rn = 1
        left join latest_escolas le
            on le.codigo_municipio = m.codigo_municipio
           and le.rn = 1
        left join public.hospitais h
            on h.codigo_municipio = m.codigo_municipio
        left join public.criminalidade c
            on c.codigo_municipio = m.codigo_municipio
        where m.municipio_localidade ilike %s
        order by m.municipio_localidade
        limit 1
    """

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (f"%{nome.strip()}%",))
            return cur.fetchone()


def fetch_overview() -> dict:
    """
    Devolve uma visão agregada do conjunto de municípios.

    Inclui contagem total, cobertura da renda, médias por dimensão e o
    top-3 dos extremos (mais barato, mais escolas, mais hospitais, menos
    crimes). É usado como contexto generico em todas as perguntas, para que
    o modelo consiga responder a perguntas tipo "qual é o concelho mais
    barato?" sem precisar de ferramentas adicionais.
    """
    sql_overview = """
        with latest_renda as (
            select
                r.codigo_municipio,
                r.valor_medio_m2,
                row_number() over (
                    partition by r.codigo_municipio
                    order by
                        cast(substring(r.trimestre from '(\\d{4})') as int) desc,
                        cast(substring(r.trimestre from '^(\\d)') as int) desc
                ) as rn
            from public.renda r
        ),
        latest_escolas as (
            select
                e.codigo_municipio,
                e.valor,
                row_number() over (
                    partition by e.codigo_municipio
                    order by cast(split_part(e.ano, '/', 1) as int) desc
                ) as rn
            from public.escolas e
        ),
        base as (
            select
                m.codigo_municipio,
                m.municipio_localidade,
                lr.valor_medio_m2 as renda,
                coalesce(le.valor, 0) as escolas,
                coalesce(h.hospitais_2024, 0) as hospitais,
                coalesce(c.crimes_2024, 0) as crimes
            from public.municipios m
            left join latest_renda lr
                on lr.codigo_municipio = m.codigo_municipio
               and lr.rn = 1
            left join latest_escolas le
                on le.codigo_municipio = m.codigo_municipio
               and le.rn = 1
            left join public.hospitais h
                on h.codigo_municipio = m.codigo_municipio
            left join public.criminalidade c
                on c.codigo_municipio = m.codigo_municipio
        )
        select
            count(*) as total_municipios,
            count(renda) as municipios_com_renda,
            avg(renda)::float as renda_media,
            min(renda)::float as renda_min,
            max(renda)::float as renda_max,
            avg(escolas)::float as escolas_media,
            avg(hospitais)::float as hospitais_media,
            avg(crimes)::float as crimes_media
        from base
    """

    sql_extremos_renda_baixa = """
        with latest_renda as (
            select
                r.codigo_municipio,
                r.valor_medio_m2,
                row_number() over (
                    partition by r.codigo_municipio
                    order by
                        cast(substring(r.trimestre from '(\\d{4})') as int) desc,
                        cast(substring(r.trimestre from '^(\\d)') as int) desc
                ) as rn
            from public.renda r
        )
        select m.municipio_localidade, lr.valor_medio_m2 as renda
        from public.municipios m
        join latest_renda lr
            on lr.codigo_municipio = m.codigo_municipio
           and lr.rn = 1
        where lr.valor_medio_m2 is not null
        order by lr.valor_medio_m2 asc
        limit 3
    """

    sql_extremos_renda_alta = """
        with latest_renda as (
            select
                r.codigo_municipio,
                r.valor_medio_m2,
                row_number() over (
                    partition by r.codigo_municipio
                    order by
                        cast(substring(r.trimestre from '(\\d{4})') as int) desc,
                        cast(substring(r.trimestre from '^(\\d)') as int) desc
                ) as rn
            from public.renda r
        )
        select m.municipio_localidade, lr.valor_medio_m2 as renda
        from public.municipios m
        join latest_renda lr
            on lr.codigo_municipio = m.codigo_municipio
           and lr.rn = 1
        where lr.valor_medio_m2 is not null
        order by lr.valor_medio_m2 desc
        limit 3
    """

    sql_top_escolas = """
        with latest_escolas as (
            select
                e.codigo_municipio,
                e.valor,
                row_number() over (
                    partition by e.codigo_municipio
                    order by cast(split_part(e.ano, '/', 1) as int) desc
                ) as rn
            from public.escolas e
        )
        select m.municipio_localidade, le.valor as escolas
        from public.municipios m
        join latest_escolas le
            on le.codigo_municipio = m.codigo_municipio
           and le.rn = 1
        order by le.valor desc
        limit 3
    """

    sql_top_hospitais = """
        select m.municipio_localidade, h.hospitais_2024 as hospitais
        from public.municipios m
        join public.hospitais h on h.codigo_municipio = m.codigo_municipio
        order by h.hospitais_2024 desc
        limit 3
    """

    sql_menos_crimes = """
        select m.municipio_localidade, c.crimes_2024 as crimes
        from public.municipios m
        join public.criminalidade c on c.codigo_municipio = m.codigo_municipio
        order by c.crimes_2024 asc
        limit 3
    """

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql_overview)
            overview = cur.fetchone() or {}

            cur.execute(sql_extremos_renda_baixa)
            mais_baratos = cur.fetchall()

            cur.execute(sql_extremos_renda_alta)
            mais_caros = cur.fetchall()

            cur.execute(sql_top_escolas)
            top_escolas = cur.fetchall()

            cur.execute(sql_top_hospitais)
            top_hospitais = cur.fetchall()

            cur.execute(sql_menos_crimes)
            menos_crimes = cur.fetchall()

    return {
        "overview": overview,
        "mais_baratos": mais_baratos,
        "mais_caros": mais_caros,
        "top_escolas": top_escolas,
        "top_hospitais": top_hospitais,
        "menos_crimes": menos_crimes,
    }


def _format_municipio_block(municipio: Optional[dict]) -> str:
    """Bloco do contexto com os dados do município específico mencionado."""
    if not municipio:
        return "Specific municipality data:\n- not requested or not found in the database"

    return (
        "Specific municipality data (live from the database):\n"
        f"- Name: {municipio.get('municipio_localidade')}\n"
        f"- District / NUTS II: {municipio.get('regiao') or '—'} / "
        f"{municipio.get('grande_regiao') or '—'}\n"
        f"- Median rent: {_fmt(municipio.get('renda_eur_m2'))} €/m² "
        f"(quarter: {_fmt(municipio.get('renda_trimestre'))})\n"
        f"- Schools (most recent year available): {_fmt(municipio.get('escolas'))}\n"
        f"- Hospitals (2024): {_fmt(municipio.get('hospitais'))}\n"
        f"- Crimes registered (2024): {_fmt(municipio.get('crimes'))}"
    )


def _format_overview_block(overview_data: dict) -> str:
    """Bloco do contexto com estatísticas globais e top-3 por dimensão."""
    ov = overview_data.get("overview") or {}

    def join_top(rows, value_key, unit=""):
        if not rows:
            return "no data"
        return ", ".join(
            f"{r['municipio_localidade']} ({_fmt(r[value_key])}{unit})"
            for r in rows
        )

    return (
        "Global overview (live from the database):\n"
        f"- Total municipalities: {_fmt(ov.get('total_municipios'))}\n"
        f"- Municipalities with official rent data: {_fmt(ov.get('municipios_com_renda'))}\n"
        f"- Rent (€/m²): avg {_fmt(ov.get('renda_media'))}, "
        f"min {_fmt(ov.get('renda_min'))}, max {_fmt(ov.get('renda_max'))}\n"
        f"- Schools average per municipality: {_fmt(ov.get('escolas_media'))}\n"
        f"- Hospitals average per municipality: {_fmt(ov.get('hospitais_media'))}\n"
        f"- Crimes average per municipality (2024): {_fmt(ov.get('crimes_media'))}\n"
        "Extremes:\n"
        f"- Cheapest rent: {join_top(overview_data.get('mais_baratos', []), 'renda', ' €/m²')}\n"
        f"- Most expensive rent: {join_top(overview_data.get('mais_caros', []), 'renda', ' €/m²')}\n"
        f"- Most schools: {join_top(overview_data.get('top_escolas', []), 'escolas')}\n"
        f"- Most hospitals: {join_top(overview_data.get('top_hospitais', []), 'hospitais')}\n"
        f"- Fewest crimes: {join_top(overview_data.get('menos_crimes', []), 'crimes')}"
    )


# Documentação técnica do RentScope. Vai como parte do system prompt para
# que o modelo responda de acordo com a verdade do sistema, em vez de
# inferir/inventar com base em apps de habitação genéricas.
APP_REFERENCE = """
RentScope reference (use this as ground truth, do not contradict):

Score system:
- Each municipality is rated on 4 dimensions: rent, schools, hospitals, crime.
- Each dimension is normalized to a 0.0 - 1.0 scale across all 308 Portuguese
  municipalities (1.0 = best on that dimension; 0.0 = worst).
- Rent and crime are inverted: lower rent and lower crime yield higher scores.
- Schools, hospitals and crime use natural-log smoothing before normalization
  so that large urban centres do not crush smaller municipalities.
- The final score is the weighted average:
    score = Σ(dim_score * weight) / Σ(weight)
  Each weight is selected by the user on a 0–3 slider in the Filters screen.
- Municipalities without official rent data are evaluated only by schools,
  hospitals and crime — the rent dimension is excluded from the calculation,
  not penalized.

Data sources and coverage:
- Rent: INE (Portuguese National Statistics Institute), quarterly release of
  median rent per square meter; only available for the 24 municipalities with
  more than 100,000 inhabitants (the remaining 284 have no rent data).
- Schools: official Ministry of Education data, latest available school year,
  308 municipalities.
- Hospitals: official 2024 data, 308 municipalities.
- Crime: official 2024 totals, 308 municipalities.

Screens of the app:
- Home: continent selector, mascot (Scopey) and shortcut to the AI assistant.
- Country list: only Portugal currently has data; other countries appear empty.
- Map: choropleth — colour intensity reflects the final score for each
  municipality (darker = higher score). Tap a polygon to see its metrics.
- Filters: 4 sliders (rent, schools, hospitals, crime) 0–3, each with an info
  icon explaining the dimension. There is no rent min/max anymore — only weight.
- Results: top-10 municipalities for the current weights, with star to favourite
  each one and a "back to search" button at the top.
- Comparison: pick multiple municipalities via checkboxes and compare side by
  side using the same weights and metrics.
- Price history: chart of median rent per m² over time for a chosen municipality
  (only available for the 24 with official data).
- Favourites: list of cities the user has starred (per-municipality, not per
  search).
- Search history: list of saved filter configurations from past sessions.

User journey:
- Pick continent on Home → choose Portugal → see the map → tap "Configure
  filters" to adjust weights → see results ranked → optionally compare or
  consult price history.

About me (Scopey):
- I am the in-app assistant. I answer in the user's app language. I do not
  invent data: if something is not in the context, I say so or stay generic.
"""


@router.post("/pergunta", response_model=AiQuestionResponse)
def perguntar_ia(payload: AiQuestionRequest):
    if not os.getenv("OPENAI_API_KEY"):
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY nao configurada.")

    app_language = resolve_language_name(payload.idioma_app)

    # Vai à BD buscar os dados reais. Se algo falhar não queremos partir o
    # endpoint: degradamos graciosamente para o contexto sem dados.
    try:
        municipio_data = fetch_municipio_data(payload.municipio) if payload.municipio else None
    except Exception:
        municipio_data = None

    try:
        overview_data = fetch_overview()
    except Exception:
        overview_data = {"overview": {}}

    contexto = f"""
App language: {app_language}
Country in focus: {payload.pais}
Municipality mentioned by user: {payload.municipio or "not specified"}

User question:
{payload.pergunta}

Current search context (weights chosen by the user, may be null):
- rent weight: {_fmt(payload.peso_renda)}
- schools weight: {_fmt(payload.peso_escolas)}
- hospitals weight: {_fmt(payload.peso_hospitais)}
- crime weight: {_fmt(payload.peso_criminalidade)}

{_format_municipio_block(municipio_data)}

{_format_overview_block(overview_data)}
""".strip()

    instructions = f"""
You are Scopey, the assistant inside the RentScope app.

Your job is to help the user with:
- specific municipalities (using the live data provided)
- score interpretation and how filters work
- rent, schools, hospitals and crime — both globally and for a given city
- choropleth map reading
- price history
- how to use the app (which screens do what)

Rules:
- Always answer in the app language given in the context.
- If the user sends only a greeting or a short message with no clear request,
  answer naturally, briefly and warmly.
- Only mention a specific city or country if the user mentioned it or asked
  about it. Do not volunteer city names unsolicited.
- When the user asks about a specific municipality, prefer the values from the
  "Specific municipality data" block. If those values are missing (no data),
  say so explicitly instead of inventing.
- When answering general questions ("which is cheapest?", "where are most
  hospitals?"), use the "Global overview" block. If the requested ranking is
  not in the overview, say what you know without making up numbers.
- Follow the RentScope reference below as ground truth: do not contradict it.
- Keep answers concise, clear and natural. Prefer short paragraphs over lists,
  unless a list clearly helps.

{APP_REFERENCE}
""".strip()

    try:
        response = client.responses.create(
            model="gpt-5-mini",
            input=[
                {"role": "system", "content": instructions},
                {"role": "user", "content": contexto},
            ],
        )

        return AiQuestionResponse(resposta=response.output_text.strip())

    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Erro ao consultar IA: {str(exc)}")
