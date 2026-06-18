"""Fait tourner l'agent sur un golden set et juxtapose attendu / obtenu.

Usage :
    python tests/run_golden.py [fichier.yaml] [limite | ids]

- fichier.yaml : golden à utiliser (défaut : tests/golden_fonds_v1.yaml)
- 2e argument :
    * un nombre  → ne traiter que les N premières questions ;
    * une liste d'ids séparés par des virgules (ex. "gfg1-02,gfg1-09") →
      ne traiter que ces questions (filtrage par préfixe d'id). Le rapport va
      alors dans tests/golden_report_rerun.md (le rapport complet est préservé).
    * absent     → toutes les questions.

Tout tourne dans UN seul processus : l'index RAG (et son embedding coûteux)
n'est construit qu'une fois et réutilisé pour toutes les questions. Le rapport
est écrit dans tests/golden_report.md.

Il n'y a pas de notation automatique (le système est non déterministe et les
réponses-types décrivent un critère, pas une chaîne exacte) : la comparaison
attendu / obtenu se fait à l'œil dans le rapport.
"""
import os
import sys
import time
from pathlib import Path

import yaml

# Éval = beaucoup d'appels LLM → on force un modèle économe (Claude Haiku) par
# défaut, avant tout import qui construirait le client LLM. Surchargeable :
# `RAG__LLM__OPENAI__MODEL=claude-opus-4-8 python tests/run_golden.py`.
os.environ.setdefault("RAG__LLM__OPENAI__MODEL", "claude-haiku-4-5")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from main import answer_query  # noqa: E402

DEFAULT_GOLDEN = ROOT / "tests" / "golden_fonds_v1.yaml"
REPORT_PATH = ROOT / "tests" / "golden_report.md"


def main():
    golden_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_GOLDEN
    arg2 = sys.argv[2] if len(sys.argv) > 2 else None

    data = yaml.safe_load(golden_path.read_text(encoding="utf-8"))
    items = data["items"]
    report_path = REPORT_PATH
    if arg2 and arg2.isdigit():
        items = items[:int(arg2)]
    elif arg2:
        ids = [t.strip() for t in arg2.split(",") if t.strip()]
        items = [it for it in items if any(it["id"].startswith(t) for t in ids)]
        report_path = REPORT_PATH.with_name("golden_report_rerun.md")

    print(f"Golden : {golden_path.name} ({data.get('version', '?')}) — "
          f"{len(items)} question(s)\n")

    sections = []
    t0 = time.time()
    for n, item in enumerate(items, 1):
        qid, question = item["id"], item["question"]
        expected = (item.get("expected_answer") or "").strip()
        print(f"\n########## {n}/{len(items)} — {qid} ##########")
        try:
            obtained = answer_query(question, verbose=False).strip()
        except Exception as exc:  # une question ne doit pas tuer le batch
            obtained = f"[ERREUR pendant l'exécution : {exc}]"
        print(f"→ {obtained[:200].replace(chr(10), ' ')}...")
        sections.append(
            f"## {qid}\n\n"
            f"**Question :** {question}\n\n"
            f"**Réponse attendue (critère) :**\n\n{expected}\n\n"
            f"**Réponse obtenue :**\n\n{obtained}\n\n"
            f"---\n"
        )

    dt = time.time() - t0
    header = (
        f"# Rapport golden — {golden_path.name}\n\n"
        f"Version : `{data.get('version', '?')}` — {len(items)} question(s) — "
        f"temps total : {dt:.0f}s\n\n"
        f"> Comparaison manuelle : la « réponse attendue » est un critère de "
        f"justesse, pas une chaîne exacte.\n\n---\n\n"
    )
    report_path.write_text(header + "\n".join(sections), encoding="utf-8")
    print(f"\nRapport écrit dans {report_path.relative_to(ROOT)} "
          f"({len(items)} question(s), {dt:.0f}s).")


if __name__ == "__main__":
    main()
