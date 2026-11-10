"""Repete a avaliação com cache vazio para medir a variação entre execuções.

Uso: uv run python scripts/repeticoes.py [--n 2]      (chama a API; modelos :free)
Cada repetição usa uma pasta de cache própria (.cache/rep<i>) e refaz as 3 configurações nos 20
cardápios. Une com a execução original (reports/resultados_*.csv) em reports/repeticoes.json.
"""

import argparse
import csv
import json
import os
import subprocess
import sys
from pathlib import Path

from dotenv import find_dotenv, load_dotenv

RAIZ = Path(__file__).resolve().parents[1]
CONFIGS = ("zero_shot", "few_shot", "zero_shot_modelo_pequeno")
CAMPOS = ("f1_nomes", "acuracia_preco", "acuracia_categoria", "acuracia_status_alergenos")


def rodar_uma(rep: int) -> None:
    # Importa aqui, depois de o ambiente definir LLM_CACHE_DIR para esta repetição
    from evaluate import MODELO_PEQUENO, carregar_exemplos

    from project_nov26_p2_cardapios.extrator import extrair
    from project_nov26_p2_cardapios.llm import MODELO_PADRAO
    from project_nov26_p2_cardapios.metricas import avaliar, resumir_configuracao
    from project_nov26_p2_cardapios.schema import Cardapio

    configs = {
        "zero_shot": (MODELO_PADRAO, None),
        "few_shot": (MODELO_PADRAO, carregar_exemplos()),
        "zero_shot_modelo_pequeno": (MODELO_PEQUENO, None),
    }
    saida = {}
    for nome, (modelo, exemplos) in configs.items():
        linhas = []
        for gab in sorted((RAIZ / "data/gabarito").glob("*.json")):
            gabarito = Cardapio.model_validate_json(gab.read_text())
            texto = (RAIZ / "data/menus" / f"{gab.stem}.txt").read_text()
            extraido, meta = extrair(texto, exemplos, modelo)
            linhas.append({"menu": gab.stem, **avaliar(extraido, gabarito), **meta})
            print(f"rep{rep} {nome} {gab.stem}", flush=True)
        saida[nome] = {k: round(v, 3) for k, v in resumir_configuracao(linhas).items()}
    (RAIZ / f"reports/repeticao_{rep}.json").write_text(json.dumps(saida, indent=2))


def original() -> dict:
    from project_nov26_p2_cardapios.metricas import resumir_configuracao

    saida = {}
    for nome in CONFIGS:
        with open(RAIZ / f"reports/resultados_{nome}.csv") as f:
            linhas = []
            for r in csv.DictReader(f):
                linhas.append(
                    {
                        k: (v == "True")
                        if v in ("True", "False")
                        else (float(v) if "." in v else int(v))
                        for k, v in r.items()
                        if k != "menu"
                    }
                )
        saida[nome] = {k: round(v, 3) for k, v in resumir_configuracao(linhas).items()}
    return saida


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--n", type=int, default=2)
    p.add_argument("--rep", type=int, default=None, help="uso interno: roda só esta repetição")
    args = p.parse_args()
    load_dotenv(find_dotenv(".env.shared", usecwd=True))  # chave do OpenRouter
    load_dotenv(find_dotenv(".env", usecwd=True), override=True)
    sys.path.insert(0, str(RAIZ / "scripts"))
    if args.rep is not None:
        rodar_uma(args.rep)
        return
    for i in range(1, args.n + 1):
        env = {**os.environ, "LLM_CACHE_DIR": str(RAIZ / f".cache/rep{i}")}
        subprocess.run([sys.executable, __file__, "--rep", str(i)], cwd=RAIZ, env=env, check=True)
    execucoes = [original()] + [
        json.loads((RAIZ / f"reports/repeticao_{i}.json").read_text()) for i in range(1, args.n + 1)
    ]
    resumo = {
        nome: {
            campo: {
                "execucoes": [e[nome][campo] for e in execucoes],
                "min": min(e[nome][campo] for e in execucoes),
                "max": max(e[nome][campo] for e in execucoes),
            }
            for campo in CAMPOS
        }
        for nome in CONFIGS
    }
    (RAIZ / "reports/repeticoes.json").write_text(json.dumps(resumo, indent=2, ensure_ascii=False))
    print(json.dumps(resumo, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
