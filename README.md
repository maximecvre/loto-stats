# Loto Toolkit

Télécharge, normalise et analyse l'historique officiel du LOTO® FDJ
(archives ZIP de https://www.fdj.fr/jeux-de-tirage/loto/historique).

## ⚠️ À lire avant de commencer

Le LOTO® est un tirage aléatoire équiprobable : chaque numéro a la même
probabilité à chaque tirage, indépendamment des tirages précédents.
**Aucun calcul sur l'historique ne peut prédire le prochain tirage** — ni
les "numéros en retard", ni les "numéros chauds". Cet outil sert à explorer
les données et à vérifier que le tirage est bien équilibré (test du chi²),
pas à générer des pronostics fiables.

## Consulter ça depuis ton téléphone, sans ordinateur

Le dossier contient aussi `generate_report.py` (génère une page web
autonome dans `site/index.html`) et `.github/workflows/report.yml` (fait
tourner tout le pipeline automatiquement 3 fois par semaine et publie la
page sur GitHub Pages). Suis **GITHUB_SETUP.md** pour une installation
guidée, 100% depuis un navigateur mobile.

## Installation (usage local, sur ordinateur)

```bash
pip install requests pandas scipy
```

## Utilisation

```bash
# Pipeline complet : téléchargement + normalisation + statistiques
python main.py

# Si tu as déjà téléchargé les archives et veux juste refaire les stats
python main.py --skip-download

# Forcer un nouveau téléchargement
python main.py --force
```

Chaque étape peut aussi être lancée séparément :

```bash
python download_loto.py     # -> data/raw/<periode>/*.csv
python normalize_loto.py    # -> data/loto_historique_normalise.csv
python stats_loto.py        # affiche le rapport de stats dans le terminal
```

## Utiliser les données dans tes propres calculs

```python
from stats_loto import load, number_frequencies, chance_frequencies, gaps_since_last_seen, most_common_pairs, theoretical_probabilities

df = load()
print(number_frequencies(df))          # fréquence de chaque numéro 1-49
print(chance_frequencies(df))          # fréquence de chaque numéro chance 1-10
print(gaps_since_last_seen(df))        # tirages écoulés depuis la dernière sortie
print(most_common_pairs(df, top_n=15)) # paires les plus fréquentes
print(theoretical_probabilities())     # probabilités exactes de gain à chaque rang
```

## Structure du schéma normalisé

| colonne | description |
|---|---|
| `date_tirage` | date du tirage |
| `boule_1` … `boule_5` | les 5 boules principales (1-49) |
| `numero_chance` | numéro Chance (1-10), tirages récents |
| `numero_complementaire` | équivalent ancien format, avant 2017 |
| `id_tirage` | identifiant / numéro du tirage |
| `source` | période d'origine du fichier |
| `extra_*` | colonnes non reconnues automatiquement (gains par rang, etc.), conservées telles quelles |

Si FDJ modifie un format de colonnes et qu'un champ finit en `extra_...`
alors qu'il ne devrait pas, ajoute simplement un mot-clé dans la fonction
`_map_columns()` de `normalize_loto.py` — le script imprime justement la
liste des colonnes non reconnues à chaque exécution pour repérer ce cas.

## Limite technique connue

Les URLs des ZIP sont codées dans `download_loto.py`, copiées depuis la
page FDJ à la date de génération de cet outil. Si FDJ change ses liens,
va rechercher les nouvelles URLs sur
https://www.fdj.fr/jeux-de-tirage/loto/historique et remplace-les dans
`LOTO_ARCHIVES`.
