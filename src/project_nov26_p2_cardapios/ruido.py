"""Gera o texto "bagunçado" de um cardápio a partir do gabarito.

Partir do gabarito garante consistência por construção: tudo o que está no JSON
está dedutível do texto. O ruído imita cardápios reais (PDF, WhatsApp, foto
transcrita): formatos de preço variados, seções opcionais, abreviações,
alergênicos declarados por sinônimos e itens sem preço.
"""

import random

SINONIMOS_ALERGENO = {
    "gluten": ["glúten", "trigo", "gluten"],
    "lactose": ["lactose", "leite", "derivados de leite"],
    "ovo": ["ovo", "ovos"],
    "amendoim": ["amendoim"],
    "castanhas": ["castanhas", "nozes", "castanha de caju"],
    "soja": ["soja", "shoyu (soja)"],
    "peixe": ["peixe"],
    "frutos_do_mar": ["frutos do mar", "camarão", "crustáceos"],
}
TITULO_SECAO = {
    "entrada": ["ENTRADAS", "Para começar", "PORÇÕES"],
    "prato_principal": ["PRATOS PRINCIPAIS", "Pratos", "PRATOS DA CASA"],
    "lanche": ["LANCHES", "Sanduíches", "BURGERS & LANCHES"],
    "pizza": ["PIZZAS", "Pizzas (8 fatias)", "NOSSAS PIZZAS"],
    "sobremesa": ["SOBREMESAS", "Doces", "PRA ADOÇAR"],
    "bebida": ["BEBIDAS", "Bebidas", "PRA BEBER"],
    "combo": ["COMBOS", "Promoções", "COMBOS DO DIA"],
    "outro": ["OUTROS", "Adicionais", "EXTRAS"],
}
ABREVIACOES = {" com ": " c/ ", " sem ": " s/ ", " e ": " & ", "queijo": "qj", "molho": "mlh"}


def _preco(valor: float | None, rng: random.Random, estilo: int) -> str:
    if valor is None:
        return rng.choice(["consulte", "(preço sob consulta)", "—"])
    inteiro = float(valor).is_integer()
    reais, centavos = int(valor), round((valor - int(valor)) * 100)
    formatos = [
        f"R$ {reais},{centavos:02d}",
        f"{reais},{centavos:02d}".rstrip("0").rstrip(",")
        if centavos % 10 == 0
        else f"{reais},{centavos:02d}",
        f"R${reais}" if inteiro else f"R${reais},{centavos:02d}",
        f"{valor:.2f}",
        f"{reais} reais" if inteiro else f"{reais},{centavos:02d} reais",
    ]
    return formatos[estilo % len(formatos)]


def _alergenos(lista: list[str] | None, rng: random.Random) -> str:
    if lista is None:
        return ""
    if not lista:
        return rng.choice(["Sem alergênicos.", "Não contém alergênicos", "(livre de alergênicos)"])
    termos = [rng.choice(SINONIMOS_ALERGENO[a]) for a in lista]
    juntos = termos[0] if len(termos) == 1 else ", ".join(termos[:-1]) + " e " + termos[-1]
    return rng.choice(["Contém: {}.", "Alérgicos: contém {}", "⚠ {}"]).format(juntos)


def _abreviar(texto: str, rng: random.Random) -> str:
    for longo, curto in ABREVIACOES.items():
        if longo in texto and rng.random() < 0.5:
            texto = texto.replace(longo, curto)
    return texto


def renderizar(gabarito: dict, seed: int) -> str:
    rng = random.Random(seed)
    estilo_preco = rng.randrange(5)
    layout = rng.randrange(3)
    usa_secoes = rng.random() < 0.6
    marca_veg = any(i.get("vegetariano") is not None for i in gabarito["itens"])

    nome = gabarito["restaurante"]
    linhas = [rng.choice([nome.upper(), f"*** {nome} ***", f"Cardápio — {nome}"]), ""]
    if marca_veg:
        linhas += ["(V) = vegetariano", ""]

    itens = list(gabarito["itens"])
    if usa_secoes:
        ordem = list(dict.fromkeys(i["categoria"] for i in itens))
        grupos = [(c, [i for i in itens if i["categoria"] == c]) for c in ordem]
    else:
        grupos = [(None, itens)]

    for categoria, grupo in grupos:
        if categoria:
            linhas += [rng.choice(TITULO_SECAO[categoria]), ""]
        for item in grupo:
            nome_item = item["nome"].upper() if layout == 2 else item["nome"]
            if marca_veg and item.get("vegetariano"):
                nome_item += " (V)"
            desc = _abreviar(f" {item['descricao']} ", rng).strip() if item.get("descricao") else ""
            preco = _preco(item.get("preco"), rng, estilo_preco)
            alerg = _alergenos(item.get("alergenos"), rng)
            if layout == 0:
                linhas.append(f"{nome_item} {'.' * rng.randint(3, 8)} {preco}")
                if desc:
                    linhas.append(f"  ({desc})")
            elif layout == 1:
                partes = [nome_item, desc, preco] if desc else [nome_item, preco]
                linhas.append(" - ".join(partes))
            else:
                linhas += [nome_item] + ([f"  {desc}"] if desc else []) + [f"  {preco}"]
            if alerg:
                linhas.append(f"  {alerg}")
        linhas.append("")
    return "\n".join(linhas).rstrip() + "\n"
