"""
generate_report.py
-------------------
Génère un rapport HTML statique, autonome (aucun JS requis), pensé pour être
consulté sur téléphone via GitHub Pages. Écrit dans site/index.html.
"""

from datetime import datetime, timezone
from pathlib import Path

from stats_loto import (
    load,
    number_frequencies,
    chance_frequencies,
    gaps_since_last_seen,
    most_common_pairs,
    chi_square_uniformity,
    theoretical_probabilities,
)

SITE_DIR = Path(__file__).parent / "site"

CSS = """
:root {
  --bg: #101a2e;
  --bg-panel: #16233d;
  --text: #f1eee4;
  --text-muted: #94a3c4;
  --gold: #d4a537;
  --cold: #3a4c74;
  --rule: rgba(241, 238, 228, 0.14);
}

* { box-sizing: border-box; }

html { -webkit-text-size-adjust: 100%; }

body {
  margin: 0;
  background: var(--bg);
  color: var(--text);
  font-family: "JetBrains Mono", ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 15px;
  line-height: 1.55;
}

main {
  max-width: 480px;
  margin: 0 auto;
  padding: 28px 20px 48px;
  border-left: 1px dashed var(--rule);
  border-right: 1px dashed var(--rule);
}

h1, h2 {
  font-family: "Fraunces", Georgia, serif;
  font-weight: 600;
  margin: 0 0 6px;
  letter-spacing: 0.2px;
}

h1 { font-size: 28px; }

h2 {
  font-size: 18px;
  margin-top: 0;
}

.subtitle {
  color: var(--text-muted);
  font-size: 13px;
  margin: 0 0 18px;
}

.notice {
  font-size: 13px;
  color: var(--text-muted);
  border-top: 1px solid var(--rule);
  border-bottom: 1px solid var(--rule);
  padding: 12px 0;
  margin: 0 0 28px;
}

.notice strong { color: var(--text); }

section { margin: 34px 0; }

.grid7 {
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
  margin: 16px 0 8px;
}

.cell {
  flex: 0 0 calc((100% - 30px) / 7);
  height: 0;
  padding-bottom: calc((100% - 30px) / 7);
  position: relative;
  border-radius: 4px;
  font-weight: 600;
  font-size: 14px;
  border: 1px solid var(--rule);
}

.cell span {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
}

.chance-row {
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
  margin: 16px 0 8px;
}

.chance-row .cell {
  flex: 0 0 calc((100% - 45px) / 10);
  padding-bottom: calc((100% - 45px) / 10);
  border-radius: 999px;
  font-size: 12px;
}

.caption {
  color: var(--text-muted);
  font-size: 12px;
  margin: 6px 0 0;
}

.ticket-row {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  padding: 8px 0;
  border-bottom: 1px solid var(--rule);
  font-size: 14px;
}

.ticket-row .date { color: var(--text-muted); white-space: nowrap; }

.balls { letter-spacing: 2px; }

.chance-tag {
  display: inline-block;
  min-width: 20px;
  padding: 1px 6px;
  border-radius: 999px;
  background: var(--gold);
  color: #1a1200;
  font-weight: 600;
  text-align: center;
}

table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

th, td {
  text-align: left;
  padding: 6px 8px 6px 0;
  border-bottom: 1px solid var(--rule);
}

th { color: var(--text-muted); font-weight: 500; }

.table-wrap { overflow-x: auto; }

.stat-line {
  background: var(--bg-panel);
  border: 1px solid var(--rule);
  border-radius: 6px;
  padding: 14px;
  font-size: 13px;
}

footer {
  margin-top: 40px;
  padding-top: 18px;
  border-top: 1px dashed var(--rule);
  color: var(--text-muted);
  font-size: 12px;
}

footer p { margin: 0 0 10px; }

a { color: var(--gold); }
a:focus-visible, button:focus-visible { outline: 2px solid var(--gold); outline-offset: 2px; }
"""

HEAD = """<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>LOTO — état des lieux</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Fraunces:wght@500;600&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
<style>{css}</style>
</head>
<body>
<main>
"""

TAIL = """
</main>
</body>
</html>
"""


def _color_for(t: float) -> str:
    """Interpole entre bleu ardoise (froid/rare) et or (chaud/fréquent), t dans [0,1]."""
    cold = (58, 76, 116)
    gold = (212, 165, 55)
    r = cold[0] + (gold[0] - cold[0]) * t
    g = cold[1] + (gold[1] - cold[1]) * t
    b = cold[2] + (gold[2] - cold[2]) * t
    return f"rgb({r:.0f},{g:.0f},{b:.0f})"


def _text_color_for(t: float) -> str:
    return "#1a1200" if t > 0.62 else "#f1eee4"


def _normalize(series):
    lo, hi = series.min(), series.max()
    if hi == lo:
        return {k: 0.5 for k in series.index}
    return {k: (v - lo) / (hi - lo) for k, v in series.items()}


def build_number_grid(freq) -> str:
    norm = _normalize(freq)
    cells = []
    for n in range(1, 50):
        t = norm[n]
        bg = _color_for(t)
        fg = _text_color_for(t)
        cells.append(
            f'<div class="cell" style="background:{bg};color:{fg}" '
            f'title="{n}: {int(freq[n])} sorties"><span>{n}</span></div>'
        )
    return f'<div class="grid7">{"".join(cells)}</div>'


def build_chance_row(freq) -> str:
    norm = _normalize(freq)
    cells = []
    for n in range(1, 11):
        t = norm[n]
        bg = _color_for(t)
        fg = _text_color_for(t)
        cells.append(
            f'<div class="cell" style="background:{bg};color:{fg}" '
            f'title="{n}: {int(freq[n])} sorties"><span>{n}</span></div>'
        )
    return f'<div class="chance-row">{"".join(cells)}</div>'


