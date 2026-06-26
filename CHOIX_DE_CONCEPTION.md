# Choix de conception — justifications

*Ce document ne contient que **le pourquoi** : pour chaque partie du système, le
raisonnement derrière les choix faits **depuis la naissance du projet**, et les
alternatives écartées. Pour **ce qu'est** chaque composant et **comment** il marche,
voir `architecture.md` (même découpage en parties). Pour les règles de sûreté
consolidées, voir `GUARDRAILS.md`.*

> **Note d'évolution.** Le projet est né **100 % local** (Ollama, `qwen2.5:7b`,
> index NumPy maison). Beaucoup de choix ci-dessous sont nés de la **contrainte d'un
> petit modèle 7B** : ils restent pertinents aujourd'hui que le défaut soit Claude
> Opus via passerelle — soit parce qu'ils sont une **assurance à coût nul**, soit
> parce que l'invariant qu'ils garantissent vaut quel que soit le modèle. Quand un
> choix était spécifiquement dicté par le 7B, c'est signalé.

---

## 0. Vision : pourquoi un agent, pas un simple RAG

Un RAG classique suit un pipeline figé (question → recherche → réponse) et échoue dès
que la tâche demande **plusieurs actions** (chercher, puis calculer, puis rédiger). Le
choix central est d'**inverser le contrôle** : c'est le LLM qui décide quoi faire. Le
RAG devient alors **un outil parmi d'autres** — l'agent peut répondre à des questions
qui ne passent pas par les documents (un calcul), ou qui en combinent plusieurs.

**Pourquoi « plan d'abord » plutôt qu'une boucle ReAct pure ?** ReAct (le LLM décide
l'action suivante à chaque tour, sans plan) dérive vite sur un petit modèle (étapes
redondantes, boucles infinies). Un plan explicite en amont **borne les itérations**,
reste **lisible et auditable** (affiché et sauvegardé avant exécution), et garde
**chaque appel LLM simple** (un prompt = une décision). Compromis assumé : le plan
n'est pas réordonnable en cours de route ; la souplesse est récupérée localement par
la réflexion (§5).

---

## 1. Stack & orchestration : pourquoi deux niveaux

**Pourquoi deux couches de dépendances.** L'agent (`agent/`, `main.py`) reste minimal
et écrit à la main — le but pédagogique (montrer *comment* un agent fonctionne) impose
qu'aucun framework agentique ne cache la mécanique. Le moteur RAG (`rag_engine/`), lui,
assume des dépendances lourdes (bge-m3, reranker, Qdrant) : c'est une brique réutilisable
où la **qualité de récupération prime sur la lisibilité**. L'agent ne le voit qu'à
travers le contrat mince de `agent/rag_adapter.py`. **Écarté : LangChain/LlamaIndex *dans*
l'agent** — la machinerie agentique n'emprunte aucun framework.

