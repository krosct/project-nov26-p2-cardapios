"""Gera o texto "bagunçado" de um cardápio a partir do gabarito.

Partir do gabarito garante consistência por construção: tudo o que está no JSON
está dedutível do texto. O ruído imita cardápios reais (PDF, WhatsApp, foto
transcrita): formatos de preço variados, seções opcionais, abreviações,
alergênicos declarados por sinônimos e itens sem preço.
"""

import random

# Como cada alergênico pode ser escrito no texto (sinônimos)
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
# Títulos de seção possíveis para cada categoria
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
# Trocas de abreviação aplicadas com 50% de chance cada, na descrição
ABREVIACOES = {" com ": " c/ ", " sem ": " s/ ", " e ": " & ", "queijo": "qj", "molho": "mlh"}


def _preco(valor: float | None, rng: random.Random, estilo: int) -> str:
    # Sem preço: escolhe um texto qualquer de "sem preço"
    if valor is None:
        return rng.choice(["consulte", "(preço sob consulta)", "—"])
    inteiro = float(valor).is_integer()  # Preço sem centavos?
    reais, centavos = int(valor), round((valor - int(valor)) * 100)
    # Cinco formatos diferentes de escrever o mesmo preço; "estilo" escolhe um
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
    if lista is None:  # None = cardápio não diz nada: não escreve nada
        return ""
    if not lista:  # Lista vazia = cardápio declara que não há alergênicos
        return rng.choice(["Sem alergênicos.", "Não contém alergênicos", "(livre de alergênicos)"])
    # Troca cada alergênico por um sinônimo sorteado
    termos = [rng.choice(SINONIMOS_ALERGENO[a]) for a in lista]
    # Junta os termos em português: "a, b e c"
    juntos = termos[0] if len(termos) == 1 else ", ".join(termos[:-1]) + " e " + termos[-1]
    return rng.choice(["Contém: {}.", "Alérgicos: contém {}", "⚠ {}"]).format(juntos)


def _abreviar(texto: str, rng: random.Random) -> str:
    # Para cada abreviação, aplica com 50% de chance
    for longo, curto in ABREVIACOES.items():
        if longo in texto and rng.random() < 0.5:
            texto = texto.replace(longo, curto)
    return texto


def renderizar(gabarito: dict, seed: int) -> str:
    rng = random.Random(seed)  # Semente fixa: mesmo gabarito + seed gera sempre o mesmo texto
    estilo_preco = rng.randrange(5)  # Formato de preço usado no cardápio inteiro
    layout = rng.randrange(3)  # Layout dos itens (pontilhado, traço ou bloco)
    usa_secoes = rng.random() < 0.6  # 60% dos cardápios têm seções por categoria
    # Só mostra a legenda (V) se o cardápio marca algum vegetariano
    marca_veg = any(i.get("vegetariano") is not None for i in gabarito["itens"])

    nome = gabarito["restaurante"]
    # Cabeçalho com o nome do restaurante em um dos três estilos
    linhas = [rng.choice([nome.upper(), f"*** {nome} ***", f"Cardápio — {nome}"]), ""]
    if marca_veg:
        linhas += ["(V) = vegetariano", ""]

    itens = list(gabarito["itens"])
    if usa_secoes:  # Agrupa os itens por categoria, na ordem em que aparecem
        ordem = list(dict.fromkeys(i["categoria"] for i in itens))
        grupos = [(c, [i for i in itens if i["categoria"] == c]) for c in ordem]
    else:  # Sem seções: um único grupo com todos os itens
        grupos = [(None, itens)]

    for categoria, grupo in grupos:
        if categoria:  # Escreve o título da seção, se houver
            linhas += [rng.choice(TITULO_SECAO[categoria]), ""]
        for item in grupo:
            # Layout 2 escreve o nome em caixa alta
            nome_item = item["nome"].upper() if layout == 2 else item["nome"]
            if marca_veg and item.get("vegetariano"):  # Marca vegetariano com (V)
                nome_item += " (V)"
            # Descrição com abreviações aleatórias (strip remove o espaço extra)
            desc = _abreviar(f" {item['descricao']} ", rng).strip() if item.get("descricao") else ""
            preco = _preco(item.get("preco"), rng, estilo_preco)
            alerg = _alergenos(item.get("alergenos"), rng)
            if layout == 0:  # Nome com pontilhado até o preço, descrição em linha abaixo
                linhas.append(f"{nome_item} {'.' * rng.randint(3, 8)} {preco}")
                if desc:
                    linhas.append(f"  ({desc})")
            elif layout == 1:  # Tudo numa linha, separado por " - "
                partes = [nome_item, desc, preco] if desc else [nome_item, preco]
                linhas.append(" - ".join(partes))
            else:  # Bloco: nome, descrição e preco em linhas separadas
                linhas += [nome_item] + ([f"  {desc}"] if desc else []) + [f"  {preco}"]
            if alerg:  # Linha de alergênicos, se o cardápio informa
                linhas.append(f"  {alerg}")
        linhas.append("")  # Linha em branco entre seções
    # Junta tudo, remove espaços finais e garante uma quebra de linha no fim
    return "\n".join(linhas).rstrip() + "\n"
