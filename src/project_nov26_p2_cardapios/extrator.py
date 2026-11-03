"""Extração: texto de cardápio → `Cardapio` validado, com nova tentativa em caso de erro."""

import json
import re

from pydantic import ValidationError

from project_nov26_p2_cardapios.llm import MODELO_PADRAO, chamar_llm
from project_nov26_p2_cardapios.schema import Cardapio

INSTRUCOES = """Você extrai cardápios de restaurantes para JSON.

Regras:
- Devolva SOMENTE um JSON válido no esquema abaixo, sem texto antes ou depois.
- Um item por produto vendido. Não invente itens.
- preco: número em reais (ex.: 32.9). Se o cardápio não informa o preço, use null.
- categoria: uma das opções do esquema, deduzida da seção ou do nome do item.
- descricao: os ingredientes/descrição que aparecem no cardápio, ou null.
- alergenos: SOMENTE se o cardápio DECLARA alergênicos para o item. Converta sinônimos
  (leite/laticínios → lactose; trigo → gluten; camarão/frutos do mar → frutos_do_mar;
  nozes/castanha → castanhas; shoyu → soja; ovos → ovo).
  Se o cardápio declara que o item não tem alergênicos, use [].
  Se o cardápio não diz nada sobre alergênicos, use null — NÃO deduza pelos ingredientes.
- vegetariano: true/false somente se o cardápio marca itens vegetarianos; senão null.

Esquema:
"""


def montar_prompt(texto: str, exemplos: list[tuple[str, dict]] | None = None) -> list[dict]:
    esquema = json.dumps(Cardapio.model_json_schema(), ensure_ascii=False)
    mensagens = [{"role": "system", "content": INSTRUCOES + esquema}]
    for texto_ex, json_ex in exemplos or []:
        mensagens += [
            {"role": "user", "content": texto_ex},
            {"role": "assistant", "content": json.dumps(json_ex, ensure_ascii=False)},
        ]
    mensagens.append({"role": "user", "content": texto})
    return mensagens


def limpar_cercas(texto: str) -> str:
    """Remove cercas de código (```json ... ```) que alguns modelos adicionam."""
    m = re.search(r"```(?:json)?\s*(.*?)```", texto, flags=re.DOTALL)
    return (m.group(1) if m else texto).strip()


def extrair(
    texto: str,
    exemplos: list[tuple[str, dict]] | None = None,
    modelo: str = MODELO_PADRAO,
    max_tentativas: int = 3,
) -> tuple[Cardapio | None, dict]:
    """Retorna (cardápio ou None, metadados: tentativas, latência e tokens acumulados)."""
    mensagens = montar_prompt(texto, exemplos)
    meta = {"tentativas": 0, "latencia_s": 0.0, "tokens_entrada": 0, "tokens_saida": 0}
    for _ in range(max_tentativas):
        r = chamar_llm(mensagens, modelo)
        meta["tentativas"] += 1
        meta["latencia_s"] += r["latencia_s"]
        meta["tokens_entrada"] += r["tokens_entrada"] or 0
        meta["tokens_saida"] += r["tokens_saida"] or 0
        try:
            return Cardapio.model_validate_json(limpar_cercas(r["texto"])), meta
        except ValidationError as erro:
            mensagens = mensagens + [
                {"role": "assistant", "content": r["texto"]},
                {
                    "role": "user",
                    "content": f"O JSON é inválido:\n{erro}\nDevolva somente o JSON corrigido.",
                },
            ]
    return None, meta
