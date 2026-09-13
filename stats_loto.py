"""
stats_loto.py
-------------
Calculs statistiques sur l'historique normalisé du LOTO®.

IMPORTANT (à lire avant d'utiliser ces chiffres) :
Le LOTO® est un tirage aléatoire équiprobable : à chaque tirage, chaque boule
a exactement la même probabilité de sortir (1/49, puis 1/10 pour le numéro
Chance), INDÉPENDAMMENT des tirages précédents. Aucune analyse statistique
de l'historique ne peut donc prédire le prochain tirage : un numéro "en
retard" n'a pas plus de chance de sortir, un numéro "chaud" n'en a pas moins.

Ce module sert à :
  - vérifier que le tirage est bien équilibré (test du chi²)
  - explorer l'historique par curiosité (fréquences, écarts, paires)
  - calculer la probabilité mathématique exacte de gain à chaque rang
Il ne sert PAS à prédire un tirage futur.
"""

from itertools import combinations
from math import comb
from pathlib import Path

import numpy as np
import pandas as pd

DATA_FILE = Path(__file__).parent / "data" / "loto_historique_normalise.csv"

MAIN_RANGE = range(1, 50)   # boules 1 à 49
CHANCE_RANGE = range(1, 11)  # numéro chance 1 à 10
BALL_COLS = [f"boule_{i}" for i in range(1, 6)]


def load() -> pd.DataFrame:
    if not DATA_FILE.exists():
        raise FileNotFoundError("Lance d'abord normalize_loto.py pour générer les données.")
    df = pd.read_csv(DATA_FILE, parse_dates=["date_tirage"])
    return df


def number_frequencies(df: pd.DataFrame) -> pd.Series:
    """Nombre de fois où chaque boule (1-49) est sortie, toutes positions confondues."""
    cols = [c for c in BALL_COLS if c in df.columns]
    all_draws = pd.concat([df[c] for c in cols])
    freq = all_draws.value_counts().reindex(MAIN_RANGE, fill_value=0).sort_index()
    freq.index.name = "numero"
    freq.name = "nb_sorties"
    return freq


def chance_frequencies(df: pd.DataFrame) -> pd.Series:
    if "numero_chance" not in df.columns:
        return pd.Series(dtype=int)
    freq = df["numero_chance"].value_counts().reindex(CHANCE_RANGE, fill_value=0).sort_index()
    freq.index.name = "numero_chance"
    freq.name = "nb_sorties"
    return freq


def gaps_since_last_seen(df: pd.DataFrame) -> pd.Series:
    """Nombre de tirages écoulés depuis la dernière sortie de chaque numéro (0 = sorti au dernier tirage)."""
    cols = [c for c in BALL_COLS if c in df.columns]
    df_sorted = df.sort_values("date_tirage").reset_index(drop=True)
    last_seen_index = {n: None for n in MAIN_RANGE}
    for idx, row in df_sorted.iterrows():
        for c in cols:
            n = row[c]
            if pd.notna(n):
                last_seen_index[int(n)] = idx
    total_draws = len(df_sorted)
    gaps = {
        n: (total_draws - 1 - idx if idx is not None else None)
        for n, idx in last_seen_index.items()
    }
    s = pd.Series(gaps, name="tirages_depuis_derniere_sortie").sort_index()
    s.index.name = "numero"
    return s


def most_common_pairs(df: pd.DataFrame, top_n: int = 10) -> pd.DataFrame:
    """Paires de numéros les plus fréquemment sorties ensemble dans un même tirage."""
    cols = [c for c in BALL_COLS if c in df.columns]
    counter: dict[tuple[int, int], int] = {}
    for _, row in df.iterrows():
        nums = sorted(int(row[c]) for c in cols if pd.notna(row[c]))
        for pair in combinations(nums, 2):
            counter[pair] = counter.get(pair, 0) + 1
    result = pd.DataFrame(
        [(a, b, count) for (a, b), count in counter.items()],
        columns=["numero_1", "numero_2", "nb_fois_ensemble"],
    ).sort_values("nb_fois_ensemble", ascending=False)
    return result.head(top_n).reset_index(drop=True)


def chi_square_uniformity(freq: pd.Series) -> dict:
    """
    Teste si la distribution observée est compatible avec un tirage uniforme.
    Une p-value élevée (proche de 1) confirme ce que l'on attend d'un tirage
    équitable : les écarts de fréquence entre numéros sont dus au hasard, pas
    à un biais. Ça ne donne AUCUNE indication sur le futur.
    """
    try:
        from scipy.stats import chisquare
    except ImportError:
        return {"error": "scipy non installé (pip install scipy) — test ignoré"}

    stat, p_value = chisquare(freq.values)
    return {
        "chi2_statistic": float(stat),
        "p_value": float(p_value),
        "interpretation": (
            "p_value élevée => rien n'indique un biais, cohérent avec un tirage aléatoire équitable."
            if p_value > 0.05
            else "p_value faible => écart notable par rapport à l'uniformité (à examiner, "
                 "mais reste possible par simple hasard sur un grand nombre de tirages)."
        ),
    }


