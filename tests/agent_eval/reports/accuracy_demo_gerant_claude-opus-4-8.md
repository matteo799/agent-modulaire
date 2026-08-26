# Justesse des réponses — run gérant (Opus 4.8)

Généré par `python tests/agent_eval/score_accuracy.py`. Aucun appel LLM :
la vérité terrain est recalculée depuis `documents/amundi/` avec `agent/finance/`,
puis comparée au texte du rapport d'évaluation déjà versionné.

```
Rapport : golden_report_demo_gerant_claude-opus-4-8.md — 40 réponses extraites

==========================================================================
 OK  g01-fiche-esg                      2/2
 ~   g02-frais                          2/3   manque : commission de surperformance
 OK  g04-caracteristiques               2/2
 OK  g05-profil-complet                 3/3
 OK  g06-vol-drawdown                   2/2
 OK  g07-sharpe                         1/1
 OK  g08-sortino                        1/1
 OK  g09-intention-baisse               2/2
 OK  g10-intention-queue                2/2
 OK  g11-intention-regularite           2/2
 OK  g13-compare-sharpe                 2/2
 OK  g14-compare-sortino                2/2
 OK  g15-compare-frais                  3/3
 OK  g18-sans-historique                1/1
 OK  g19-isin-inexistant                1/1
 OK  g20-perf-periodes                  2/2
 OK  g21-perf-5ans                      2/2
 OK  g23-champ-absent                   1/1
 OK  g24-surperformance-non-calculable  1/1
 OK  g26-valeur-investie                1/1
 OK  g28-correlation                    1/1
 OK  g34-risque-queue                   4/4
 OK  g35-audit-nav                      1/1
 OK  g37-alpha-tracking-error           1/1
 OK  g38-composition-holdings           1/1
 OK  g39-esg-profond                    1/1
 OK  g40-duration-credit                1/1
==========================================================================

Questions notées automatiquement : 27/40  (13 laissées à la lecture, 0 absentes du rapport)
  entièrement exactes : 26
  partiellement       : 1
  aucune assertion    : 0

Assertions vérifiées : 45/46 (98 %)
Témoin négatif (réponses permutées) : 12/46 (26 %) — doit s'effondrer, sinon le barème valide du bruit.

Rappel : cette mesure vérifie qu'une valeur exacte figure dans la réponse.
Elle ne juge ni le raisonnement, ni la pertinence d'une recommandation.
```