**Pourquoi le LLM a migré du local vers la passerelle.** Né sous Ollama/`qwen2.5:7b`
pour la **confidentialité, le coût zéro et la pédagogie** (tout visible, pas de function
calling propriétaire). Mais sur des tâches réelles, la qualité d'un 7B plafonne. Le LLM
est donc devenu **configurable** (`provider` dans `rag_engine/configs`), défaut
**Claude Opus** via la passerelle meai.cloud — meilleure intelligence sur le plan, le
choix d'outil et la synthèse. Le **mode 100 % local reste une option** (`provider:
ollama`) : le contrat de `agent/llm.py` n'a pas changé, seul le réglage bascule.

**Pourquoi un moteur RAG séparé plutôt que l'index NumPy d'origine.** L'index NumPy en
mémoire (cosinus brut sur `nomic-embed-text`) démontrait le principe mais s'effondrait
sur des PDF réels : pas de réordonnancement, pas de découpage parent/enfant, aucun rejet
fiable du hors-sujet. Le moteur comble ces trois manques (§6).

---

## 2. Couche LLM : pourquoi fiabiliser le JSON et typer l'indisponibilité

**Pourquoi trois défenses JSON empilées.** Le plan et le choix d'outil reposent sur du
JSON renvoyé par le modèle ; un petit modèle en produit régulièrement d'imparfait. D'où
`format=json` au sampling + parsing tolérant (extraction de bloc, découpe accolades,
`strict=False`) + 2 retries. **Écarté : demander au LLM de réparer son propre JSON** —
plus coûteux (un appel de plus systématique) et pas plus fiable qu'un retry sur un cas
aussi simple. *Né du 7B, conservé comme assurance bon marché.*

**Pourquoi une exception typée (`LLMUnavailable`) pour la résilience.** Une erreur réseau
doit être traitée par un **repli gracieux**, pas par une stack trace. La distinguer d'une
erreur de contenu (par un type dédié) permet à chaque étage de la rattraper précisément
(§8).

---

## 3. Planificateur : pourquoi un plan court, ancré sur les outils

- **Catalogue injecté dans le prompt** : sans lui, le LLM invente des étapes
  irréalisables (« envoyer un email »). En lui montrant ses capacités réelles, chaque
  étape correspond à un outil existant.
- **3 à 7 étapes, une étape = un outil** : chaque étape atomique rend la sélection
  d'outil (§4) triviale, et borner le plan borne le temps total.
- **Dernière étape = livrable** : force le plan à converger vers un résultat concret.
- **Décomposition multi-fonds** : une recherche globale sur « compare 3 fonds » ne
  ramenait les passages que d'**un seul** fonds → calcul faux *par construction*
  (observé : `2.3 - 0.5373`, deux frais du même fonds). On insère donc `list_documents`
  puis **une `rag_search` par fonds** ; les noms étant inconnus au moment du plan (plan
  figé), c'est l'exécuteur qui remplit `source`. Correctif le plus rentable mesuré sur
  les comparaisons.
- **Parsing défensif + exemple « ne pas recopier »** : un LLM dérive parfois vers un
  schéma plus riche (étapes-objets) ou recopie l'exemple tel quel. Mieux vaut récupérer
  un plan imparfait que planter.

---

## 4. Registre d'outils : pourquoi un dict, pas un framework

- **Un simple dict `{nom: {function, description}}`** : extensible en 5 lignes (une
  fonction + une entrée), aucun décorateur ni schéma. **Écarté : le function calling
  natif** — support partiel selon les modèles, et le faire « à la main » via le prompt
  est plus portable et rend le mécanisme visible.
- **Les descriptions disent aussi *quand NE PAS* utiliser l'outil** : une description qui
  énonce seulement ce que fait l'outil laisse un petit modèle confondre des outils
  proches (chercher vs calculer). Comme le catalogue est la **seule** information dont
  dispose le LLM pour choisir, c'est là que le cadrage est le plus rentable — à coût nul.
- **Choix par outil** :
  - `write_file` **confiné à `workspace/`** : sandbox minimale, l'agent n'écrit pas
    ailleurs sur la machine.
  - `calculator` : `eval()` neutralisé par **liste blanche de caractères** + suppression
    des builtins — suffisant pour de l'arithmétique, bien plus simple qu'un parseur. Il
    existe parce que **les LLM sont mauvais en calcul** : déléguer à Python est le cas
    d'école de l'utilité des outils.
  - **Erreurs renvoyées en texte** (pas d'exception) : une erreur devient une
    *observation* que la boucle peut lire et corriger, au lieu de planter.

---

## 5. Boucle agentique : pourquoi ces mécanismes

- **`raison` avant le choix d'outil** : obliger le modèle à justifier *avant* de nommer
  l'outil l'oblige à raisonner (mini chain-of-thought), ce qui réduit les choix absurdes
  (lancer `calculator` au lieu de `rag_search`). Coût nul (même appel), et le raisonnement
  devient inspectable. C'est la **prévention** du « cas 4 » (un outil inadapté qui renvoie
  pourtant un résultat valide, donc indétectable par la réflexion déterministe).
  *Limite résiduelle assumée* : ça corrige le *choix* de l'outil, pas le raisonnement *à
  l'intérieur* (un `calculator` bien choisi peut encoder une mauvaise expression).
- **Mémoire = liste + fichier**, tronquée à 1500 caractères : un petit contexte saturerait
  avec des résultats RAG complets ; 1500 caractères suffisent à savoir ce qu'une étape a
  produit. Persistée dans `notes.md` → on observe l'agent en temps réel et un crash ne perd
  pas le travail. **Écarté : l'historique de conversation complet** (trop volumineux).
- **Réflexion déterministe** (échec = vide ou « Erreur ») plutôt qu'un juge LLM. La version
  initiale faisait juger chaque résultat par un appel LLM : sur un 7B, **beaucoup de faux
  positifs** (« insuffisant » sur des résultats corrects) → relances parasites. La règle
  déterministe **supprime ces retries** et **économise un appel LLM par étape**. Compromis :
  elle ne détecte que les vrais plantages, pas les résultats subtilement incomplets — bon
  arbitrage sur 7B ; avec un modèle plus fiable, on pourrait réintroduire un juge sémantique
  **en complément** (filtrer les erreurs franches *puis* juger la qualité), pas à sa place.
- **`MAX_RETRIES = 1`** : au-delà, le risque de boucler sans converger l'emporte ; une
  correction capture l'essentiel du bénéfice pour un coût borné.

---

## 6. RAG : pourquoi cette stack et ce rejet du hors-sujet

- **La stack (bge-m3 → parent-child → reranker)** : `bge-m3` bat `nomic-embed-text` sur du
  français technique ; le parent-child indexe de petits *children* (précision) mais renvoie
  le *parent* (contexte) ; le reranker apporte le plus gros gain de qualité.
- **Rejet du hors-sujet par juge LLM, pas par seuil** : sur ces corpus, hors-sujet et
  in-corpus se chevauchent autour de ~0,50 — un seuil numérique ne sépare pas. Le juge de
  pertinence (`grade_documents`) écarte les `irrelevant` ; si rien ne subsiste, message
  explicite. C'est ce **filtre**, et non un nombre, qui garantit le **non-invention** quand
  la question sort du corpus. En échange : il faut un LLM disponible.
- **Une collection par dataset, jamais combinées** : étanchéité des corpus (droit ≠ finance) ;
  le moteur n'interroge qu'une collection à la fois. Index **persisté** (construit une fois à
  l'ingestion, pas reconstruit à chaque lancement).
- **Sortie en texte `[source]\ntexte`** : le consommateur est le LLM (qui lit du texte) ;
  afficher la source rend chaque passage traçable.

---

## 7. Couche métriques (*rating fond*) : pourquoi best-effort honnête

- **Un outil par métrique, porteur de ses caractéristiques** : le boss veut que la
  planification choisisse la bonne métrique selon l'intention (Sharpe vs Sortino…). En
  mettant les caractéristiques (pénalise-hausse, tendance, données requises) dans la
  **description** de chaque outil, le planner existant choisit déjà par description — pas
  besoin d'un outil sélecteur séparé. *(Décision actée avec l'utilisateur.)*
- **Calcul best-effort + garde-fou honnête** : un KID/DICI ne contient **ni série de
  rendements, ni R, ni σ** (vérifié sur l'extracteur). On calcule donc si les entrées sont
  fournies (ou lisibles dans une factsheet via `source`), sinon on **explique sans inventer
  de chiffre**. Dire « je ne sais pas » est ici un gage de stabilité, pas un échec — c'est le
  plafond d'information du corpus.
- **Famille « budget » explicative seulement** : CVaR/drawdown sous contrainte exigent un
  univers multi-fonds + une matrice de rendements + un optimiseur (hors repo) → on ne simule
  pas une optimisation qu'on ne peut pas faire (V2).
- **Clarification interactive** : quand deux métriques se valent, l'agent **demande** plutôt
  que de trancher arbitrairement. `ask_fn` est injectable pour rester interactif en CLI sans
  bloquer les démos/éval.

---

## 8. Garde-fous & robustesse : pourquoi consolider et durcir

- **Pourquoi un `GUARDRAILS.md` consolidé** : les règles de sûreté étaient éparpillées dans
  les prompts, l'adaptateur RAG et les outils. Les rassembler dans un document unique
  (chacune pointant son lieu d'application) rend le système **auditable et professionnel** —
  doc seule, zéro changement de comportement.
- **Pourquoi durcir au niveau agent** : un run a planté sur une erreur transport
  (`RemoteProtocolError`) **non** couverte par les retries du client — elle remontait et tuait
  tout. Le filet (retries + `LLMUnavailable`) vit dans `agent/llm.py`, là où les appels ont
  lieu, sans toucher le moteur.
- **Pourquoi une dégradation gracieuse par étage** plutôt qu'un seul try/except global :
  chaque étage a un repli *utile* distinct (sélection ignorée / message clair / étape en
  erreur mais boucle qui continue / repli sur le livrable brut) — on rend toujours quelque
  chose d'exploitable, jamais un crash.

---

## 9. Principe transversal : une garantie structurelle plutôt qu'une consigne de prompt

C'est le fil conducteur des choix les plus importants, né d'une contrainte concrète : **un
petit modèle n'obéit pas de façon fiable à une interdiction de prompt.** « Ne fais pas X »
réduit la fréquence de X sans jamais la supprimer — surtout si le matériau qui permet X reste
sous ses yeux. À chaque fois qu'un comportement *doit* être garanti, on l'a retiré au LLM pour
le confier au **code** (règle déterministe ou restriction de ce qu'il voit).

Trois applications, toutes nées du même échec « le prompt ne suffit pas » :

1. **Réflexion (§5)** — version prompt : « ne juge insuffisant que les vrais échecs » → faux
   positifs constants. Version structurelle : règle déterministe, aucun appel LLM. Le jugement
   n'est plus *demandé*, il est *calculé*.
2. **Cohérence de la synthèse (§1)** — version prompt : passer le livrable *et* la mémoire en
   disant « n'ajoute rien hors du livrable » → réintroduction d'éléments des chunks RAG.
   Version structurelle : ne plus passer la mémoire quand un livrable existe. Privé de la
   source, le modèle **ne peut plus** ajouter — cohérence garantie par construction.
3. **Sélection d'outil (§4-5)** — cas nuancé qui montre la limite : on *prévient* les mauvais
   choix (descriptions cadrées + `raison` obligatoire), mais ce sont encore des leviers de
   prompt. La garantie complète (imposer l'outil dès la planification) a été écartée : trop de
   souplesse perdue. Tout ne peut pas être verrouillé sans coût.

**La leçon et son revers** : faire respecter un invariant par le code est plus robuste que
toute formulation de prompt — mais une garantie structurelle est plus « bête » (la réflexion ne
voit que les plantages francs ; la synthèse ancrée garantit la *cohérence*, pas la *justesse* :
si le livrable est faux, elle reproduit fidèlement le faux). On échange de la finesse contre de
la fiabilité — bon échange sur un petit modèle, à reconsidérer avec un modèle plus capable.

---

## 10. Limites assumées : pourquoi ces simplifications sont volontaires

- **Plan figé** : pas de re-planification globale — on a préféré borner et auditer plutôt que la
  souplesse d'un ReAct qui dérive (§0).
- **Ingestion manuelle, hors agent** : (ré)indexer un corpus est une étape dev séparée ;
  l'index persistant suffit au cas d'usage.
- **Troncature fixe (1500 car.)** plutôt qu'un comptage de tokens : approximation suffisante,
  grossière mais sans coût.
- **Calcul multi-étapes fiabilisé, pas garanti** : décomposition multi-fonds + consigne dure
  « toujours passer par `calculator` » ont nettement amélioré les choses, mais restent des
  **leviers de prompt** (§9). Le verrou dur envisagé (interdire dans `write_file` tout nombre
  non issu d'un `calculator`) a été écarté comme trop intrusif pour le gain.
- **Pas plus d'info que le corpus** : aucune donnée de marché externe — un ratio exigeant une
  série de rendements n'est calculable que si on la fournit (§7).
- **Validation par exécutions + tests des parties déterministes** : les sorties LLM
  interdisent l'assertion sur une chaîne exacte → golden sets, démos rejouables, et tests
  unitaires sur le calcul pur, la sélection et la résilience.
- **Sécurité minimale** : sandbox d'écriture + calculatrice filtrée, mais pas de limite de
  temps ni de quota d'appels LLM.

*Chaque limite indique l'extension naturelle suivante du projet.*
