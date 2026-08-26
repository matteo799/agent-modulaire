"""Justesse des réponses : compare ce que l'agent a répondu à la vérité terrain.

Usage :
    python tests/agent_eval/score_accuracy.py [rapport.md]

POURQUOI CE SCRIPT EXISTE
-------------------------
`run_golden.py` mesure la **conformité de trajectoire** : l'agent a-t-il appelé les
outils attendus. C'est une mesure de processus, et elle a un angle mort — un agent
peut appeler les bons outils et rapporter un chiffre faux dans sa synthèse, ou
produire le bon chiffre par un mauvais chemin. Dans les deux cas la couverture
d'outils est aveugle.

Ce script mesure autre chose : **la réponse finale est-elle exacte**.

Il n'appelle AUCUN LLM. Le dataset Amundi étant structuré (`summary.json`) et
historisé (`nav.csv`), la bonne réponse est calculable de façon déterministe avec
`agent/finance/` — le même code que les outils de l'agent, mais invoqué
directement. On compare ensuite au texte réellement produit, extrait du rapport
d'évaluation déjà versionné. D'où la propriété utile : **la justesse se mesure a
posteriori, sur un run déjà payé, sans aucun accès API.**

CE QU'IL VÉRIFIE, ET CE QU'IL NE VÉRIFIE PAS
--------------------------------------------
Il vérifie qu'une valeur exacte apparaît dans la réponse, qu'un libellé attendu y
figure, ou qu'un refus a bien eu lieu quand la donnée n'existe pas. C'est plus dur
que la couverture d'outils.

Il ne vérifie NI le raisonnement autour du chiffre, NI la pertinence d'une
recommandation. Une réponse peut contenir le bon Sharpe et en tirer une conclusion
absurde : elle sera comptée juste. Les questions non mécanisables (screening,
adéquation, audit) sont explicitement laissées à la lecture et comptées à part,
jamais silencieusement omises.
"""
from __future__ import annotations

import re
import sys
import unicodedata
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))

from agent.finance import amundi, metrics  # noqa: E402

DEFAULT_REPORT = HERE / "reports" / "golden_report_demo_gerant_claude-opus-4-8.md"

# Taux sans risque : SEULES les questions qui l'énoncent explicitement (« rf 2 % »)
# imposent 2 %. Les autres ne le mentionnent pas, et rf = 0 est alors la convention
# légitime — c'est celle que l'agent applique. Confondre les deux fait passer une
# réponse correcte pour une erreur : c'est arrivé pendant la mise au point de ce
# barème, sur g09 et g11.
RF_STATED = 0.02
RF_DEFAULT = 0.0

REFUSAL_MARKERS = (
    "ne permettent pas de répondre",
    "ne permet pas de répondre",
    "aucun passage pertinent",
    "je ne sais pas",
    "n'est pas couvert",
    "ne figure pas",
    "non calculable",
    "impossible de calculer",
    "aucune information",
    "aucune donnée",
    "n'est pas disponible",
    "ne sont pas disponibles",
    "non disponible",
    "pas disponible",
    "introuvable",
    "aucun fonds",
    "hors du périmètre",
    "ne permettent pas",
    "impossible à calculer",
    "ne peut pas être",
    "ne peuvent pas être",
    "n'a pas pu",
    "n'ont pas pu",
    "ne sont pas présent",
    "n'est pas présent",
    "ne contient pas",
    "ne contiennent pas",
    "pas en mesure",
    "ne dispose pas",
    "ne disposons pas",
)


# ── Vérité terrain, calculée à la volée ──────────────────────────────────────


def _returns(isin: str) -> list[float]:
    return amundi.load_returns(isin)


def vol(isin: str) -> float:
    return metrics.annualized_vol(_returns(isin))


def maxdd(isin: str) -> float:
    return metrics.max_drawdown(_returns(isin))


def sharpe(isin: str, rf: float = RF_STATED) -> float:
    return metrics.sharpe_from_returns(_returns(isin), rf=rf)


def sortino(isin: str, rf: float = RF_STATED) -> float:
    return metrics.sortino_from_returns(_returns(isin), rf=rf)


def starr(isin: str, rf: float = RF_STATED) -> float:
    return metrics.starr_from_returns(_returns(isin), rf=rf)


def martin(isin: str, rf: float = RF_STATED) -> float:
    return metrics.martin_from_returns(_returns(isin), rf=rf)


