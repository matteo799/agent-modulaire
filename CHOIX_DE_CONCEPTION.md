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

### `nomic-embed-text` pour les embeddings

Modèle d'embedding léger, dédié (séparé du modèle de chat), standard dans
l'écosystème Ollama. Là aussi une constante (`EMBED_MODEL`).

### Dépendances réduites à `ollama` + `numpy`

Choix délibéré de **ne pas utiliser LangChain / LlamaIndex** ni de base
vectorielle (Chroma, FAISS) :

- le corpus visé est petit (quelques fichiers) — un index NumPy en mémoire
  suffit largement ;
- chaque mécanisme (chunking, similarité cosinus, boucle d'agent) est écrit
  explicitement, donc compréhensible et débogable ligne par ligne ;
- pas de magie cachée dans un framework : c'est le but du projet de montrer
  *comment* un agent fonctionne.

---

## 3. Couche LLM (`agent/llm.py`) : fiabiliser le JSON

Toute la machinerie agentique repose sur des réponses JSON (plan, choix
d'outil, verdict de réflexion). Or un modèle 7B local produit régulièrement du
JSON imparfait. Trois mécanismes de défense, empilés :

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
- **3 à 6 étapes maximum, une étape = un outil.** Contrainte volontaire :
  chaque étape doit être atomique pour que la sélection d'outil (§5) soit un
  problème trivial. Et borner le plan borne le temps d'exécution total.
- **La dernière étape doit produire le livrable** (généralement `write_file`) :
  cela force le plan à converger vers un résultat concret plutôt qu'une suite
  de recherches sans conclusion.
- **Sortie défensive** : le prompt demande `{"steps": [...]}`, mais le code
  accepte aussi une liste nue ou un dict avec une autre clé
  (`list(plan.values())[0]`), car les petits modèles ne respectent pas
  toujours le schéma exact. Mieux vaut récupérer un plan imparfait que
  planter.
- **Un exemple de sortie dans le prompt** (few-shot minimal) : montrer le
  format attendu est plus efficace que le décrire.

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
`{"tool": ..., "args": {...}}`. Donner la tâche globale **et** la mémoire
permet au modèle de choisir des arguments cohérents avec ce qui a déjà été
trouvé (ex. : écrire le rapport en réutilisant les passages extraits).

`execute_step` valide que l'outil existe et rattrape les `TypeError`
(mauvais arguments) en les renvoyant comme texte — même logique que pour les
outils : l'erreur nourrit la boucle au lieu de la casser.

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

### Réflexion / auto-correction

Après chaque exécution, un appel LLM distinct juge le résultat :
`{"sufficient": bool, "feedback": str}`. Si insuffisant, le feedback est
injecté dans une nouvelle tentative de sélection d'outil ("Tentative
précédente insuffisante. Conseil : …").

Choix de paramétrage :

- **`MAX_RETRIES = 1`** : une seule correction par étape. Au-delà, on observe
  des boucles où le modèle juge éternellement "insuffisant" sans converger ;
  une tentative corrigée capture l'essentiel du bénéfice pour un coût borné.
- **Après la dernière tentative, le résultat est gardé tel quel** : un
  résultat imparfait dans la mémoire vaut mieux qu'une étape vide, et la
  synthèse finale peut souvent compenser.
- **Si la réflexion elle-même plante** (JSON invalide), on considère l'étape
  réussie (`sufficient: True`). C'est un choix "fail-open" assumé : la
  réflexion est une optimisation, pas un point de défaillance acceptable.
- Le résultat est tronqué à 2000 caractères pour le juge : il évalue la
  *forme* de la réussite, pas chaque détail.

---

## 7. RAG (`agent/rag.py`) : minimal mais avec un fallback

### Chunking par caractères, avec recouvrement

Découpage en fenêtres de **800 caractères avec 150 de recouvrement**, sans
respecter les phrases ni les paragraphes. Pourquoi si simple :

- 800 caractères ≈ un paragraphe : assez grand pour porter une idée, assez
  petit pour que le top-3 tienne dans le contexte du modèle ;
- le recouvrement évite qu'une information à cheval sur deux chunks soit
  coupée et devienne introuvable ;
- un découpage sémantique (par titres, par phrases) serait meilleur mais
  ajoute de la complexité non justifiée pour un corpus de démonstration.

### Index en mémoire, reconstruit à la volée

L'index (`RagIndex`) est construit **paresseusement au premier `search`**, en
RAM, sans persistance. Justification : avec quelques fichiers, l'indexation
prend une seconde — sauvegarder/invalider un index sur disque serait de la
complexité pure. Les vecteurs sont **normalisés à la construction**, ce qui
réduit la similarité cosinus à un simple produit matriciel (`vectors @ q`).

### Fallback lexical si les embeddings sont indisponibles

Si `nomic-embed-text` n'est pas installé (ou qu'Ollama échoue), l'index
retombe sur un **score de recouvrement de mots** (proportion des mots de la
requête présents dans le chunk, mots de moins de 3 lettres ignorés). C'est
une dégradation gracieuse délibérée : le projet reste démontrable avec le
seul modèle de chat, avec une recherche moins fine mais fonctionnelle.

### Sortie en texte formaté, pas en objets

`rag_search` retourne une chaîne `[source — score]\ntexte` et non une
structure : le consommateur est le LLM, qui lit du texte. Afficher la source
et le score lui permet (et permet à l'utilisateur qui lit les notes) de juger
la fiabilité des passages.

---

## 8. Orchestration (`main.py`) et workspace

- **CLI minimaliste** (`python main.py "question"`) : pas d'argparse ni de
  config — un seul argument, la tâche. Les mots de `sys.argv` sont joints
  pour tolérer une question non quotée.
- **La synthèse finale est un appel LLM séparé**, hors de la boucle : il
  reçoit la tâche initiale et toute la mémoire de travail, et rédige la
  réponse utilisateur. Séparer "agir" et "rédiger" donne une réponse beaucoup
  plus propre que de retourner le résultat brut de la dernière étape.
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

## 9. Limites connues et assumées

Ces simplifications sont volontaires, à l'échelle d'un projet de démonstration :

- **Plan figé** : pas de re-planification globale en cours d'exécution ; seule
  la correction locale par étape existe.
- **Pas de persistance de l'index RAG** ni de gestion de gros corpus
  (l'embedding de tous les chunks se refait à chaque lancement).
- **Troncatures fixes** (1500/2000 caractères) plutôt qu'un comptage de
  tokens : approximation suffisante, mais grossière.
- **Pas de tests automatisés** : le système étant non déterministe de bout en
  bout, la validation s'est faite par exécutions répétées sur le scénario
  `documents/projet_alpha.md` (analyse de risques), dont le résultat est
  visible dans `workspace/rapport.md`.
- **Sécurité minimale** : sandbox d'écriture limitée au workspace et
  calculatrice filtrée, mais pas de limite de temps ni de quota d'appels LLM.

Chacune de ces limites indique l'extension naturelle suivante du projet.
