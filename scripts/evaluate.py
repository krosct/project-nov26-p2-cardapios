"""Avalia a extração nos 20 cardápios: zero-shot × few-shot.

Uso: uv run python scripts/evaluate.py   (requer OPENROUTER_API_KEY no ambiente ou no .env)
Saídas: reports/resultados_<config>.csv, reports/resumo.json, reports/erros.json
"""

import csv
import json
from pathlib import Path

from project_nov26_p2_cardapios.extrator import extrair
from project_nov26_p2_cardapios.llm import MODELO_PADRAO
from project_nov26_p2_cardapios.metricas import avaliar, casar_itens, resumir_configuracao
from project_nov26_p2_cardapios.schema import Cardapio

RAIZ = Path(__file__).resolve().parents[1]  # Raiz do projeto (pasta acima de scripts/)
MODELO_PEQUENO = "liquid/lfm-2.5-2.6b:free"  # Modelo pequeno, usado na comparação de custo/erro


def carregar_exemplos() -> list[tuple[str, dict]]:
    # Carrega os pares (texto, JSON) de exemplo para o prompt few-shot
    pasta = RAIZ / "data/exemplos_fewshot"
    return [
        (j.with_suffix(".txt").read_text(), json.loads(j.read_text()))
        for j in sorted(pasta.glob("*.json"))
    ]


def coletar_erros(extraido: Cardapio | None, gabarito: Cardapio, menu: str) -> list[dict]:
    # Lista os erros item a item, para inspeção manual em reports/erros.json
    if extraido is None:  # JSON inválido: um único erro para o cardápio inteiro
        return [{"menu": menu, "tipo": "json_invalido"}]
    erros = []
    for e, g in casar_itens(extraido.itens, gabarito.itens):  # Só compara itens casados
        # Erro de preço: um tem preço e o outro não, ou os valores diferem em 0,01 ou mais
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
        # Erro de alergênicos: conjuntos diferentes, ou None × lista
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
        if e.categoria != g.categoria:  # Erro de categoria
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
    # As três configurações comparadas: (modelo, exemplos few-shot ou None)
    configs = {
        "zero_shot": (MODELO_PADRAO, None),
        "few_shot": (MODELO_PADRAO, carregar_exemplos()),
        "zero_shot_modelo_pequeno": (MODELO_PEQUENO, None),
    }
    # Acumuladores do resumo geral e dos erros de todas as configurações
    resumo, todos_erros = {"modelo": MODELO_PADRAO, "modelo_pequeno": MODELO_PEQUENO}, {}
    for nome, (modelo, exemplos) in configs.items():
        linhas, erros = [], []  # Resultados e erros de uma configuração
        for gab_path in sorted((RAIZ / "data/gabarito").glob("*.json")):
            gabarito = Cardapio.model_validate_json(gab_path.read_text())  # Gabarito certo
            texto = (RAIZ / "data/menus" / f"{gab_path.stem}.txt").read_text()  # Entrada ruidosa
            extraido, meta = extrair(texto, exemplos, modelo)  # Chama o LLM
            # Uma linha por cardápio: métricas + metadados de tentativas/latência/tokens
            linhas.append({"menu": gab_path.stem, **avaliar(extraido, gabarito), **meta})
            erros += coletar_erros(extraido, gabarito, gab_path.stem)
            f1 = linhas[-1]["f1_nomes"]
            print(f"{nome:9} {gab_path.stem}: f1={f1:.2f} tentativas={meta['tentativas']}")
        # Grava o CSV detalhado por cardápio desta configuração
        with open(RAIZ / f"reports/resultados_{nome}.csv", "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(linhas[0]))
            w.writeheader()
            w.writerows(linhas)
        # Guarda o resumo arredondado (3 casas) desta configuração
        resumo[nome] = {k: round(v, 3) for k, v in resumir_configuracao(linhas).items()}
        todos_erros[nome] = erros
    # Grava os relatórios finais em JSON (resumo e erros)
    (RAIZ / "reports/resumo.json").write_text(json.dumps(resumo, indent=2, ensure_ascii=False))
    (RAIZ / "reports/erros.json").write_text(json.dumps(todos_erros, indent=2, ensure_ascii=False))
    print(json.dumps(resumo, indent=2, ensure_ascii=False))


if __name__ == "__main__":  # Só executa main() quando o arquivo é rodado diretamente
    main()