def perf(isin: str, period: str, key: str = "cumulative") -> float:
    return amundi.performance(isin, period)[key]


def summary_field(isin: str, field: str):
    return amundi.load_summary(isin).get(field)


def cost(isin: str, field: str) -> float:
    return (amundi.load_summary(isin).get("costs") or {}).get(field)


def _charac(isin: str, key: str) -> str:
    return str((amundi.load_summary(isin).get("characteristics") or {}).get(key, ""))


# ── Types de vérification ────────────────────────────────────────────────────


class Check:
    def __init__(self, kind: str, payload, label: str):
        self.kind, self.payload, self.label = kind, payload, label


def num(value, label: str) -> Check:
    return Check("num", value, label)


def text(substring: str, label: str) -> Check:
    return Check("text", substring, label)


def refuse(label: str) -> Check:
    return Check("refuse", None, label)


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFD", s or "")
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return s.lower()


def _answer_numbers(answer: str) -> list[float]:
    out = []
    for raw in re.findall(r"-?\d[\d  ]*(?:[.,]\d+)?", answer or ""):
        cleaned = raw.replace(" ", "").replace(" ", "").replace(",", ".").rstrip(".")
        try:
            out.append(float(cleaned))
        except ValueError:
            continue
    return out


def _matches(expected: float, answer: str, tol: float = 0.02) -> bool:
    """Le chiffre attendu figure-t-il dans la réponse ?

    On accepte la fraction (0,4367) ET le pourcentage (43,67 %) : les deux
    conventions coexistent légitimement dans les réponses.

    Deux tolérances se cumulent :
      - relative (2 %), pour les arrondis d'affichage courants ;
      - par arrondi explicite : la valeur attendue arrondie à n décimales. Les
        outils du dépôt formatent parfois à 2 décimales (la corrélation sort en
        `-0.01` pour une valeur réelle de -0.0068). Sans cette seconde règle, une
        réponse qui recopie fidèlement la sortie de l'outil serait comptée fausse.
        On écarte les arrondis qui annulent la valeur, sans quoi n'importe quel
        « 0 » de la réponse validerait une petite grandeur.
    """
    if expected is None:
        return False
    candidates = [expected, expected * 100, -expected, -expected * 100]
    for got in _answer_numbers(answer):
        for exp in candidates:
            if exp == 0:
                if abs(got) < 1e-9:
                    return True
                continue
            if abs(got - exp) <= abs(exp) * tol:
                return True
            for decimals in range(0, 5):
                rounded = round(exp, decimals)
                if rounded == 0:
                    continue
                if abs(got - rounded) < 1e-9:
                    return True
    return False


def _is_refusal(answer: str) -> bool:
    return any(m in _norm(answer) for m in (_norm(x) for x in REFUSAL_MARKERS))


def evaluate(check: Check, answer: str) -> bool:
    if check.kind == "num":
        return _matches(check.payload, answer)
    if check.kind == "text":
        return _norm(check.payload) in _norm(answer)
    if check.kind == "refuse":
        return _is_refusal(answer)
    raise ValueError(check.kind)


# ── Le barème, question par question ─────────────────────────────────────────
# Chaque entrée est une fonction sans argument : la vérité terrain n'est calculée
# que si la question est effectivement notée, et jamais figée dans le fichier.

A = "FR0011223569"  # fonds actions, présent dans la majorité des questions
B = "LU1882473009"
C = "FR0011585629"
M = "LU0568620214"  # fonds monétaire
D = "LU1882469403"

