# Politique de sécurité

## Signaler une vulnérabilité

Merci de **ne pas** ouvrir d'issue publique pour une faille de sécurité.
Contactez directement le mainteneur : **matteo.epone@gmail.com** — décrivez le
problème, les étapes de reproduction et l'impact estimé. Une réponse est visée
sous quelques jours ouvrés.

## Modèle de menace

Cet agent LLM manipule un corpus de documents financiers et exécute des outils.
Deux surfaces d'attaque sont traitées explicitement (voir `GUARDRAILS.md` §6,
couche 6 — aligné sur l'OWASP LLM Top 10) :

- **L'utilisateur** peut tenter de détourner l'agent de sa mission (jailbreak,
  injection de prompt, exfiltration de secrets, exécution de code).
- **Un document du corpus** peut contenir des instructions hostiles (injection
  de prompt *indirecte*).

Le principe est constant : **une garantie structurelle par le code**, jamais une
simple consigne de prompt.

## Contrôles en place

| Risque (OWASP LLM) | Contrôle | Où |
|---|---|---|
| LLM01 Prompt Injection (directe) | Gate d'entrée : motifs déterministes + classifieur de périmètre | `agent/security.py:screen_query` |
| LLM01 Prompt Injection (indirecte) | Clôture « données, pas instructions » autour des passages RAG | `agent/security.py:fence_passages` |
| Obfuscation des motifs | Normalisation NFKC + casse + zero-width | `agent/security.py:normalize` |
| Path traversal / fuite de secrets | Confinement lecture/écriture (`workspace/`, `documents/`) | `agent/security.py:confine` |
| Exécution de code / DoS | Calculateur AST en liste blanche (jamais `eval`) | `agent/security.py:safe_eval` |
| Charge / arguments hostiles | Validation générique des arguments d'outil | `agent/security.py:validate_args` |
| Consommation non bornée | Budget de run (kill-switch : appels LLM + temps) | `agent/llm.py:_check_budget` |
| Traçabilité / audit | Journal JSONL par run | `agent/audit.py` |

## Gestion des secrets

Les clés API ne sont **jamais** versionnées : uniquement via un `.env` gitignoré
(`RAG__LLM__OPENAI__API_KEY`). Le confinement des fichiers empêche l'agent de
lire ce `.env`.

## Limites assumées

La normalisation anti-obfuscation ne prétend pas couvrir tous les encodages
(base64, langues rares) ; le classifieur de périmètre est *fail-open* sur panne
LLM (la couche déterministe a déjà bloqué les attaques connues). Ces choix sont
documentés dans `GUARDRAILS.md`.