def build_recent_draws(df, n=5) -> str:
    recent = df.sort_values("date_tirage", ascending=False).head(n)
    rows = []
    ball_cols = [c for c in ["boule_1", "boule_2", "boule_3", "boule_4", "boule_5"] if c in df.columns]
    for _, row in recent.iterrows():
        date_str = row["date_tirage"].strftime("%d/%m/%Y")
        balls = "  ".join(f"{int(row[c]):02d}" for c in ball_cols if row[c] == row[c])
        chance = f'<span class="chance-tag">{int(row["numero_chance"]):02d}</span>' if "numero_chance" in df.columns and row.get("numero_chance") == row.get("numero_chance") else ""
        rows.append(
            f'<div class="ticket-row"><span class="date">{date_str}</span>'
            f'<span class="balls">{balls}</span>{chance}</div>'
        )
    return "".join(rows)


def build_gap_table(gaps, top_n=10) -> str:
    ranked = gaps.dropna().sort_values(ascending=False).head(top_n)
    rows = "".join(
        f"<tr><td>{n}</td><td>{int(g)} tirages</td></tr>" for n, g in ranked.items()
    )
    return (
        '<div class="table-wrap"><table><thead><tr><th>Numéro</th>'
        f"<th>Depuis sa dernière sortie</th></tr></thead><tbody>{rows}</tbody></table></div>"
    )


def build_pairs_table(pairs_df) -> str:
    rows = "".join(
        f"<tr><td>{r.numero_1:02d} — {r.numero_2:02d}</td><td>{r.nb_fois_ensemble}×</td></tr>"
        for r in pairs_df.itertuples()
    )
    return (
        '<div class="table-wrap"><table><thead><tr><th>Paire</th>'
        f"<th>Ensemble</th></tr></thead><tbody>{rows}</tbody></table></div>"
    )


def build_proba_table(proba_df) -> str:
    rows = []
    for _, r in proba_df.iterrows():
        chance_txt = "+ bon N° chance" if r["bon_numero_chance"] else "sans le N° chance"
        odds = int(r["1_chance_sur"]) if r["1_chance_sur"] == r["1_chance_sur"] else None
        odds_txt = f"{odds:,}".replace(",", " ") if odds is not None else "—"
        rows.append(f"<tr><td>{r['bonnes_boules']}/5 {chance_txt}</td><td>1 sur {odds_txt}</td></tr>")
    return (
        '<div class="table-wrap"><table><thead><tr><th>Résultat</th>'
        f"<th>Probabilité</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div>"
    )


def generate() -> Path:
    df = load()
    freq = number_frequencies(df)
    chance_freq = chance_frequencies(df)
    gaps = gaps_since_last_seen(df)
    pairs = most_common_pairs(df, top_n=10)
    chi2 = chi_square_uniformity(freq)
    proba = theoretical_probabilities()

    period_start = df["date_tirage"].min().strftime("%d/%m/%Y")
    period_end = df["date_tirage"].max().strftime("%d/%m/%Y")
    generated_at = datetime.now(timezone.utc).strftime("%d/%m/%Y %H:%M UTC")

    chi2_txt = (
        chi2.get("interpretation", "Test indisponible.")
        if isinstance(chi2, dict)
        else "Test indisponible."
    )

    body = f"""
<h1>LOTO — état des lieux</h1>
<p class="subtitle">{len(df)} tirages analysés · {period_start} → {period_end}</p>
<p class="notice"><strong>À lire avant de jouer :</strong> chaque tirage est indépendant
et parfaitement équiprobable. Ce qui suit décrit le passé ; ça n'augmente ni ne
diminue la chance d'un numéro au prochain tirage.</p>

<section>
  <h2>Fréquence historique — boules 1 à 49</h2>
  {build_number_grid(freq)}
  <p class="caption">Plus la case est claire (or), plus le numéro est sorti souvent depuis {period_start}.</p>
</section>

<section>
  <h2>Fréquence — numéro Chance</h2>
  {build_chance_row(chance_freq)}
</section>

<section>
  <h2>Derniers tirages</h2>
  {build_recent_draws(df)}
</section>

<section>
  <h2>Numéros "en retard"</h2>
  {build_gap_table(gaps)}
  <p class="caption">Nombre de tirages depuis leur dernière sortie. Un grand écart
  n'annonce pas un rattrapage : chaque tirage reste indépendant.</p>
</section>

<section>
  <h2>Paires les plus fréquentes</h2>
  {build_pairs_table(pairs)}
</section>

<section>
  <h2>Le tirage est-il équilibré ?</h2>
  <div class="stat-line">{chi2_txt}</div>
</section>

<section>
  <h2>Probabilités exactes, à chaque tirage</h2>
  {build_proba_table(proba)}
</section>

<footer>
  <p>Généré automatiquement le {generated_at}, à partir de l'historique officiel
  FDJ (<a href="https://www.fdj.fr/jeux-de-tirage/loto/historique">fdj.fr</a>).</p>
  <p>Le LOTO® est un jeu de hasard. Aucune statistique ne prédit un tirage futur.
  Jouer comporte des risques : dépendance, pertes financières. Aide et
  information sur <a href="https://www.joueurs-info-service.fr/">joueurs-info-service.fr</a>.</p>
</footer>
"""

    html = HEAD.format(css=CSS) + body + TAIL
    SITE_DIR.mkdir(parents=True, exist_ok=True)
    out = SITE_DIR / "index.html"
    out.write_text(html, encoding="utf-8")
    print(f"Rapport généré : {out}")
    return out


if __name__ == "__main__":
    generate()
