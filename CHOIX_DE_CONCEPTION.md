# Choix de conception — Mini Deep Agent local (Ollama)

Ce document justifie les choix techniques et architecturaux du projet : pourquoi
chaque composant existe, pourquoi il est construit de cette façon, et quelles
alternatives ont été écartées.

---

## 1. Vision d'ensemble : pourquoi un agent et pas un simple RAG ?

Un RAG classique suit un pipeline figé : question → recherche → réponse. Il
échoue dès que la tâche demande plusieurs actions (chercher, puis calculer,
puis rédiger un fichier). Le choix central du projet est donc d'inverser le
contrôle : **c'est le LLM qui décide quoi faire**, en trois phases :

1. **Planification** : décomposer la tâche en étapes (`agent/planner.py`).
2. **Boucle agentique** : pour chaque étape, choisir un outil, l'exécuter,
   juger le résultat, recommencer si besoin (`agent/executor.py`).
3. **Synthèse** : rédiger la réponse finale à partir des résultats accumulés
   (`main.py`).

Le RAG n'est plus le cœur du système : il devient **un outil parmi d'autres**
dans le registre `TOOLS`. C'est le changement de paradigme principal — l'agent
peut répondre à des questions qui ne passent pas du tout par les documents
(un calcul, la lecture d'un fichier), ou qui en combinent plusieurs.

### Pourquoi "plan d'abord, puis exécution" plutôt qu'une boucle ReAct pure ?

Une alternative classique est ReAct : le LLM décide de l'action suivante à
chaque tour, sans plan préalable. J'ai préféré un plan explicite établi en
amont parce que :

- avec un petit modèle local (7B), une boucle totalement libre dérive vite
  (étapes redondantes, boucles infinies). Le plan borne le nombre d'itérations ;
- le plan est **lisible et auditable** : il est affiché à l'utilisateur et
  sauvegardé dans `workspace/plan.md` avant toute exécution ;
- chaque appel LLM reste simple (un prompt = une décision), ce qui est
  beaucoup plus fiable sur un modèle 7B qu'un méga-prompt qui devrait tout
  gérer à la fois.

Le compromis : le plan ne peut pas être réordonné en cours de route. La
souplesse est récupérée localement par le mécanisme de réflexion (cf. §6).

---

## 2. Stack technique : local et minimal

### Ollama plutôt qu'une API cloud (OpenAI, Anthropic…)

- **Confidentialité** : le cas d'usage est l'analyse de documents internes ;
  rien ne sort de la machine.
- **Coût zéro et reproductibilité** : pas de clé API, le projet tourne
  hors-ligne une fois les modèles téléchargés.
- **Pédagogie** : tout le mécanisme agentique est visible dans le code, sans
  dépendre du "function calling" propriétaire d'un fournisseur.

### `qwen2.5:7b` comme modèle de génération

Choisi car c'est un des meilleurs compromis taille/qualité pour du JSON
structuré et du français à l'époque du développement : assez petit pour
tourner sur une machine de bureau, assez bon pour suivre des consignes de
format. Le modèle est une simple constante (`MODEL` dans `agent/llm.py`),
donc interchangeable en une ligne.

### Embeddings et récupération : délégués au moteur `rag_engine`

La version initiale portait son propre RAG : embeddings `nomic-embed-text`
(constante `EMBED_MODEL` dans `agent/llm.py`) et index NumPy en mémoire. C'était
le bon choix pédagogique au départ — tout le mécanisme tenait en quelques dizaines
de lignes lisibles. Mais sur des corpus réels (prospectus financiers, cours de
droit en PDF de centaines de pages), la similarité cosinus brute sur un petit
modèle d'embedding ne suffit plus : trop de faux positifs, pas de
réordonnancement, pas de rejet fiable du hors-sujet.

Le RAG a donc été remplacé par un **moteur modulaire dédié, `rag_engine/`**,
branché via l'adaptateur `agent/rag.py` (cf. §7). `agent/llm.py` conserve `embed()`
/ `EMBED_MODEL`, mais ils ne sont plus appelés : l'embedding de la récupération est
désormais `BAAI/bge-m3`, à l'intérieur du moteur.

### Deux couches de dépendances, pas une

Le projet a maintenant deux niveaux, assumés :

- **L'agent (`agent/`, `main.py`)** reste minimal : `ollama` pour le LLM
  (`qwen2.5:7b`), aucun framework agentique. Tout le raisonnement (plan, choix
  d'outil, réflexion) est écrit à la main — le but pédagogique, montrer *comment*
  un agent fonctionne, reste intact.
- **Le moteur RAG (`rag_engine/`)** assume des dépendances lourdes
  (sentence-transformers pour bge-m3, le reranker bge, Qdrant) : c'est un composant
  réutilisable, traité comme une brique fournie. L'agent ne le voit qu'à travers le
  contrat mince de `agent/rag.py` (deux fonctions qui renvoient des chaînes).

Ce qui reste écarté : LangChain / LlamaIndex **dans l'agent**. La machinerie
agentique n'emprunte aucun framework ; seul le RAG, partie où la qualité de
récupération prime sur la lisibilité, s'appuie sur une vraie stack.

---

## 3. Couche LLM (`agent/llm.py`) : fiabiliser le JSON

Plusieurs étapes de la machinerie agentique reposent sur des réponses JSON du
modèle (le plan, le choix d'outil — la réflexion, elle, est déterministe, cf.
§6). Or un modèle 7B local produit régulièrement du JSON imparfait. Trois
mécanismes de défense, empilés :

1. **`format="json"` côté Ollama** (`json_mode=True`) : contraint le décodage
   du modèle au niveau du sampling. C'est la première ligne de défense.
2. **Parsing tolérant (`_parse_json`)** : même en mode JSON, le modèle entoure
   parfois sa réponse de ` ```json … ``` ` ou de texte. Le parseur extrait le
   premier bloc de code s'il existe, puis découpe entre la première
   accolade/crochet et la dernière. `strict=False` tolère les retours à la
   ligne bruts dans les chaînes, erreur fréquente des petits modèles.
3. **Retries (`chat_json`, 2 nouvelles tentatives)** : si le parsing échoue
   malgré tout, on rappelle simplement le modèle. Le non-déterminisme du
   sampling fait qu'une nouvelle tentative suffit presque toujours. Au-delà,
   on relance l'exception originale plutôt que de masquer le problème.

Alternative écartée : demander au LLM de "réparer" son propre JSON. Plus
coûteux (un appel de plus systématique) et pas plus fiable qu'un simple retry
sur un cas aussi simple.

---

## 4. Planner (`agent/planner.py`) : un plan court, ancré sur les outils

- **Le catalogue d'outils est injecté dans le prompt de planification.**
  Sans cela, le LLM invente des étapes irréalisables ("envoyer un email").
  En lui montrant ses capacités réelles, chaque étape correspond à un outil
  existant.
- **3 à 7 étapes maximum, une étape = un outil.** Contrainte volontaire :
  chaque étape doit être atomique pour que la sélection d'outil (§5) soit un
  problème trivial. Et borner le plan borne le temps d'exécution total. (Plafond
  porté de 6 à 7 pour laisser la place à la décomposition multi-entités
  ci-dessous.)
- **La dernière étape doit produire le livrable** (généralement `write_file`) :
  cela force le plan à converger vers un résultat concret plutôt qu'une suite
  de recherches sans conclusion.
- **Décomposition des tâches multi-entités (multi-fonds).** Une tâche du type
  « compare 3 fonds » produisait, en une seule étape de recherche globale, des
  passages d'UN seul fonds — la comparaison et le calcul qui suivaient étaient
  alors faux *par construction* (observé sur la 1ʳᵉ version de
  `demo_multi_tache.md` : `2.3 - 0.5373`, deux frais du même fonds). Le planner
  est donc nudgé : sur une tâche portant sur plusieurs documents, il insère une
  étape `list_documents` puis **une étape `rag_search` par fonds**, formulée
  *génériquement* (« le 1ᵉʳ fonds », « le 2ᵉ fonds »…) car les noms ne sont pas
  connus au moment de la planification (le plan est figé, cf. §1 et §10). C'est
  l'**exécuteur** qui, au moment de l'exécution, remplit le paramètre `source`
  de `rag_search` avec le bon fonds tiré du résultat de `list_documents`. Le
  calcul et le livrable n'interviennent qu'*après* avoir collecté la valeur de
  chaque fonds. C'est le correctif le plus rentable mesuré sur les tâches de
  comparaison.
- **Sortie défensive.** Le prompt demande `{"steps": [...]}`, mais le code
  accepte aussi une liste nue, un dict avec une autre clé
  (`list(plan.values())[0]`), et des étapes renvoyées en **objet**
  (`{"step": 1, "action": "…"}`) qu'il renormalise en phrase (`_step_text`) : un
  LLM dérive parfois vers un schéma plus riche. Mieux vaut récupérer un plan
  imparfait que planter.
- **Un exemple de sortie dans le prompt** (few-shot minimal), assorti d'une
  consigne explicite de **ne pas le recopier** : sans elle, le modèle renvoyait
  parfois l'exemple tel quel (« Chercher les informations sur X »), produisant
  un plan dégénéré.

---

## 5. Registre d'outils (`agent/tools.py`) : un dict, pas un framework

### Structure

`TOOLS` est un simple dictionnaire `{nom: {function, description}}`. Ce choix
a deux conséquences voulues :

- **Extensible en 5 lignes** : ajouter un outil = écrire une fonction Python
  et une entrée dans le dict. Pas de décorateur, pas de schéma Pydantic.
- **La description sert de "documentation pour le LLM"** : `tools_catalog()`
  la formate et l'injecte dans les prompts du planner et du sélecteur. La
  description mentionne explicitement les noms et types des arguments, car
  c'est la seule information dont dispose le LLM pour construire `args`.

**Les descriptions disent aussi quand NE PAS utiliser l'outil.** Une
description qui se contente d'énoncer ce que fait l'outil laisse un petit
modèle confondre des outils proches (chercher une info vs. faire un calcul).
Chaque description porte donc une frontière d'usage explicite : `calculator`
précise « sur des nombres DÉJÀ connus… ne pas l'utiliser pour chercher une
information : pour ça, utiliser rag_search » ; `read_file` renvoie vers
`rag_search` pour explorer les documents ; etc. Comme le catalogue est la
seule information dont le LLM dispose pour choisir, c'est là que le cadrage
est le plus rentable — à coût nul (aucun appel LLM supplémentaire). C'est le
versant « prévention » du cas 4, complémentaire de la justification `raison`
(cf. §6).

Alternative écartée : le function calling natif (schémas JSON d'outils passés
à l'API). Ollama le supporte partiellement selon les modèles, mais le faire
"à la main" via le prompt est plus portable et rend le mécanisme visible.

### Choix par outil

- **`rag_search`** : la recherche documentaire, reléguée au rang d'outil
  (cf. §1 et §7).
- **`read_file` / `write_file`** : donnent à l'agent une mémoire persistante
  sur disque et la capacité de produire des livrables. `write_file` est
  **confiné au dossier `workspace/`** : l'agent ne peut pas écrire ailleurs
  sur la machine (sandbox minimale). Le préfixe `workspace/` est retiré s'il
  est présent, car le LLM l'ajoute souvent de lui-même. `read_file` essaie
  d'abord le workspace puis un chemin relatif au projet, pour pouvoir relire
  aussi bien ses propres notes que les documents sources.
- **`calculator`** : `eval()` est dangereux par nature ; il est neutralisé
  par une **liste blanche de caractères** (chiffres et opérateurs uniquement
  — impossible d'écrire un nom de fonction ou d'attribut) plus la suppression
  des builtins. Pour une expression arithmétique, c'est suffisant et bien plus
  simple qu'un parseur dédié. Pourquoi cet outil existe : les LLM sont
  notoirement mauvais en arithmétique ; déléguer le calcul à Python est le
  cas d'école de l'utilité des outils.
- **Convention de robustesse commune** : les outils **retournent leurs
  erreurs sous forme de texte** ("Erreur : fichier introuvable…") au lieu de
  lever des exceptions. Une erreur devient ainsi une observation que le LLM
  peut lire et corriger au tour suivant (via la réflexion), au lieu de faire
  planter la boucle.

---

## 6. Boucle agentique (`agent/executor.py`) : le cœur du système

### Sélection d'outil par étape

À chaque étape, un appel LLM dédié reçoit : la tâche globale, l'étape
courante, le catalogue d'outils, et la mémoire de travail. Il retourne
`{"raison": ..., "tool": ..., "args": {...}}`. Donner la tâche globale **et**
la mémoire permet au modèle de choisir des arguments cohérents avec ce qui a
déjà été trouvé (ex. : écrire le rapport en réutilisant les passages extraits).

`execute_step` valide que l'outil existe et rattrape les `TypeError`
(mauvais arguments) en les renvoyant comme texte — même logique que pour les
outils : l'erreur nourrit la boucle au lieu de la casser.

**Le champ `raison` (justification avant le choix).** La sortie JSON commence
par une justification, *avant* le nom de l'outil. Ce n'est pas cosmétique :
obliger le modèle à écrire pourquoi un outil convient à l'étape l'oblige à
raisonner avant de répondre (un mini *chain-of-thought*), ce qui réduit les
choix absurdes — typiquement lancer `calculator` là où il fallait `rag_search`.
Bonus : la raison est affichée dans les logs, donc le raisonnement de l'agent
devient inspectable. Coût nul : c'est le même appel LLM, juste un champ de plus.

Ce mécanisme attaque le **« cas 4 »** — un outil sémantiquement inadapté mais
qui renvoie un résultat valide (donc non détecté par la réflexion
déterministe, qui ne repère que les erreurs franches). Le cas 4 ne pouvant pas
être *détecté* à moindre coût sur un 7B, on le *prévient* à la source : la
justification (ici) plus des descriptions d'outils qui cadrent l'usage (cf.
§5). C'est volontairement de la prévention, pas de la détection — réintroduire
un juge sémantique resterait la solution de détection, mais seulement avec un
modèle plus fiable (cf. §6, réflexion).

**Limite résiduelle assumée.** Ces deux garde-fous corrigent le *choix* de
l'outil, pas le *raisonnement à l'intérieur* d'un outil bien choisi. Un appel
`calculator` peut être correctement sélectionné tout en encodant une expression
qui traduit une mauvaise interprétation de la question (confondre « la hausse
du coût » avec « 15 % du budget », par exemple). Le bon outil n'a jamais
garanti le bon calcul ; ça relève de la qualité de raisonnement du modèle, hors
de portée de la sélection d'outil.

### Mémoire de travail : une liste + un fichier

La mémoire est une simple liste de dicts `{step, tool, result}` :

- elle est **réinjectée dans chaque prompt** (formatée par `_format_memory`),
  ce qui donne à l'agent le contexte de ses actions passées ;
- chaque résultat est **tronqué à 1500 caractères** dans le prompt : un
  modèle 7B a une fenêtre de contexte limitée, et un résultat de RAG complet
  à chaque étape la saturerait. 1500 caractères suffisent pour que le modèle
  sache ce qu'une étape a produit ;
- elle est **persistée à chaque étape dans `workspace/notes.md`**. Double
  intérêt : on peut observer l'agent "réfléchir" en temps réel en ouvrant le
  fichier, et un crash en cours de route ne perd pas le travail accompli.

Alternative écartée : un historique de conversation complet (tous les
messages). Trop volumineux pour un petit contexte, et la mémoire structurée
par étape est plus facile à tronquer et à relire.

### Réflexion / auto-correction : déterministe, pas confiée au LLM

Après chaque exécution, la fonction `reflect()` juge si l'étape a réussi et,
si non, le feedback est injecté dans une nouvelle tentative de sélection
d'outil ("Tentative précédente insuffisante. Conseil : …").

**La décision est déterministe** : une étape est considérée réussie sauf si
son résultat est vide ou commence par "Erreur". Aucun appel LLM n'est fait
ici. Ce choix repose sur une convention du projet — tous les outils renvoient
leurs échecs sous forme de texte commençant par "Erreur" (cf. §5). Le seul
signal dont la réflexion a réellement besoin ("l'outil a-t-il planté ?") est
donc déjà lisible directement dans la chaîne renvoyée.

**Pourquoi avoir retiré le juge LLM ?** La version initiale demandait à un
appel LLM distinct de juger chaque résultat (`{"sufficient": bool,
"feedback": str}`). En pratique, sur un modèle 7B local, ce juge produisait
beaucoup de **faux positifs** : il marquait "insuffisant" des résultats
parfaitement corrects (un nombre déjà calculé, un document déjà extrait) en
réclamant un perfectionnement inutile, ce qui déclenchait des relances
parasites à presque chaque étape. La règle déterministe a deux bénéfices
mesurés : elle **supprime ces retries inutiles** et elle **économise un appel
LLM par étape** (sur un plan de 5 étapes, 5 allers-retours modèle en moins par
exécution), donc des runs plus rapides.

**Le compromis assumé** : la réflexion est désormais "bête" — elle ne détecte
que les vrais plantages, pas les résultats subtilement incomplets (un résumé
qui oublierait un risque, par exemple). Pour ce projet c'est le bon arbitrage,
parce que le juge LLM 7B faisait plus de faux positifs que de vraies
détections utiles. Avec un modèle plus gros et plus fiable, on pourrait
réintroduire un jugement sémantique — mais **en complément** de la règle
déterministe (d'abord filtrer les erreurs franches, puis juger la qualité),
pas à sa place.

Autres choix de paramétrage :

- **`MAX_RETRIES = 1`** : une seule correction par étape. Au-delà, le risque
  de boucler sans converger l'emporte ; une tentative corrigée capture
  l'essentiel du bénéfice pour un coût borné.
- **Après la dernière tentative, le résultat est gardé tel quel** : un
  résultat imparfait dans la mémoire vaut mieux qu'une étape vide, et la
  synthèse finale peut souvent compenser.

---

## 7. RAG (`agent/rag.py` → moteur `rag_engine`)

Le RAG n'est plus un mini-index maison mais un **adaptateur mince**
(`agent/rag.py`) sur un moteur de récupération modulaire et réutilisable,
`rag_engine/` (cf. §2). L'adaptateur expose exactement le **même contrat
qu'avant** — `rag_search` et `list_sources` renvoient des chaînes — si bien que
`tools.py`, le planner et `main.py` n'ont pas changé. Le reste de l'agent ignore
qu'il y a un vrai moteur derrière.

### Pourquoi un moteur séparé plutôt que l'index NumPy d'origine

L'index NumPy en mémoire (cosinus brut sur `nomic-embed-text`) était parfait
pour démontrer le principe, mais s'effondrait sur des PDF réels : pas de
réordonnancement, pas de découpage parent/enfant, aucun moyen fiable de dire
« ce passage n'a rien à voir avec la question ». Le moteur comble ces trois
manques.

### La stack de récupération (dans le moteur)

Pour chaque requête, `rag_search` enchaîne :

1. **Dense `bge-m3`** : embedding de qualité, multilingue, bien meilleur que
   `nomic-embed-text` sur du français technique.
2. **Parent-Child** : on indexe de petits *children* (précision de la recherche)
   mais on renvoie le *parent* qui les contient (contexte suffisant pour le LLM).
3. **Reranker `bge-reranker-v2-m3`** : réordonne les candidats par pertinence
   réelle à la question — c'est le plus gros gain de qualité (mesures dans
   `rag_engine/README.md`).

On ne renvoie **que les passages**, pas de génération : c'est le LLM de l'agent
qui synthétise, exactement comme avec l'ancien `rag_search`.

### Rejet du hors-sujet : un juge LLM, pas un seuil

Le besoin clé sur des corpus sensibles : ne **rien inventer** quand la question
sort du corpus. Un seuil numérique sur le score du reranker ne marche pas ici —
hors-sujet et in-corpus se chevauchent autour de ~0,50. On utilise donc le
**juge de pertinence LLM** du moteur (prompt `grade_documents`, labels
relevant / ambiguous / irrelevant) : chaque passage récupéré est jugé, on écarte
les `irrelevant`, et si aucun ne subsiste `rag_search` renvoie un message
explicite « aucun passage pertinent ». C'est ce filtre, et non un nombre, qui
garantit le rejet d'une question étrangère au dataset. En échange : il faut un
LLM disponible (Ollama par défaut).

### Une collection par dataset, jamais combinées

Règle d'architecture imposée : **un corpus = une collection Qdrant**, et le
moteur n'en interroge qu'une à la fois — jamais droit et finance mélangés dans
une même recherche. La collection active est choisie par configuration
(`RAG__VECTOR_STORE__COLLECTION`, défaut `dataset_finance`) ; l'index est
**persisté** sur disque dans `rag_engine/data/` (Qdrant local), construit une
fois à l'ingestion et non reconstruit à chaque lancement. L'argument `source`
(optionnel) de `rag_search` restreint en plus la recherche à un document précis
(ex. un ISIN), utile pour comparer des fonds un par un.

### Sortie en texte formaté, pas en objets

`rag_search` retourne une chaîne `[source]\ntexte` et non une structure : le
consommateur est le LLM, qui lit du texte. Afficher la source permet (à l'agent
comme à l'utilisateur qui lit `notes.md`) de tracer d'où vient chaque passage.

---

## 8. Orchestration (`main.py`) et workspace

- **CLI minimaliste** (`python main.py "question"`) : pas d'argparse ni de
  config — un seul argument, la tâche. Les mots de `sys.argv` sont joints
  pour tolérer une question non quotée.
- **La synthèse finale est un appel LLM séparé**, hors de la boucle. Séparer
  "agir" et "rédiger" donne une réponse plus propre que de retourner le
  résultat brut de la dernière étape. **Elle s'ancre sur le livrable, pas sur
  la mémoire** : si l'agent a écrit un fichier pendant la boucle
  (`last_deliverable`), la synthèse reçoit *uniquement* ce livrable et le
  reformule, sans voir la mémoire de travail. Sinon (aucun fichier écrit),
  elle retombe sur l'ancien mode "synthèse à partir de toute la mémoire". Le
  pourquoi de cette séparation stricte est détaillé en §9.
- **Le rapport est toujours écrit dans `workspace/rapport.md`** par le code
  (pas seulement si le plan l'a prévu) : garantie qu'un livrable existe quoi
  qu'il arrive.
- **Le dossier `workspace/` matérialise l'état mental de l'agent** :
  `plan.md` (ce qu'il compte faire), `notes.md` (ce qu'il a appris),
  `rapport.md` (ce qu'il conclut). C'est à la fois la mémoire de l'agent et
  son outil de transparence vis-à-vis de l'utilisateur.
- **Affichage de progression** à chaque étape (outil choisi, arguments,
  début du résultat, verdicts de réflexion) : indispensable pour déboguer un
  système non déterministe.

---

## 9. Principe transversal : une garantie structurelle plutôt qu'une consigne de prompt

C'est le fil conducteur des choix les plus importants du projet, et il vient
d'une contrainte concrète : **un modèle 7B local n'obéit pas de façon fiable à
une interdiction formulée dans le prompt.** Lui écrire « ne fais pas X » réduit
la fréquence de X, mais ne le supprime jamais — surtout si le matériau qui
permet de faire X reste sous ses yeux. À chaque fois qu'un comportement *doit*
être garanti, on l'a donc retiré au LLM pour le confier au code (une règle
déterministe ou une restriction de ce qu'il voit), au lieu de l'espérer d'une
consigne.

Trois applications concrètes, toutes nées du même échec « le prompt ne suffit
pas » :

1. **Réflexion / auto-correction (§6).** Version prompt : demander au LLM de ne
   juger « insuffisant » que les vrais échecs → il marquait sans cesse
   insuffisants des résultats corrects. Version structurelle : une règle
   déterministe (échec = résultat vide ou commençant par « Erreur »), aucun
   appel LLM. Le jugement n'est plus *demandé*, il est *calculé*.

2. **Cohérence de la synthèse finale (§8).** Version prompt : passer le
   livrable *et* toute la mémoire à la synthèse en lui disant « n'ajoute rien
   qui ne soit dans le livrable » → elle réintroduisait quand même des éléments
   tirés des chunks RAG encore présents dans le contexte. Version structurelle :
   ne plus passer la mémoire du tout quand un livrable existe. Privé de la
   source, le modèle **ne peut plus** ajouter d'éléments absents — la cohérence
   est garantie par construction, pas espérée d'une consigne.

3. **Sélection d'outil (§5, §6).** Cas plus nuancé, qui montre la limite du
   principe. On a *prévenu* les mauvais choix par des descriptions d'outils qui
   cadrent l'usage et un champ `raison` obligatoire — mais ce sont encore des
   leviers de prompt, donc partiels. La garantie structurelle complète
   (imposer l'outil dès la planification) a été écartée car elle retirait trop
   de souplesse. C'est le rappel que tout ne peut pas être verrouillé sans coût.

**La leçon, et son revers.** Quand un invariant compte, le faire respecter par
le code (ou en privant le modèle de la possibilité de le violer) est plus
robuste que toute formulation de prompt. Le revers : une garantie structurelle
est plus « bête » — la réflexion déterministe ne détecte que les plantages
francs (§6), et la synthèse ancrée sur le livrable garantit la *cohérence* mais
pas la *justesse* (si le livrable est faux, elle reproduit fidèlement le faux,
§8). On échange de la finesse contre de la fiabilité — un bon échange sur un
7B, à reconsidérer avec un modèle plus capable.

---

## 10. Limites connues et assumées

Ces simplifications sont volontaires, à l'échelle d'un projet de démonstration :

- **Plan figé** : pas de re-planification globale en cours d'exécution ; seule
  la correction locale par étape existe.
- **Ingestion manuelle, hors de l'agent** : l'index RAG est persistant
  (`rag_engine/data/`, Qdrant) mais l'agent ne sait pas (ré)indexer un corpus —
  c'est une étape dev séparée (`python -m rag.ingestion.cli`). Ajouter un document
  suppose de le déposer dans `documents/<dataset>/` puis de relancer l'ingestion.
- **Troncature fixe** (1500 caractères par résultat dans la mémoire injectée)
  plutôt qu'un comptage de tokens : approximation suffisante, mais grossière.
- **Calcul et comparaison multi-étapes : fiabilisés, pas garantis.** Enchaîner
  « récupérer des chiffres puis les combiner » reste le point dur. Deux
  correctifs (mesurés sur `demo_multi_tache.md`) l'ont nettement amélioré :
  (1) la **décomposition multi-fonds** du planner (§4), qui donne au calcul les
  bonnes valeurs de *chaque* fonds au lieu d'un seul ; (2) une **consigne dure**
  poussant l'agent à toujours passer par l'outil `calculator` plutôt que de
  calculer « de tête » dans le texte (descriptions d'outils renforcées + règle de
  sélection). Mais ce sont des **leviers de prompt, pas des verrous** (§9) : d'un
  run à l'autre, l'agent appelle le `calculator` plus souvent qu'avant sans
  garantie, et peut encore extraire le mauvais opérande d'un passage. Le verrou
  structurel envisagé — interdire dans `write_file` tout nombre non issu d'un
  résultat `calculator` — a été écarté comme trop intrusif pour le gain.
- **Validation par exécutions, pas par tests unitaires de bout en bout.** Le
  système étant non déterministe, on valide par des **golden sets** côté
  récupération (`tests/`, lancés via `python -m tests.rag_eval.run`) et par des
  **démos rejouables** (`demo_30_questions*.md`, `demo_comparaison.md`,
  `demo_multi_tache.md`) — comparées à l'œil — plutôt que par des assertions sur
  une chaîne exacte, impossibles sur des sorties LLM.
- **Sécurité minimale** : sandbox d'écriture limitée au workspace et
  calculatrice filtrée, mais pas de limite de temps ni de quota d'appels LLM.

Chacune de ces limites indique l'extension naturelle suivante du projet.
