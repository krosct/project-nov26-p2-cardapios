"""Comparação campo a campo entre a extração e o gabarito."""

import unicodedata
from difflib import SequenceMatcher

from project_nov26_p2_cardapios.schema import Cardapio, Item

LIMIAR_NOME = 0.85


def normalizar(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return " ".join(sem_acento.lower().replace("-", " ").split())


def casar_itens(extraidos: list[Item], gabarito: list[Item]) -> list[tuple[Item, Item]]:
    """Casamento guloso pelo nome normalizado (similaridade ≥ LIMIAR_NOME), um para um."""
    candidatos = sorted(
        (
            (SequenceMatcher(None, normalizar(e.nome), normalizar(g.nome)).ratio(), i, j)
            for i, e in enumerate(extraidos)
            for j, g in enumerate(gabarito)
        ),
        reverse=True,
    )
    usados_e, usados_g, pares = set(), set(), []
    for score, i, j in candidatos:
        if score < LIMIAR_NOME:
            break
        if i not in usados_e and j not in usados_g:
            usados_e.add(i)
            usados_g.add(j)
            pares.append((extraidos[i], gabarito[j]))
    return pares


def _f1(p: float, r: float) -> float:
    return 2 * p * r / (p + r) if p + r else 0.0


def avaliar(extraido: Cardapio | None, gabarito: Cardapio) -> dict:
    """Métricas de um cardápio. Extração inválida conta como nada extraído."""
    itens = extraido.itens if extraido else []
    pares = casar_itens(itens, gabarito.itens)

    precisao = len(pares) / len(itens) if itens else 0.0
    recall = len(pares) / len(gabarito.itens)

    precos_ok = sum(
        (e.preco is None and g.preco is None)
        or (e.preco is not None and g.preco is not None and abs(e.preco - g.preco) < 0.01)
        for e, g in pares
    )
    categorias_ok = sum(e.categoria == g.categoria for e, g in pares)

    # Alergênicos: "não informado" (None) tratado como conjunto vazio na contagem
    # micro, e a distinção None × lista medida à parte.
    vp = fp = fn = 0
    status_ok = 0
    for e, g in pares:
        pred, real = set(e.alergenos or []), set(g.alergenos or [])
        vp += len(pred & real)
        fp += len(pred - real)
        fn += len(real - pred)
        status_ok += (e.alergenos is None) == (g.alergenos is None)

    n = len(pares) or 1
    return {
        "json_valido": extraido is not None,
        "itens_gabarito": len(gabarito.itens),
        "itens_extraidos": len(itens),
        "itens_casados": len(pares),
        "precisao_nomes": precisao,
        "recall_nomes": recall,
        "f1_nomes": _f1(precisao, recall),
        "acuracia_preco": precos_ok / n,
        "acuracia_categoria": categorias_ok / n,
        "alergenos_vp": vp,
        "alergenos_fp": fp,
        "alergenos_fn": fn,
        "acuracia_status_alergenos": status_ok / n,
    }


def precisao_recall_alergenos(vp: int, fp: int, fn: int) -> tuple[float, float]:
    return (vp / (vp + fp) if vp + fp else 1.0, vp / (vp + fn) if vp + fn else 1.0)
