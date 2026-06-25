"""Fait tourner l'agent sur un golden set et MESURE ce qu'il fait.

Usage :
    python tests/agent_eval/run_golden.py [fichier.yaml] [limite | ids]

- fichier.yaml : jeu de questions (défaut : tests/agent_eval/question_test.yaml, qui
  exerce toute la boîte à outils ; golden_fonds_v1.yaml = lookups RAG seuls)
- 2e argument :
    * un nombre  → ne traiter que les N premières questions ;
    * une liste d'ids séparés par des virgules (ex. "v2-08,v2-12") → filtrage par
      préfixe d'id (rapport suffixé `_rerun`) ;
    * absent     → toutes les questions.

Tout tourne dans UN seul processus : l'index RAG (embedding coûteux) n'est construit
qu'une fois et réutilisé. Les rapports sont écrits dans tests/agent_eval/reports/,
auto-étiquetés par modèle (golden_report_<modèle>.md).

Métriques AUTOMATIQUES (en tête du rapport) : couverture d'outils
(expected_tools ⊆ outils appelés), latence et tokens par question, agrégés par
catégorie + matrice des outils exercés. La JUSTESSE de la réponse reste à valider
à l'œil (le critère « réponse attendue » est un principe, pas une chaîne exacte).
"""
import sys
import time
from pathlib import Path

import yaml

# L'éval tourne sur le modèle PAR DÉFAUT du projet (Claude Opus 4.8, cf.
# rag_engine/configs). Pour une passe économe, surcharger avant de lancer :
#   RAG__LLM__OPENAI__MODEL=claude-haiku-4-5 python tests/agent_eval/run_golden.py
HERE = Path(__file__).resolve().parent  # tests/agent_eval/
ROOT = HERE.parents[1]  # racine du dépôt
sys.path.insert(0, str(ROOT))

from agent import llm  # noqa: E402
from agent.finance.select import auto_ask  # noqa: E402
from agent.tools import TOOLS  # noqa: E402
from main import answer_query  # noqa: E402

DEFAULT_GOLDEN = HERE / "question_test.yaml"
REPORTS_DIR = HERE / "reports"


def _model_slug() -> str:
    """Identifiant du modèle actif, pour étiqueter le rapport (Opus vs Haiku…)."""
    try:
        return str(llm._client().model_id).replace("/", "-")
    except Exception:
        return "model"


def main():
    golden_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_GOLDEN
    arg2 = sys.argv[2] if len(sys.argv) > 2 else None

    data = yaml.safe_load(golden_path.read_text(encoding="utf-8"))
    items = data["items"]
    # Rapport auto-étiqueté par modèle → comparaisons multi-modèles sans écrasement.
    REPORTS_DIR.mkdir(exist_ok=True)
    model = _model_slug()
    report_path = REPORTS_DIR / f"golden_report_{model}.md"
    if arg2 and arg2.isdigit():
        items = items[:int(arg2)]
    elif arg2:
        ids = [t.strip() for t in arg2.split(",") if t.strip()]
        items = [it for it in items if any(it["id"].startswith(t) for t in ids)]
        report_path = report_path.with_name(f"golden_report_{model}_rerun.md")

    print(f"Golden : {golden_path.name} ({data.get('version', '?')}) — "
          f"{len(items)} question(s)\n")

    sections = []
    rows = []  # une ligne de métriques par question
    tools_seen: set[str] = set()  # outils réellement exercés sur tout le run
    t0 = time.time()
    for n, item in enumerate(items, 1):
        qid, question = item["id"], item["question"]
        expected = (item.get("expected_answer") or "").strip()
        category = item.get("category", "(n/a)")
        expected_tools = item.get("expected_tools", []) or []
        print(f"\n########## {n}/{len(items)} — {qid} [{category}] ##########")

        llm.reset_usage()  # mesure du coût propre à cette question
        tq = time.time()
        try:
            # auto_ask : l'éval ne doit jamais bloquer sur une clarification stdin.
            obtained, trace = answer_query(
                question, verbose=False, ask_fn=auto_ask, return_trace=True
            )
            obtained = obtained.strip()
        except Exception as exc:  # une question ne doit pas tuer le batch
            obtained = f"[ERREUR pendant l'exécution : {exc}]"
            trace = {"tools": [], "metric": None, "clarification_asked": False, "n_steps": 0}
        latency = time.time() - tq
        usage = llm.get_usage()
        tokens = usage["in_tokens"] + usage["out_tokens"]

        used = list(dict.fromkeys(trace["tools"]))  # ordre conservé, dédupliqué
        tools_seen.update(used)
        # Couverture : tous les outils attendus ont-ils été appelés ?
        covered = all(t in used for t in expected_tools) if expected_tools else None

        rows.append({
            "id": qid, "category": category, "expected_tools": expected_tools,
            "used": used, "covered": covered, "latency": latency, "tokens": tokens,
            "metric": trace.get("metric"), "asked": trace.get("clarification_asked"),
        })
        mark = "✓" if covered else ("✗" if covered is False else "—")
        print(f"→ couverture {mark} | outils={used} | {latency:.1f}s | ~{tokens} tok")

        sections.append(
            f"## {qid}  ·  `{category}`\n\n"
            f"**Question :** {question}\n\n"
            f"**Outils attendus :** {expected_tools or '—'}  ·  "
            f"**appelés :** {used or '—'}  ·  **couverture :** {mark}  ·  "
            f"**latence :** {latency:.1f}s  ·  **tokens :** ~{tokens}"
            + (f"  ·  **métrique :** {trace.get('metric')}"
               f"{' (clarification demandée)' if trace.get('asked') else ''}"
               if trace.get("metric") else "")
            + f"\n\n**Réponse attendue (critère) :**\n\n{expected}\n\n"
            f"**Réponse obtenue :**\n\n{obtained}\n\n---\n"
        )

    dt = time.time() - t0
    report_path.write_text(
        _build_report(golden_path, data, rows, tools_seen, dt) + "\n".join(sections),
        encoding="utf-8",
    )
    cov_pass = sum(1 for r in rows if r["covered"] is True)
    cov_tot = sum(1 for r in rows if r["covered"] is not None)
    print(f"\nRapport écrit dans {report_path.relative_to(ROOT)} "
          f"({len(items)} question(s), {dt:.0f}s).")
    print(f"Couverture d'outils : {cov_pass}/{cov_tot} questions  ·  "
          f"outils exercés : {len(tools_seen)}/{len(TOOLS)}")