CHECKS: dict[str, callable] = {
    "g01-fiche-esg": lambda: [
        text(str(summary_field(A, "sfdr")), "classification SFDR"),
        num(summary_field(A, "risk_sri"), "SRI"),
    ],
    "g02-frais": lambda: [
        num(cost(A, "entry_pct"), "frais d'entrée"),
        num(cost(A, "ongoing_pct"), "frais courants"),
        num(cost(A, "performance_pct"), "commission de surperformance"),
    ],
    "g04-caracteristiques": lambda: [
        text(str(summary_field(C, "currency")), "devise"),
        num(summary_field(C, "aum"), "encours"),
    ],
    "g05-profil-complet": lambda: [
        num(vol(A), "volatilité"),
        num(maxdd(A), "max drawdown"),
        num(sharpe(A), "Sharpe"),
    ],
    "g06-vol-drawdown": lambda: [
        num(vol(A), "volatilité annualisée"),
        num(maxdd(A), "drawdown maximal"),
    ],
    "g07-sharpe": lambda: [num(sharpe(A), "ratio de Sharpe")],
    "g08-sortino": lambda: [num(sortino(B), "ratio de Sortino")],
    # g09-g11 n'énoncent aucun taux sans risque → rf = 0 (cf. RF_DEFAULT).
    "g09-intention-baisse": lambda: [
        text("sortino", "métrique retenue"),
        num(sortino(A, RF_DEFAULT), "valeur du Sortino"),
    ],
    "g10-intention-queue": lambda: [
        text("starr", "métrique retenue"),
        num(starr(B, RF_DEFAULT), "valeur du STARR"),
    ],
    "g11-intention-regularite": lambda: [
        text("martin", "métrique retenue"),
        num(martin(C, RF_DEFAULT), "valeur du Martin"),
    ],
    "g13-compare-sharpe": lambda: [
        num(sharpe(A), f"Sharpe {A}"),
        num(sharpe(M), f"Sharpe {M}"),
    ],
    "g14-compare-sortino": lambda: [
        num(sortino(B), f"Sortino {B}"),
        num(sortino(D), f"Sortino {D}"),
    ],
    "g15-compare-frais": lambda: [
        num(cost(A, "ongoing_pct"), f"frais courants {A}"),
        num(cost(C, "ongoing_pct"), f"frais courants {C}"),
        num(abs(cost(A, "ongoing_pct") - cost(C, "ongoing_pct")), "écart"),
    ],
    "g18-sans-historique": lambda: [refuse("fonds absent du dataset")],
    "g19-isin-inexistant": lambda: [refuse("ISIN inexistant")],
    "g20-perf-periodes": lambda: [
        num(perf(A, "1y"), "performance 1 an"),
        num(perf(A, "3y"), "performance 3 ans"),
    ],
    "g21-perf-5ans": lambda: [
        num(perf(B, "5y", "annualized"), "annualisé 5 ans"),
        num(perf(B, "all", "annualized"), "annualisé depuis création"),
    ],
    "g23-champ-absent": lambda: [refuse("note Morningstar absente du corpus")],
    "g24-surperformance-non-calculable": lambda: [refuse("surperformance non calculable")],
    "g26-valeur-investie": lambda: [
        num(amundi.invested_value(A, 10000, "3y")["value"], "valeur finale"),
    ],
    # On réutilise `correlation_pairs`, l'implémentation canonique du dépôt, plutôt
    # qu'un calcul maison : la vérité terrain doit venir du même code que l'outil.
    "g28-correlation": lambda: [
        num(amundi.correlation_pairs([A, M])[0][2], "corrélation"),
    ],
    "g34-risque-queue": lambda: [
        num(metrics.var_historical(_returns(A), 0.05), "VaR 95 %"),
        num(metrics.var_historical(_returns(A), 0.01), "VaR 99 %"),
        num(metrics.skewness(_returns(A)), "skewness"),
        num(metrics.kurtosis_excess(_returns(A)), "kurtosis"),
    ],
    "g35-audit-nav": lambda: [num(len(amundi.load_navs(A)), "nombre de points NAV")],
    "g03-gouvernance": lambda: [
        text(_charac(B, "Gérant").split()[0], "gérant"),
        text("caceis", "dépositaire"),
    ],
    "g12-ambigu": lambda: [
        text("sharpe", "Sharpe évoqué"),
        text("sortino", "Sortino évoqué"),
    ],
    "g16-adequation-defensif": lambda: [
        num(summary_field(A, "risk_sri"), "SRI"),
        num(vol(A), "volatilité"),
        num(maxdd(A), "max drawdown"),
    ],
    "g17-adequation-tresorerie": lambda: [num(summary_field(M, "risk_sri"), "SRI")],
    "g22-screening": lambda: [
        text(amundi.screen("sortino", 5, "action", "8", rf=RF_STATED)[0][2][:24], "1er du classement"),
    ],
    "g25-recherche-par-nom": lambda: [
        text("amundi actions france responsable", "fonds identifié"),
    ],
    # g27 et g29-g33 n'énoncent pas de taux sans risque → rf = 0.
    "g27-comparaison-complete": lambda: [
        num(vol(A), f"volatilité {A}"),
        num(vol(B), f"volatilité {B}"),
        num(maxdd(A), f"max drawdown {A}"),
        num(cost(A, "ongoing_pct"), f"frais courants {A}"),
    ],
    "g29-rendements-calendaires": lambda: [
        num(dict(amundi.calendar_returns(A)).get(2022), "année 2022"),
        num(dict(amundi.calendar_returns(A)).get(2021), "année 2021"),
    ],
    "g30-regime-marche": lambda: [
        num(dict(amundi.calendar_returns(A)).get(2022), "performance 2022"),
        num(amundi.period_return(A, "19/02/2020", "23/03/2020")["cumulative"], "krach Covid"),
    ],
    "g31-stats-mensuelles": lambda: [
        num(amundi.monthly_stats(A)["best"][1], "meilleur mois"),
        num(amundi.monthly_stats(A)["worst"][1], "pire mois"),
        num(amundi.monthly_stats(A)["pct_positive"], "% de mois positifs"),
    ],
    "g32-temps-sous-leau": lambda: [
        num(amundi.underwater(A)["longest_underwater_days"], "jours sous l'eau"),
        num(amundi.underwater(A)["max_drawdown"], "max drawdown"),
    ],
    "g33-sharpe-glissant": lambda: [
        num(amundi.rolling_sharpe(A)["mean"], "Sharpe glissant moyen"),
    ],
    "g37-alpha-tracking-error": lambda: [refuse("alpha/TE hors périmètre")],
    "g38-composition-holdings": lambda: [refuse("positions hors périmètre")],
    "g39-esg-profond": lambda: [refuse("ESG détaillé hors périmètre")],
    "g40-duration-credit": lambda: [refuse("duration hors périmètre")],
}

