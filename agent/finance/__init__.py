"""Métriques d'optimisation (projet *rating fond*).

Trois briques, sans dépendance au reste de l'agent :

- `metrics`        : fonctions de calcul PURES (aucun LLM, aucun I/O).
- `metric_catalog` : métadonnées par métrique (formule, caractéristiques, données
                     requises…), source unique de vérité reprise de
                     `metriques_optimisation_gold.md`.
- `select`         : mappe l'intention de l'utilisateur vers la bonne métrique et
                     demande une clarification quand deux métriques se valent.
- `amundi`         : accès au dataset Amundi structuré (documents/amundi/<ISIN>/) —
                     nav.csv → rendements (vrai calcul des métriques), summary.json → faits.
"""
