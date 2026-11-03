"""Avalia a extração nos 20 cardápios: zero-shot × few-shot.

Uso: uv run python scripts/evaluate.py   (requer OPENROUTER_API_KEY no ambiente ou no .env)
Saídas: reports/resultados_<config>.csv, reports/resumo.json, reports/erros.json
"""

import csv
import json
from pathlib import Path

from project_nov26_p2_cardapios.extrator import extrair
from project_nov26_p2_cardapios.llm import MODELO_PADRAO
from project_nov26_p2_cardapios.metricas import avaliar, casar_itens, precisao_recall_alergenos
from project_nov26_p2_cardapios.schema import Cardapio

RAIZ = Path(__file__).resolve().parents[1]
MODELO_PEQUENO = "liquid/lfm-2.5-2.6b:free"


def carregar_exemplos() -> list[tuple[str, dict]]:
    pasta = RAIZ / "data/exemplos_fewshot"
    return [
        (j.with_suffix(".txt").read_text(), json.loads(j.read_text()))
        for j in sorted(pasta.glob("*.json"))
    ]


def resumir(linhas: list[dict]) -> dict:
    n = len(linhas)
    vp, fp, fn = (
        sum(r[k] for r in linhas) for k in ("alergenos_vp", "alergenos_fp", "alergenos_fn")
    )
    p_alerg, r_alerg = precisao_recall_alergenos(vp, fp, fn)
    media = lambda k: sum(r[k] for r in linhas) / n  # noqa: E731
    return {
        "json_valido": media("json_valido"),
        "valido_na_1a_tentativa": sum(r["tentativas"] == 1 and r["json_valido"] for r in linhas)
        / n,
        "f1_nomes": media("f1_nomes"),
        "acuracia_preco": media("acuracia_preco"),
        "acuracia_categoria": media("acuracia_categoria"),
        "precisao_alergenos": p_alerg,
        "recall_alergenos": r_alerg,
        "acuracia_status_alergenos": media("acuracia_status_alergenos"),
        "latencia_media_s": media("latencia_s"),
        "tokens_entrada_medios": media("tokens_entrada"),
        "tokens_saida_medios": media("tokens_saida"),
    }


def coletar_erros(extraido: Cardapio | None, gabarito: Cardapio, menu: str) -> list[dict]:
    if extraido is None:
        return [{"menu": menu, "tipo": "json_invalido"}]
    erros = []
    for e, g in casar_itens(extraido.itens, gabarito.itens):
        if (e.preco is None) != (g.preco is None) or (
            e.preco is not None and g.preco is not None and abs(e.preco - g.preco) >= 0.01
        ):
            erros.append(
                {
                    "menu": menu,
                    "item": g.nome,
                    "tipo": "preco",
                    "extraido": e.preco,
                    "gabarito": g.preco,
                }
            )
        if set(e.alergenos or []) != set(g.alergenos or []) or (e.alergenos is None) != (
            g.alergenos is None
        ):
            erros.append(
                {
                    "menu": menu,
                    "item": g.nome,
                    "tipo": "alergenos",
                    "extraido": e.alergenos,
                    "gabarito": g.alergenos,
                }
            )
        if e.categoria != g.categoria:
            erros.append(
                {
                    "menu": menu,
                    "item": g.nome,
                    "tipo": "categoria",
                    "extraido": e.categoria,
                    "gabarito": g.categoria,
                }
            )
    return erros


def main() -> None:
    configs = {
        "zero_shot": (MODELO_PADRAO, None),
        "few_shot": (MODELO_PADRAO, carregar_exemplos()),
        "zero_shot_modelo_pequeno": (MODELO_PEQUENO, None),
    }
    resumo, todos_erros = {"modelo": MODELO_PADRAO, "modelo_pequeno": MODELO_PEQUENO}, {}
    for nome, (modelo, exemplos) in configs.items():
        linhas, erros = [], []
        for gab_path in sorted((RAIZ / "data/gabarito").glob("*.json")):
            gabarito = Cardapio.model_validate_json(gab_path.read_text())
            texto = (RAIZ / "data/menus" / f"{gab_path.stem}.txt").read_text()
            extraido, meta = extrair(texto, exemplos, modelo)
            linhas.append({"menu": gab_path.stem, **avaliar(extraido, gabarito), **meta})
            erros += coletar_erros(extraido, gabarito, gab_path.stem)
            f1 = linhas[-1]["f1_nomes"]
            print(f"{nome:9} {gab_path.stem}: f1={f1:.2f} tentativas={meta['tentativas']}")
        with open(RAIZ / f"reports/resultados_{nome}.csv", "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(linhas[0]))
            w.writeheader()
            w.writerows(linhas)
        resumo[nome] = {k: round(v, 3) for k, v in resumir(linhas).items()}
        todos_erros[nome] = erros
    (RAIZ / "reports/resumo.json").write_text(json.dumps(resumo, indent=2, ensure_ascii=False))
    (RAIZ / "reports/erros.json").write_text(json.dumps(todos_erros, indent=2, ensure_ascii=False))
    print(json.dumps(resumo, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