# Questions volontairement NON mécanisables : le critère reste qualitatif, et
# aucune assertion déterministe ne le capturerait honnêtement.
MANUAL = {
    "g36-impact-frais": "la projection dépend d'hypothèses de rendement non fixées par la question",
}


# ── Extraction des réponses du rapport ───────────────────────────────────────


def parse_coverage(path: Path) -> dict[str, bool | None]:
    """Verdict de couverture d'outils par question, tel qu'écrit par run_golden."""
    raw = path.read_text(encoding="utf-8")
    out: dict[str, bool | None] = {}
    for block in re.split(r"\n## (?=g\d)", raw)[1:]:
        qid = block.split(" ")[0].strip()
        m = re.search(r"\*\*couverture :\*\* (✓|✗|—)", block)
        if m:
            out[qid] = {"✓": True, "✗": False, "—": None}[m.group(1)]
    return out


def parse_report(path: Path) -> dict[str, str]:
    """Récupère la réponse finale de chaque question du rapport d'évaluation."""
    raw = path.read_text(encoding="utf-8")
    answers: dict[str, str] = {}
    for block in re.split(r"\n## (?=g\d)", raw)[1:]:
        qid = block.split(" ")[0].strip()
        # La réponse court jusqu'à la fin du bloc. On ne peut PAS s'arrêter au
        # premier « --- » : les réponses contiennent leurs propres règles
        # horizontales markdown, et on tronquerait la moitié du contenu.
        m = re.search(r"### Réponse de l'agent\s*(.*)", block, re.DOTALL)
        if m:
            answers[qid] = m.group(1).strip().rstrip("-").strip()
    return answers


def control_run(answers: dict[str, str]) -> tuple[int, int]:
    """Témoin négatif : noter chaque question avec la réponse d'une AUTRE question.

    Un barème qui reste élevé sous permutation ne mesure rien — il valide du
    bruit. Ce témoin est la garantie que le score principal a du sens, et il
    doit s'effondrer. On le fait tourner à chaque exécution.
    """
    qids = [q for q in CHECKS if q in answers]
    shifted = {q: answers[qids[(i + 1) % len(qids)]] for i, q in enumerate(qids)}
    ok = total = 0
    for qid in qids:
        try:
            checks = CHECKS[qid]()
        except Exception:
            continue
        for c in checks:
            total += 1
            ok += bool(evaluate(c, shifted[qid]))
    return ok, total


