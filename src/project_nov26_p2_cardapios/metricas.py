"""Comparação campo a campo entre a extração e o gabarito."""

import unicodedata
from difflib import SequenceMatcher

from project_nov26_p2_cardapios.schema import Cardapio, Item

# Similaridade mínima (0 a 1) para dois nomes de item serem considerados o mesmo
LIMIAR_NOME = 0.85


def normalizar(texto: str) -> str:
    # Remove acentos, põe em minúsculas, troca "-" por espaço e colapsa espaços repetidos
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return " ".join(sem_acento.lower().replace("-", " ").split())


def casar_itens(extraidos: list[Item], gabarito: list[Item]) -> list[tuple[Item, Item]]:
    """Casamento guloso pelo nome normalizado (similaridade ≥ LIMIAR_NOME), um para um."""
    # Lista todas as combinações (extraído, gabarito) com a similaridade, da maior para a menor
    candidatos = sorted(
        (
            (SequenceMatcher(None, normalizar(e.nome), normalizar(g.nome)).ratio(), i, j)
            for i, e in enumerate(extraidos)
            for j, g in enumerate(gabarito)
        ),
        reverse=True,
    )
    usados_e, usados_g, pares = set(), set(), []  # Índices já pareados e a lista de pares
    for score, i, j in candidatos:
        if score < LIMIAR_NOME:  # Como está ordenado, o resto também fica abaixo do limiar
            break
        if i not in usados_e and j not in usados_g:  # Garante pareamento um para um
            usados_e.add(i)
            usados_g.add(j)
            pares.append((extraidos[i], gabarito[j]))
    return pares


def _f1(p: float, r: float) -> float:
    # Média harmônica entre precisão e recall; 0 se ambos forem 0
    return 2 * p * r / (p + r) if p + r else 0.0


def avaliar(extraido: Cardapio | None, gabarito: Cardapio) -> dict:
    """Métricas de um cardápio. Extração inválida conta como nada extraído."""
    itens = extraido.itens if extraido else []  # Extração inválida vira lista vazia
    pares = casar_itens(itens, gabarito.itens)  # Pares de itens equivalentes

    precisao = len(pares) / len(itens) if itens else 0.0  # Dos extraídos, quantos existem
    recall = len(pares) / len(gabarito.itens)  # Do gabarito, quantos foram achados

    precos_ok = sum(  # Preço certo: ambos sem preço, ou ambos com preço igual (±0,01)
        (e.preco is None and g.preco is None)
        or (e.preco is not None and g.preco is not None and abs(e.preco - g.preco) < 0.01)
        for e, g in pares
    )
    categorias_ok = sum(e.categoria == g.categoria for e, g in pares)  # Categoria igual

    # Alergênicos: "não informado" (None) tratado como conjunto vazio na contagem
    # micro, e a distinção None × lista medida à parte.
    vp = fp = fn = 0  # Verdadeiros positivos, falsos positivos e falsos negativos
    status_ok = 0  # Pares em que None × lista coincide
    for e, g in pares:
        pred, real = set(e.alergenos or []), set(g.alergenos or [])
        vp += len(pred & real)  # Alergênicos previstos e corretos
        fp += len(pred - real)  # Previstos mas não existem no gabarito
        fn += len(real - pred)  # Existem no gabarito mas não foram previstos
        status_ok += (e.alergenos is None) == (g.alergenos is None)

    n = len(pares) or 1  # Divisor para médias por par (evita divisão por zero)
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
    # Precisão e recall micro; sem previsões (ou sem positivos reais) vale 1,0 por convenção
    return (vp / (vp + fp) if vp + fp else 1.0, vp / (vp + fn) if vp + fn else 1.0)


def resumir_configuracao(linhas: list[dict]) -> dict:
    """Resume uma configuração a partir das linhas por cardápio.

    Métricas por item (nomes, preço, categoria, status de alergênicos) são MICRO: somam os
    itens de todos os cardápios, de modo que "0,61" significa 61% dos itens casados.
    Validade do JSON e tentativas são frações dos cardápios; latência e tokens, médias por cardápio.
    """
    n = len(linhas)
    casados = sum(r["itens_casados"] for r in linhas)
    extraidos = sum(r["itens_extraidos"] for r in linhas)
    gabarito = sum(r["itens_gabarito"] for r in linhas)
    vp, fp, fn = (
        sum(r[k] for r in linhas) for k in ("alergenos_vp", "alergenos_fp", "alergenos_fn")
    )
    p_alerg, r_alerg = precisao_recall_alergenos(vp, fp, fn)
    p_nomes = casados / extraidos if extraidos else 0.0
    r_nomes = casados / gabarito
    por_item = lambda campo: sum(r[campo] * r["itens_casados"] for r in linhas) / (casados or 1)  # noqa: E731
    media = lambda k: sum(r[k] for r in linhas) / n  # noqa: E731
    return {
        "json_valido": media("json_valido"),
        "valido_na_1a_tentativa": sum(r["tentativas"] == 1 and r["json_valido"] for r in linhas)
        / n,
        "itens_casados": casados,
        "itens_gabarito": gabarito,
        "f1_nomes": _f1(p_nomes, r_nomes),
        "acuracia_preco": por_item("acuracia_preco"),
        "acuracia_categoria": por_item("acuracia_categoria"),
        "precisao_alergenos": p_alerg,
        "recall_alergenos": r_alerg,
        "acuracia_status_alergenos": por_item("acuracia_status_alergenos"),
        "latencia_media_s": media("latencia_s"),
        "tokens_entrada_medios": media("tokens_entrada"),
        "tokens_saida_medios": media("tokens_saida"),
    }
