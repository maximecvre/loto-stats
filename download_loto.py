"""
download_loto.py
-----------------
Télécharge les archives ZIP officielles de l'historique du LOTO® FDJ
et les extrait dans data/raw/.

Les URLs ci-dessous sont celles listées sur :
https://www.fdj.fr/jeux-de-tirage/loto/historique
(section "Historique Loto" - tirages du LOTO classique, hors Super Loto
et Grand Loto qui sont des tirages spéciaux avec des cagnottes différentes).

Si FDJ change ses URLs, il suffit de mettre à jour la liste LOTO_ARCHIVES
avec les nouveaux liens trouvés sur la page.
"""

import io
import zipfile
from pathlib import Path

import requests

RAW_DIR = Path(__file__).parent / "data" / "raw"

# (période, URL) - toutes récupérées sur la page historique FDJ
LOTO_ARCHIVES = [
    ("2019-2026", "https://www.sto.api.fdj.fr/anonymous/service-draw-info/v3/documentations/1a2b3c4d-9876-4562-b3fc-2c963f66afp6"),
    ("2019_fev-nov", "https://www.sto.api.fdj.fr/anonymous/service-draw-info/v3/documentations/1a2b3c4d-9876-4562-b3fc-2c963f66afo6"),
    ("2017-2019", "https://www.sto.api.fdj.fr/anonymous/service-draw-info/v3/documentations/1a2b3c4d-9876-4562-b3fc-2c963f66afn6"),
    ("2008-2017", "https://www.sto.api.fdj.fr/anonymous/service-draw-info/v3/documentations/1a2b3c4d-9876-4562-b3fc-2c963f66afm6"),
    ("1976-2008", "https://www.sto.api.fdj.fr/anonymous/service-draw-info/v3/documentations/1a2b3c4d-9876-4562-b3fc-2c963f66afl6"),
]

HEADERS = {
    # Un User-Agent "normal" évite certains blocages basiques côté serveur.
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
}


def download_all(force: bool = False) -> list[Path]:
    """Télécharge et extrait chaque archive. Retourne la liste des fichiers extraits."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    extracted_files: list[Path] = []

    for label, url in LOTO_ARCHIVES:
        dest_dir = RAW_DIR / label
        marker = dest_dir / ".done"
        if marker.exists() and not force:
            print(f"[skip] {label} déjà téléchargé (utilisez force=True pour re-télécharger)")
            extracted_files.extend(p for p in dest_dir.glob("*") if p.suffix.lower() in (".csv", ".txt"))
            continue

        print(f"[download] {label} -> {url}")
        try:
            resp = requests.get(url, headers=HEADERS, timeout=30)
            resp.raise_for_status()
        except requests.RequestException as exc:
            print(f"  !! échec du téléchargement pour {label}: {exc}")
            continue

        dest_dir.mkdir(parents=True, exist_ok=True)
        try:
            with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
                zf.extractall(dest_dir)
                names = zf.namelist()
        except zipfile.BadZipFile:
            print(f"  !! le contenu reçu pour {label} n'est pas un ZIP valide")
            continue

        marker.write_text("ok")
        for name in names:
            p = dest_dir / name
            if p.suffix.lower() in (".csv", ".txt"):
                extracted_files.append(p)
        print(f"  -> extrait: {names}")

    return extracted_files


if __name__ == "__main__":
    files = download_all()
    print(f"\n{len(files)} fichier(s) prêt(s) à être normalisés dans {RAW_DIR}")