def _build_report(golden_path, data, rows, tools_seen, dt) -> str:
    """Construit l'en-tête : tableau par catégorie + matrice de couverture d'outils."""
    # Agrégat par catégorie
    cats: dict[str, dict] = {}
    for r in rows:
        c = cats.setdefault(r["category"], {"n": 0, "cov_pass": 0, "cov_tot": 0,
                                            "lat": 0.0, "tok": 0})
        c["n"] += 1
        c["lat"] += r["latency"]
        c["tok"] += r["tokens"]
        if r["covered"] is not None:
            c["cov_tot"] += 1
            c["cov_pass"] += int(r["covered"])

    cat_table = ["| Catégorie | Q | Couverture outils | Latence moy. | Tokens moy. |",
                 "|---|---|---|---|---|"]
    for name, c in cats.items():
        cov = f"{c['cov_pass']}/{c['cov_tot']}" if c["cov_tot"] else "—"
        cat_table.append(
            f"| {name} | {c['n']} | {cov} | {c['lat'] / c['n']:.1f}s | "
            f"~{round(c['tok'] / c['n'])} |"
        )

    # Matrice : quels outils ont été exercés au moins une fois ?
    missing = [t for t in TOOLS if t not in tools_seen]
    tools_line = (
        f"**Outils exercés : {len(tools_seen)}/{len(TOOLS)}** — "
        + ", ".join(sorted(tools_seen))
        + (f"  ·  _manquants :_ {', '.join(missing)}" if missing else "  ·  _aucun manquant_ ✓")
    )

    cov_pass = sum(1 for r in rows if r["covered"] is True)
    cov_tot = sum(1 for r in rows if r["covered"] is not None)
    return (
        f"# Rapport golden — {golden_path.name}\n\n"
        f"Version : `{data.get('version', '?')}` — {len(rows)} question(s) — "
        f"temps total : {dt:.0f}s\n\n"
        f"**Couverture d'outils globale : {cov_pass}/{cov_tot} questions** "
        f"(les outils attendus ont bien été appelés).\n\n"
        f"{tools_line}\n\n"
        f"## Synthèse par catégorie\n\n" + "\n".join(cat_table) + "\n\n"
        "> La justesse de la réponse reste à valider à l'œil (le critère « réponse "
        "attendue » n'est pas une chaîne exacte). La **couverture d'outils**, la "
        "**latence** et les **tokens** sont mesurés automatiquement. Coût en tokens "
        "= estimation (count_tokens du client), pour comparer, pas pour facturer.\n\n"
        "---\n\n"
    )


if __name__ == "__main__":
    main()
