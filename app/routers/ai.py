import os
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from openai import OpenAI

router = APIRouter(prefix="/ai", tags=["ai"])

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

class AiQuestionRequest(BaseModel):
    pais: str
    municipio: Optional[str] = None
    pergunta: str
    renda: Optional[float] = None
    escolas: Optional[float] = None
    hospitais: Optional[float] = None
    criminalidade: Optional[float] = None
    score: Optional[float] = None

class AiQuestionResponse(BaseModel):
    resposta: str

@router.post("/pergunta", response_model=AiQuestionResponse)
def perguntar_ia(payload: AiQuestionRequest):
    if not os.getenv("OPENAI_API_KEY"):
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY não configurada.")

    contexto = f"""
País: {payload.pais}
Município: {payload.municipio or "não informado"}
Pergunta do utilizador: {payload.pergunta}

Dados disponíveis do local:
- score: {payload.score}
- renda: {payload.renda}
- escolas: {payload.escolas}
- hospitais: {payload.hospitais}
- criminalidade: {payload.criminalidade}
"""

instrucoes = """
Tu és o assistente inteligente do app RentScope.

REGRAS:
- Responde SEM pedir mais dados
- Usa o contexto fornecido (mesmo que incompleto)
- Se faltarem dados, responde de forma geral
- NÃO digas que faltam dados
- Dá sempre uma resposta útil

IDIOMA:
- Responde no mesmo idioma da pergunta do utilizador

Estilo:
- direto, claro e útil
- máximo 4–5 linhas

Objetivo:
Ajudar alguém que quer decidir se vale a pena viver naquele local.
"""

    try:
        response = client.responses.create(
            model="gpt-5.4",
            input=[
                {"role": "system", "content": instrucoes},
                {"role": "user", "content": contexto},
            ],
        )

        return AiQuestionResponse(resposta=response.output_text.strip())

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao consultar IA: {str(e)}")