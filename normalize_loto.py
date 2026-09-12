"""
normalize_loto.py
------------------
Les fichiers d'historique FDJ ont changé de format plusieurs fois depuis 1976
(noms de colonnes, séparateur, encodage, présence ou non d'un "numéro
complémentaire" avant l'introduction du numéro Chance en 2017...).

Plutôt que de coder en dur des noms de colonnes exacts (risqué : un seul
changement de libellé casse tout), ce module détecte les colonnes par
mots-clés (boule, chance, complémentaire, date...) et les fait correspondre
à un schéma normalisé unique :

    date_tirage | boule_1 | boule_2 | boule_3 | boule_4 | boule_5 |
    numero_chance | numero_complementaire | id_tirage | source

Toute colonne non reconnue est conservée telle quelle (préfixée "extra_")
pour ne rien perdre, et un rapport de correspondance est affiché pour que
tu puisses vérifier / corriger si un format inhabituel apparaît.
"""

import re
import unicodedata
from pathlib import Path

import pandas as pd

RAW_DIR = Path(__file__).parent / "data" / "raw"
OUT_FILE = Path(__file__).parent / "data" / "loto_historique_normalise.csv"

MAIN_BALL_COUNT = 5  # LOTO® actuel : 5 boules (1-49) + 1 numéro Chance (1-10)


def _strip_accents(text: str) -> str:
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def _clean_col(col: str) -> str:
    col = _strip_accents(str(col)).lower().strip()
    col = re.sub(r"[^a-z0-9]+", "_", col).strip("_")
    return col


def _read_csv_robust(path: Path) -> pd.DataFrame:
    """Essaie plusieurs séparateurs/encodages, comme les archives FDJ varient dans le temps."""
    last_error = None
    for encoding in ("utf-8-sig", "latin-1", "cp1252"):
        try:
            df = pd.read_csv(path, sep=None, engine="python", encoding=encoding, dtype=str)
            if df.shape[1] > 1:  # séparateur correctement détecté
                return df
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            continue
    # dernier recours : séparateur ';' forcé (le plus courant chez FDJ)
    for encoding in ("utf-8-sig", "latin-1", "cp1252"):
        try:
            return pd.read_csv(path, sep=";", encoding=encoding, dtype=str)
        except Exception as exc:  # noqa: BLE001
            last_error = exc
    raise RuntimeError(f"Impossible de lire {path}: {last_error}")


def _map_columns(columns: list[str]) -> dict[str, str]:
    """Retourne un mapping {colonne_originale: colonne_normalisee}."""
    mapping: dict[str, str] = {}
    used_boule_slots: set[int] = set()

    for original in columns:
        clean = _clean_col(original)

        # numéro de tirage / identifiant
        if re.search(r"(annee.*numero.*tirage|numero.*tirage$|id.*tirage)", clean):
            mapping[original] = "id_tirage"
            continue

        # date du tirage (on exclut les dates de forclusion/réclamation)
        if "date" in clean and "forclus" not in clean and "reclam" not in clean:
            mapping[original] = "date_tirage"
            continue

        # jour de la semaine
        if clean == "jour_de_tirage" or clean == "jour_tirage" or clean == "jour":
            mapping[original] = "jour_tirage"
            continue

        # numéro chance (introduit en 2017 pour LOTO / 1996 pour Super Loto)
        if "chance" in clean:
            mapping[original] = "numero_chance"
            continue

        # numéro complémentaire (ancien format, avant le numéro Chance)
        if "complement" in clean:
            mapping[original] = "numero_complementaire"
            continue

        # boules principales : boule1, boule_1, boule 1...
        m = re.search(r"boule[_ ]?(\d+)$", clean)
        if m:
            n = int(m.group(1))
            if n not in used_boule_slots:
                mapping[original] = f"boule_{n}"
                used_boule_slots.add(n)
                continue

        # rangs de gains / nombre de gagnants -> on garde en "extra_"
        mapping[original] = f"extra_{clean}"

    return mapping


def normalize_file(path: Path, source_label: str) -> pd.DataFrame:
    df = _read_csv_robust(path)
    mapping = _map_columns(list(df.columns))
    df = df.rename(columns=mapping)
    df["source"] = source_label

    unmapped = [c for c in df.columns if c.startswith("extra_")]
    detected = [c for c in df.columns if not c.startswith("extra_") and c != "source"]
    print(f"  [{path.name}] colonnes reconnues: {sorted(detected)}")
    if unmapped:
        print(f"  [{path.name}] colonnes non reconnues (conservées telles quelles): {sorted(unmapped)}")

    return df


def normalize_all() -> pd.DataFrame:
    csv_files = sorted(RAW_DIR.rglob("*.csv")) + sorted(RAW_DIR.rglob("*.txt"))
    if not csv_files:
        raise FileNotFoundError(
            f"Aucun fichier trouvé dans {RAW_DIR}. Lance d'abord download_loto.py."
        )

    frames = []
    for path in csv_files:
        source_label = path.parent.name
        print(f"Normalisation de {path} (période: {source_label})")
        frames.append(normalize_file(path, source_label))

    combined = pd.concat(frames, ignore_index=True, sort=False)

    # Types + nettoyage
    combined["date_tirage"] = pd.to_datetime(
        combined.get("date_tirage"), dayfirst=True, errors="coerce"
    )
    ball_cols = [f"boule_{i}" for i in range(1, MAIN_BALL_COUNT + 1) if f"boule_{i}" in combined.columns]
    for col in ball_cols + ["numero_chance", "numero_complementaire"]:
        if col in combined.columns:
            combined[col] = pd.to_numeric(combined[col], errors="coerce").astype("Int64")

    # Un tirage sans date exploitable ou sans boules n'est pas utilisable pour les stats
    before = len(combined)
    combined = combined.dropna(subset=["date_tirage"] + ball_cols, how="any")
    combined = combined.drop_duplicates(subset=["date_tirage"] + ball_cols)
    combined = combined.sort_values("date_tirage").reset_index(drop=True)
    after = len(combined)
    print(f"\n{after}/{before} tirages valides et uniques conservés.")

    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    combined.to_csv(OUT_FILE, index=False)
    print(f"Fichier normalisé écrit dans: {OUT_FILE}")
    return combined


if __name__ == "__main__":
    normalize_all()