def main() -> None:
    report = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_REPORT
    if not report.exists():
        sys.exit(f"rapport introuvable : {report}")
    answers = parse_report(report)
    if not answers:
        sys.exit(f"aucune réponse extraite de {report} — format inattendu ?")

    print(f"Rapport : {report.name} — {len(answers)} réponses extraites\n")

    rows, missing = [], []
    for qid, build in CHECKS.items():
        answer = answers.get(qid)
        if answer is None:
            missing.append(qid)
            continue
        try:
            checks = build()
        except Exception as exc:  # vérité terrain incalculable → on le dit
            rows.append((qid, None, f"vérité terrain indisponible : {exc}"))
            continue
        results = [(c.label, evaluate(c, answer)) for c in checks]
        passed = sum(ok for _, ok in results)
        rows.append((qid, (passed, len(results)), results))

    print("=" * 74)
    full = partial = zero = 0
    for qid, score, detail in rows:
        if score is None:
            print(f"  ?  {qid:<34} {detail}")
            continue
        passed, total = score
        mark = "OK " if passed == total else ("~  " if passed else "NON")
        if passed == total:
            full += 1
        elif passed:
            partial += 1
        else:
            zero += 1
        failed = [lbl for lbl, ok in detail if not ok]
        print(
            f" {mark} {qid:<34} {passed}/{total}"
            + (f"   manque : {', '.join(failed)}" if failed else "")
        )

    scored = full + partial + zero
    checks_ok = sum(s[0] for _, s, _ in rows if s)
    checks_tot = sum(s[1] for _, s, _ in rows if s)
    print("=" * 74)
    print(
        f"\nQuestions notées automatiquement : {scored}/{len(answers)}"
        f"  ({len(MANUAL)} laissées à la lecture, {len(missing)} absentes du rapport)"
    )
    print(f"  entièrement exactes : {full}")
    print(f"  partiellement       : {partial}")
    print(f"  aucune assertion    : {zero}")
    print(f"\nAssertions vérifiées : {checks_ok}/{checks_tot} "
          f"({100 * checks_ok / checks_tot:.0f} %)")

    # ── Le croisement : la couverture d'outils prédit-elle la justesse ? ──
    # C'est la question « so what ? ». Un agent peut appeler exactement les outils
    # attendus et rendre une mauvaise réponse, ou prendre un chemin différent et
    # rendre la bonne. Ce tableau dit à quelle fréquence les deux signaux divergent,
    # et lequel se trompe quand ils divergent.
    coverage = parse_coverage(report)
    cells = {(True, True): [], (True, False): [], (False, True): [], (False, False): []}
    for qid, score, _detail in rows:
        if score is None or qid not in coverage or coverage[qid] is None:
            continue
        cells[(coverage[qid], score[0] == score[1])].append(qid)

    print("\n" + "=" * 74)
    print("La couverture d'outils prédit-elle la justesse de la réponse ?\n")
    print("                        réponse exacte    réponse inexacte")
    print(f"  outils attendus ✓        {len(cells[(True, True)]):>6}            "
          f"{len(cells[(True, False)]):>6}")
    print(f"  outils attendus ✗        {len(cells[(False, True)]):>6}            "
          f"{len(cells[(False, False)]):>6}")
    disagree = cells[(True, False)] + cells[(False, True)]
    total_x = sum(len(v) for v in cells.values())
    print(f"\n  Désaccord des deux signaux : {len(disagree)}/{total_x} questions")
    if cells[(True, False)]:
        print(f"    outils ✓ mais réponse fausse : {', '.join(cells[(True, False)])}")
        print("      → la couverture d'outils a validé une réponse défectueuse.")
    if cells[(False, True)]:
        print(f"    outils ✗ mais réponse juste  : {', '.join(cells[(False, True)])}")
        print("      → l'agent a pris un autre chemin et a eu raison ; la couverture")
        print("        d'outils l'a pourtant compté en échec.")

    ctrl_ok, ctrl_tot = control_run(answers)
    print(
        f"Témoin négatif (réponses permutées) : {ctrl_ok}/{ctrl_tot} "
        f"({100 * ctrl_ok / ctrl_tot:.0f} %) — doit s'effondrer, sinon le barème "
        "valide du bruit."
    )
    if missing:
        print(f"\nAbsentes du rapport : {', '.join(missing)}")
    print("\nRappel : cette mesure vérifie qu'une valeur exacte figure dans la réponse.")
    print("Elle ne juge ni le raisonnement, ni la pertinence d'une recommandation.")


if __name__ == "__main__":
    main()
