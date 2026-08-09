# Présentation produit — *Agent modulaire* (rating fond)

> **Trame prête à copier dans PowerPoint / Google Slides.** Chaque slide donne :
> le **titre**, les **puces** à afficher (courtes, lisibles de loin) et les **notes
> orateur** (ce que tu dis). Audience mixte business + tech : on ouvre sur la
> valeur et une démo, la technique vient ensuite, allégée.
>
> **Durée cible : ~20 min** + 5 min démo live + Q/R. 15 slides (+ 2 en annexe).
> Conseil : slides 4 (démo) et 7 (règle d'or) sont les moments forts — ralentis là.

---

## Slide 1 — Titre

**Affiché :**
- **Agent modulaire**
- L'assistant qui analyse nos fonds — et qui *n'invente jamais un chiffre*
- [Ton nom] · [Date] · [Équipe]

**Notes orateur :**
> Bonjour à tous. Aujourd'hui je vous présente un produit qu'on a construit en
> interne : un agent d'intelligence artificielle capable d'analyser nos fonds
> d'investissement et de répondre à des questions comme le ferait un analyste —
> mais avec une garantie qu'aucun outil grand public ne vous donne : il refuse
> d'inventer. Je vais vous montrer ce qu'il fait, puis comment on l'a rendu
> fiable et sûr pour un usage professionnel.

---

## Slide 2 — Le problème

**Affiché :**
- Analyser un fonds = fastidieux : prospectus, NAV, ratios, comparaisons
- Les IA grand public (ChatGPT & co.) **hallucinent** des chiffres → inutilisable en finance
- Un RAG classique répond à *une* question simple — pas à une tâche en plusieurs étapes

**Notes orateur :**
> Le point de départ. Répondre à une question de gérant — « compare ces deux
> fonds sur le Sharpe et l'impact des frais sur 10 ans » — demande d'aller
> chercher des données à plusieurs endroits, de calculer, de comparer. C'est long.
> On aimerait déléguer ça à une IA. Problème : une IA généraliste va vous sortir
> un ratio de Sharpe qui *sonne* juste mais qui est inventé. En finance, un
> chiffre faux avec assurance, c'est pire que pas de réponse. Et un simple moteur
> de recherche documentaire (« RAG ») ne sait pas enchaîner plusieurs étapes.

---

## Slide 3 — Ce qu'on a construit

**Affiché :**
- Un **agent** : il *planifie*, *choisit ses outils*, *exécute en boucle*, *synthétise*
- Spécialisé **analyse de fonds** : caractéristiques, performances, risque, comparaisons
- Règle d'or : **le corpus est le plafond** — pas de donnée ⇒ « je ne sais pas »

**Notes orateur :**
> Ce qu'on a construit n'est pas un chatbot de plus. C'est un *agent* : face à une
> question, il établit un plan, choisit les bons outils un par un, exécute, et
> rédige une réponse finale sourcée. Il est spécialisé sur notre métier : analyse
> de fonds. Et surtout, il obéit à une règle non négociable, gravée dans le code :
> il ne dit que ce que les documents et les données contiennent. S'il ne sait pas,
> il le dit. Dire « je ne sais pas », pour nous, c'est un succès, pas un échec.

---

## Slide 4 — Démo (moment fort)

**Affiché :**
- Exemple : *« Compare le fonds A et le fonds B, et projette l'impact des frais sur 10 ans »*
- [Capture ou démo live : plan → outils → rapport final]
- 24 questions de gérant enchaînées sans intervention → `demos/demo_Amundi.md`

**Notes orateur :**
> *(Idéalement démo live ; sinon captures.)* Regardez ce qui se passe. Je pose une
> question complexe. L'agent affiche d'abord son **plan**. Puis il déroule : il
> liste les fonds, cherche les données de chacun, calcule le Sharpe *avec une
> calculatrice* — pas de tête —, projette les frais, et écrit un rapport. À la fin,
> une réponse claire et traçable. On a rejoué **24 questions d'un gérant** d'affilée,
> sans aucune aide : tout est documenté dans le dépôt. C'est ça, le produit.

---

## Slide 5 — Comment ça marche (vue simple)

**Affiché :**
- **0.** Comprendre l'intention (quelle métrique ? clarifier si ambigu)
- **1.** Planifier → liste d'étapes
- **2.** Boucle : choisir un outil → exécuter → vérifier → mémoriser
- **3.** Synthétiser une réponse finale ancrée sur le livrable

**Notes orateur :**
> Sans entrer dans le code : quatre temps. D'abord il cerne l'intention — si vous
> parlez de risque de baisse, il sait qu'il faut un ratio de Sortino plutôt qu'un
> Sharpe, et si c'est ambigu, il *vous* demande. Ensuite il planifie. Puis il
> exécute étape par étape, avec une mémoire de travail. Enfin il rédige. Chaque
> étape est inspectable : on voit *pourquoi* il a choisi tel outil.

---

## Slide 6 — Ce qu'il sait faire (28 outils) + le moteur RAG maison

**Affiché :**
- **Faits & documents** : fiche d'un fonds, **recherche sémantique dans les prospectus**
- **Risque/rendement** : Sharpe, Sortino, volatilité, max drawdown, VaR/CVaR…
- **Multi-fonds** : comparaison, corrélation, screening / palmarès
- **Placement** : valeur d'un investissement, impact des frais dans le temps
- 🔎 **Notre RAG n'est pas un RAG de base** : bge-m3 → parent-child → reranker → **juge LLM**

**Notes orateur :**
> Un aperçu de la boîte à outils, regroupée par famille. Il lit les faits d'un
> fonds (frais, SFDR, SRI, gérant…), il calcule tout le profil de risque sur
> l'historique de valeur liquidative, il compare plusieurs fonds, il fait du
> screening — « les 5 meilleurs fonds actions Article 8 par Sortino » — et il
> répond à des questions patrimoniales concrètes comme « combien valent 100 000 €
> placés il y a 3 ans ». 28 outils au total.
>
> **Et c'est ici que je veux m'arrêter sur un outil en particulier : notre moteur
> de recherche documentaire — le RAG.** Dans notre architecture, le RAG n'est
> qu'un outil parmi 28 — mais cet outil-là, on ne l'a pas pris sur l'étagère :
> c'est un moteur maison, à l'état de l'art, en quatre étages.
>
> 1. **Embedding bge-m3** — un modèle multilingue de haute qualité : il comprend
>    une question en français comme un prospectus en anglais.
> 2. **Parent-child** — on indexe de *petits* fragments pour la précision, mais on
>    renvoie le *paragraphe entier* pour le contexte. On gagne sur les deux tableaux.
> 3. **Reranker (bge-reranker-v2-m3)** — il réordonne les passages par pertinence
>    réelle. C'est le plus gros gain de qualité de toute la chaîne.
> 4. **Juge de pertinence LLM** — l'étage décisif : chaque passage est jugé
>    pertinent ou non. Si rien ne l'est, l'agent répond « aucun passage pertinent »
>    plutôt que d'affabuler. **C'est ce juge — et pas un simple score numérique —
>    qui garantit qu'une question hors sujet est refusée.**
>
> Résultat : quand l'agent cite un prospectus, il cite le bon passage, ou il se
> tait. C'est ce moteur qui rend la règle d'or — « jamais de chiffre inventé » —
> tenable côté documents.

---

## Slide 7 — La règle d'or : jamais de chiffre inventé (moment fort)

**Affiché :**
- Un prospectus (KID) ne contient pas de série de rendements → calcul impossible
- Dans ce cas, l'agent **explique la métrique** sans fabriquer de valeur
- Tout calcul passe par une **calculatrice** (vérifiable), jamais « de tête »

**Notes orateur :**
> C'est le cœur de la confiance. Prenez le ratio de Sharpe : il faut une série de
> rendements pour le calculer. Un prospectus n'en contient pas. Une IA classique
> vous inventerait quand même un nombre. Le nôtre, non : il vous dit précisément
> *pourquoi* il ne peut pas le calculer, et ce qu'il faudrait. Et quand un calcul
> est possible, il ne le fait jamais de tête — il passe par une calculatrice, donc
> c'est reproductible et auditable. C'est ce qui rend l'outil utilisable en réunion
> d'investissement.

---

## Slide 8 — Sécurité & anti-détournement

**Affiché :**
- Aligné **OWASP LLM Top 10** — garanties par le **code**, pas par un prompt
- Bloque : jailbreak / injection, hors-périmètre, fuite de secrets, exécution de code
- Résiste même à un **document piégé** du corpus (injection indirecte)

**Notes orateur :**
> Un agent qui manipule des documents et exécute des outils, ça ouvre des risques.
> On a une couche de sécurité complète, alignée sur le référentiel OWASP dédié aux
> IA. Elle refuse les tentatives de détournement (« ignore tes instructions »…),
> les questions hors de notre métier, empêche l'agent de lire un fichier de secrets
> ou d'exécuter du code arbitraire. Et — point souvent oublié — elle neutralise le
> cas où un document du corpus lui-même contiendrait une instruction piégée.
> Important : ce ne sont pas des consignes qu'on *espère* voir respectées, ce sont
> des barrières dans le code.

---

## Slide 9 — Prêt pour la production : gouvernance

**Affiché :**
- **Budget / kill-switch** : borne dure sur le coût et le temps de chaque requête
- **Piste d'audit** : chaque décision journalisée (traçabilité, incidents)
- **Résilience** : une panne réseau ne fait jamais planter — dégradation gracieuse

**Notes orateur :**
> Passer d'une démo à un produit, c'est ça qui compte. Trois briques. Un, un
> plafond de ressources : aucune requête ne peut consommer sans limite, même si le
> plan part en vrille — maîtrise des coûts. Deux, une piste d'audit : chaque run
> est journalisé — la question, le plan, chaque outil appelé, le résultat. Si un
> jour une réponse pose question, on peut rejouer exactement ce qui s'est passé.
> C'est la base d'une IA gouvernée. Trois, la résilience : si le service IA a un
> hoquet réseau, l'agent dégrade proprement au lieu de crasher.

---

## Slide 10 — Qualité mesurée, pas affirmée

**Affiché :**
- Tests automatisés sur les parties déterministes (calculs, outils, sécurité) — CI
- Golden set : couverture d'outils mesurée question par question
- Comparaison de modèles : **Opus 4.8 = 14/15** · Haiku 4.5 = 12/15

**Notes orateur :**
> On ne se contente pas de dire « ça marche ». Les parties déterministes — les
> calculs de ratios, la sécurité — sont couvertes par des tests automatiques qui
> tournent à chaque modification. Et on évalue l'agent de bout en bout sur un jeu
> de questions de référence, en mesurant s'il choisit les bons outils. On a même
> comparé deux modèles : le grand, Opus 4.8, route correctement 14 tâches sur 15 ;
> un modèle plus léger, 12 — ce qui nous dit précisément où se situe le gain de
> capacité. C'est une démarche d'ingénierie, pas de la magie.

---

## Slide 11 — La valeur pour l'entreprise

**Affiché :**
- **Gain de temps** : une analyse multi-étapes en secondes, pas en heures
- **Confiance** : réponses sourcées, chiffres vérifiables, zéro hallucination
- **Passage à l'échelle** : conçu pour ~100 datasets/fonds, un corpus étanche par dataset

**Notes orateur :**
> Concrètement, qu'est-ce que ça nous apporte ? Du temps : ce qu'un analyste met
> une heure à assembler, l'agent le fait en quelques secondes, en montrant son
> travail. De la confiance : tout est sourcé et vérifiable, et il ne bluffe jamais.
> Et c'est pensé pour grandir : l'architecture supporte une centaine de fonds ou de
> corpus, chacun étanche — pas de fuite d'un dataset à l'autre. C'est un socle, pas
> un prototype jetable.

---

## Slide 12 — Ce qu'il ne fait pas (encore)

**Affiché :**
- Pas de données de marché externes : ratios exigeant une série ⇒ seulement si fournie
- Optimisation de portefeuille (budget CVaR/drawdown) : **explicative**, pas encore calculée
- Ingestion des documents : manuelle, hors agent

**Notes orateur :**
> Par honnêteté — la même honnêteté qu'on exige de l'agent — voici ses limites
> assumées. Il ne va pas chercher de données de marché en dehors de notre corpus.
> L'optimisation de portefeuille complète, il l'explique mais ne la calcule pas
> encore — ça demande un moteur dédié. Et l'ajout de nouveaux documents est
> aujourd'hui une étape manuelle. Rien de bloquant : ce sont nos prochaines marches.

---

## Slide 13 — Prochaines étapes

**Affiché :**
- Élargir le corpus (plus de fonds, plus de gammes)
- Optimisation de portefeuille réelle (famille CVaR/drawdown)
- Interface (Streamlit existante) → déploiement pour les équipes métier
- Garde-fou côté sortie + politique de rétention des données

**Notes orateur :**
> La suite. On étend le catalogue de fonds. On attaque l'optimisation de
> portefeuille réelle. On a déjà une interface web ; l'étape est de la déployer pour
> que vous puissiez l'essayer vous-mêmes. Et on continue de durcir la gouvernance —
> un filtre sur les réponses produites, une politique claire de conservation des
> journaux. Vos retours vont nourrir cette feuille de route.

---

## Slide 14 — En résumé

**Affiché :**
- Un **agent** d'analyse de fonds, pas un chatbot
- **Honnête** (jamais d'invention) · **Sûr** (OWASP LLM) · **Gouverné** (budget + audit)
- Mesuré, résilient, prêt à passer à l'échelle

**Notes orateur :**
> Si vous ne retenez que trois choses. Un : c'est un agent qui raisonne et agit, pas
> un chatbot. Deux : il est honnête et sûr — il n'invente rien et il résiste au
> détournement. Trois : il est gouverné et mesuré, donc prêt pour un usage
> professionnel. C'est un produit sur lequel on peut s'appuyer en confiance.

---

## Slide 15 — Merci / échangeons

**Affiché :**
- Questions ?
- Envie de l'essayer sur vos fonds ? → [contact / lien]
- Doc : `README.md` · `architecture.md` · `GUARDRAILS.md`

**Notes orateur :**
> Merci. Je serais ravi de le lancer sur *vos* cas d'usage — dites-moi les
> questions que vous vous posez au quotidien sur nos fonds, et on regarde ensemble
> ce que l'agent répond. Place à vos questions.

---

## Annexe A — Architecture technique (si audience technique / Q&R)

**Affiché :**
- Agent écrit à la main (planner / executor / mémoire) — **aucun framework agentique**
- Moteur RAG modulaire (stack détaillée slide 6) : **1 collection par dataset, étanche**
- LLM unique configuré à un endroit (Claude Opus 4.8 par défaut ; bascule Ollama possible)

**Notes orateur :**
> Pour les curieux : le raisonnement de l'agent est écrit à la main, volontairement,
> sans framework — on maîtrise chaque décision, chaque appel d'outil est inspectable.
> Le moteur RAG, je vous l'ai détaillé slide 6 ; j'ajoute juste ici une règle
> d'architecture importante : **un corpus par dataset, jamais mélangés** — les
> prospectus finance et, disons, des documents de droit vivent dans des collections
> séparées, aucune fuite de l'un vers l'autre. Et tout le monde partage le même LLM,
> configuré à un seul endroit — on change de modèle en une ligne, y compris pour du
> 100 % local via Ollama si la confidentialité l'exige.

---

## Annexe B — Les garde-fous en une table (si question « et si ça se trompe ? »)

**Affiché :**
- Refus hors-corpus **déterministe** (avant tout appel au modèle)
- Calcul **obligatoirement** outillé + recopie seule dans le livrable
- Sécurité couche 6 : gate d'entrée, confinement fichiers, calcul AST, anti-injection
- Budget + audit + dégradation gracieuse

**Notes orateur :**
> Et la question qui fâche : « et s'il se trompe ? ». La réponse est qu'on a empilé
> des filets déterministes. S'il n'a pas trouvé l'info, le refus est décidé par le
> code avant même d'interroger le modèle. Les chiffres sont calculés par outil et
> seulement recopiés. La sécurité et la gouvernance qu'on a vues complètent le
> tout. L'objectif n'est pas un agent parfait — c'est un agent dont les erreurs
> possibles sont bornées, visibles et traçables.