def theoretical_probabilities() -> pd.DataFrame:
    """
    Probabilités mathématiques EXACTES de gain au LOTO® (5 numéros parmi 49 +
    1 numéro Chance parmi 10). Ces chiffres sont valables pour CHAQUE tirage,
    tout le temps, et ne dépendent d'aucun historique.
    """
    total_grids = comb(49, 5) * 10  # combinaisons de boules x numéro chance
    rows = []
    for good_balls in range(5, -1, -1):
        for chance_match in (True, False):
            ways_balls = comb(5, good_balls) * comb(44, 5 - good_balls)
            ways_chance = 1 if chance_match else 9
            ways = ways_balls * ways_chance
            proba = ways / total_grids
            rows.append({
                "bonnes_boules": good_balls,
                "bon_numero_chance": chance_match,
                "combinaisons_gagnantes": ways,
                "probabilite": proba,
                "1_chance_sur": round(1 / proba) if proba > 0 else None,
            })
    return pd.DataFrame(rows)


def composite_scores(df: pd.DataFrame) -> pd.Series:
    """
    Combine plusieurs signaux historiques (fréquence, écart, affinité de
    paires) en un score composite par numéro (1-49). Un score plus élevé
    pèse plus lourd dans un tirage pondéré sans remise, mais ceci reste,
    mathématiquement, équivalent à un tirage uniforme : le prochain tirage
    ne dépend en rien de l'historique.
    """
    freq = number_frequencies(df)
    gaps = gaps_since_last_seen(df).fillna(0)
    all_pairs = most_common_pairs(df, top_n=10**6)  # toutes les paires observées

    def normalize(s: pd.Series) -> pd.Series:
        lo, hi = s.min(), s.max()
        if hi == lo:
            return pd.Series(0.5, index=s.index)
        return (s - lo) / (hi - lo)

    pair_weight = pd.Series(0.0, index=freq.index)
    for row in all_pairs.itertuples():
        pair_weight[row.numero_1] += row.nb_fois_ensemble
        pair_weight[row.numero_2] += row.nb_fois_ensemble

    score = 0.4 * normalize(freq) + 0.3 * normalize(gaps) + 0.3 * normalize(pair_weight)
    return score


def weighted_sample(weights: dict, k: int, rng: "np.random.Generator | None" = None) -> list[int]:
    """Tire k éléments sans remise, avec une probabilité proportionnelle aux poids fournis."""
    if rng is None:
        rng = np.random.default_rng()
    items = list(weights.keys())
    w = np.array([max(float(weights[i]), 0.0) for i in items])
    if w.sum() == 0:
        w = np.ones_like(w)
    p = w / w.sum()
    chosen_idx = rng.choice(len(items), size=k, replace=False, p=p)
    return sorted(int(items[i]) for i in chosen_idx)


def technique_grids(df: pd.DataFrame, rng: "np.random.Generator | None" = None) -> list[dict]:
    """
    Génère quelques grilles selon des techniques "classiques" (fréquence,
    écarts, paires fréquentes). Mathématiquement, chacune de ces grilles a
    exactement la même probabilité de gagner qu'une grille tirée uniformément
    au hasard : le prochain tirage est indépendant de tout ce qui précède.
    Fourni à titre exploratoire/ludique, pas comme un outil de prédiction.
    """
    if rng is None:
        rng = np.random.default_rng()

    freq = number_frequencies(df)
    chance_freq = chance_frequencies(df)
    gaps = gaps_since_last_seen(df).fillna(0)
    pairs = most_common_pairs(df, top_n=1)

    def pick_chance():
        if chance_freq.empty:
            return None
        return weighted_sample(chance_freq.to_dict(), 1, rng)[0]

    grids = []

    grids.append({
        "label": "Fréquence — numéros les plus sortis",
        "balls": weighted_sample(freq.to_dict(), 5, rng),
        "chance": pick_chance(),
    })

    grids.append({
        "label": "Écarts — numéros \"en retard\"",
        "balls": weighted_sample(gaps.to_dict(), 5, rng),
        "chance": pick_chance(),
    })

    if not pairs.empty:
        n1, n2 = int(pairs.iloc[0]["numero_1"]), int(pairs.iloc[0]["numero_2"])
        remaining = {n: w for n, w in freq.to_dict().items() if n not in (n1, n2)}
        rest = weighted_sample(remaining, 3, rng)
        grids.append({
            "label": f"Paire fréquente ({n1:02d}-{n2:02d}) + complément",
            "balls": sorted([n1, n2] + rest),
            "chance": pick_chance(),
        })

    return grids


def summary_report() -> None:
    df = load()
    print(f"Tirages chargés : {len(df)} (du {df['date_tirage'].min().date()} "
          f"au {df['date_tirage'].max().date()})\n")

    freq = number_frequencies(df)
    print("Top 5 numéros les plus sortis :")
    print(freq.sort_values(ascending=False).head(5).to_string())
    print("\nTop 5 numéros les moins sortis :")
    print(freq.sort_values().head(5).to_string())

    chance_freq = chance_frequencies(df)
    if not chance_freq.empty:
        print("\nFréquence des numéros Chance :")
        print(chance_freq.to_string())

    print("\nTest d'équilibre (chi²) sur les boules principales :")
    print(chi_square_uniformity(freq))

    print("\nProbabilités théoriques (valables à chaque tirage, indépendamment de l'historique) :")
    print(theoretical_probabilities().to_string(index=False))

    print("\nRappel : ces statistiques décrivent le PASSÉ. Le tirage suivant est un "
          "événement indépendant ; aucune fréquence ou écart passé n'augmente ou "
          "ne diminue la probabilité d'un numéro au prochain tirage.")


if __name__ == "__main__":
    summary_report()
