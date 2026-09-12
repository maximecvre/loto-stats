"""
main.py
-------
Pipeline complet : téléchargement -> normalisation -> statistiques.

Usage :
    python main.py                # pipeline complet
    python main.py --skip-download  # réutilise data/raw déjà téléchargé
    python main.py --force          # re-télécharge même si déjà présent
"""

import argparse

from download_loto import download_all
from normalize_loto import normalize_all
from stats_loto import summary_report
from generate_report import generate as generate_report


def main() -> None:
    parser = argparse.ArgumentParser(description="Pipeline historique LOTO® FDJ")
    parser.add_argument("--skip-download", action="store_true",
                         help="ne pas re-télécharger, utiliser data/raw existant")
    parser.add_argument("--force", action="store_true",
                         help="forcer le re-téléchargement même si déjà fait")
    args = parser.parse_args()

    if not args.skip_download:
        print("=== 1/3 Téléchargement des archives FDJ ===")
        download_all(force=args.force)
    else:
        print("=== 1/3 Téléchargement ignoré (--skip-download) ===")

    print("\n=== 2/3 Normalisation des données ===")
    normalize_all()

    print("\n=== 3/4 Statistiques ===")
    summary_report()

    print("\n=== 4/4 Génération du rapport HTML (site/index.html) ===")
    generate_report()


if __name__ == "__main__":
    main()
