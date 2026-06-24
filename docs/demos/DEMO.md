# Démo Harness — exemple de sortie

Parcours produit complet sur 3 questions du dataset finance.
Pipeline : **plan → récupération (dense BGE-M3 → parent-child → reranker k=6) → génération ancrée & citée → synthèse client**.
LLM : claude-sonnet-4-6 (génération) ; embeddings + reranker en local. CRAG désactivé pour la latence.

Rejouer :  `python demo.py`

```
══════════════════════════════════════════════════════════════════════════════
  HARNESS — démo produit : agent + RAG modulaire (Corrective RAG)
══════════════════════════════════════════════════════════════════════════════
  collection : dataset_finance    reranker : ON (k=6, mps)
  pipeline   : retrieve → reranker → génération ancrée + citée (CRAG off pour la latence)
  LLM        : claude-sonnet-4-6 (via https://api.meai.cloud/v1)
  chargement des modèles d'embedding + reranker…
  prêt en 0.3s


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  QUESTION 1/3  « Quels objectifs de gestion et stratégies d'investissement les fonds mettent-ils en œuvre ? »
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

┌────────────────────────────────────────────────────────────────────────────┐
│ 1  PLANIFICATION — l'agent décompose la tâche                             │
└────────────────────────────────────────────────────────────────────────────┘
   1. Lister les documents disponibles avec list_documents pour identifier les fonds
   2. Rechercher les objectifs de gestion avec rag_search(query='objectifs de gestion stratégie investissement policy')
   3. Rechercher les informations spécifiques à chaque fonds identifié avec rag_search(query='objectifs gestion stratégie investissement', source='[ISIN ou nom du fonds]') pour chaque fonds
   4. Synthétiser les résultats trouvés et rédiger le rapport final avec write_file(path='rapport_objectifs_strategies.md', content='[synthèse des objectifs et stratégies par fonds]')
   ⏱ étape : 33.8s

┌────────────────────────────────────────────────────────────────────────────┐
│ 2  RÉCUPÉRATION — dense BGE-M3 → parent-child → reranker → génération ancrée│
└────────────────────────────────────────────────────────────────────────────┘
   ● retrieve — dense BGE-M3 → parent-child → reranker (top 6)  ⏱ 38.5s
      1. [score 0.731] Propectus-2.PDF p.4  1 / 17 Le Fonds a pour objectif d’avoir la même performance que celle du maître diminué de…
      2. [score 0.729] FR001400NKV7.pdf p.7  1. Stratégies utilisées MACROSPHERE GLOBAL FUND 8 Le fonds offre une gestion active, de ty…
      3. [score 0.727] FCPI Amundi Avenir Innovation 4 FINAL 20SEP2024.pdf p.5  3.1.2.1. Stratégie d’investissement du Quota Innovant La stratégie d’investissement mise e…
      4. [score 0.727] Propectus.PDF p.5  1. Objectif de gestion Le Fonds a pour objectif la recherche de la performance, en privilé…
      5. [score 0.718] FR0010883017.pdf p.5  3. Stratégie d’investissement I. Stratégies utilisées : Le fonds peut, à titre accessoire,…
      6. [score 0.710] 990000075919.pdf p.3  TITRE I - IDENTIFICATION Article 1 - Dénomination Le Fonds a pour dénomination : « GAY-LUS…
   ● contexte — 6 passages transmis au générateur  ⏱ 0.0s
   ● generate — rédaction ancrée sur les passages retenus  ⏱ 50.5s
   ● ground_check — vérification anti-hallucination : ✓ ancrée (grounded)  ⏱ 0.0s
   ⏱ total récupération+génération : 89.0s

   Réponse ancrée du RAG :
   Les fonds présentés mettent en œuvre des objectifs et stratégies variés.
   Un premier fonds vise à reproduire la performance de son fonds maître et
   à surperformer l'indice MSCI World en sélectionnant des actions
   internationales à fort potentiel [1]. Le fonds MACROSPHERE GLOBAL FUND
   pratique une gestion active de type rendement absolu sur les taux
   souverains et les changes via une approche macroéconomique et intègre
   des critères ESG [2]. Le Quota Innovant investit en capital-risque et
   capital-développement dans des sociétés innovantes des secteurs de
   l'énergie, la santé, l'industrie 4.0 et le digital [3]. Un autre fonds
   recherche la performance sur les marchés actions de la zone euro par une
   sélection active d'OPCVM [4]. Le fonds GAY-LUSSAC HERITAGE SELECTION
   CREDIT gère activement un portefeuille obligataire diversifié avec une
   sensibilité aux taux entre -2 et 10, en utilisant des dérivés pour
   optimiser la gestion des risques [5]. Enfin, le FCPE GAY-LUSSAC
   TRESORERIE cherche à surperformer un indice mixte composé de l'€STR et
   d'obligations gouvernementales en investissant dans des fonds monétaires
   et obligataires avec une gestion active de la sensibilité et du crédit
   [6].

┌────────────────────────────────────────────────────────────────────────────┐
│ 3  SYNTHÈSE — l'agent rédige la réponse client                            │
└────────────────────────────────────────────────────────────────────────────┘
   Nos fonds couvrent des stratégies diversifiées, allant de la
   reproduction de la performance d'un fonds maître avec sélection
   d'actions internationales, à la gestion active de taux souverains et de
   changes (MACROSPHERE GLOBAL FUND), en passant par des investissements en
   capital-risque dans des sociétés innovantes (Quota Innovant), une
   sélection d'OPCVM actions zone euro, une gestion obligataire diversifiée
   et optimisée par dérivés (GAY-LUSSAC HERITAGE SELECTION CREDIT), ainsi
   qu'une allocation monétaire et obligataire visant à surperformer un
   indice mixte (FCPE GAY-LUSSAC TRESORERIE). Ces différents véhicules
   intègrent des approches variées — gestion passive, gestion active en
   rendement absolu, critères ESG et pilotage de la sensibilité — afin de
   répondre à des objectifs de performance et de gestion des risques
   adaptés.
   ⏱ étape : 8.0s

  ⏱ TOTAL QUESTION 1 : 130.8s


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  QUESTION 2/3  « Quels frais de gestion et commissions s'appliquent aux fonds ? »
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

┌────────────────────────────────────────────────────────────────────────────┐
│ 1  PLANIFICATION — l'agent décompose la tâche                             │
└────────────────────────────────────────────────────────────────────────────┘
   1. Chercher les informations sur X
   2. Synthétiser les résultats
   3. Écrire le rapport final
   ⏱ étape : 12.9s

┌────────────────────────────────────────────────────────────────────────────┐
│ 2  RÉCUPÉRATION — dense BGE-M3 → parent-child → reranker → génération ancrée│
└────────────────────────────────────────────────────────────────────────────┘
   ● retrieve — dense BGE-M3 → parent-child → reranker (top 6)  ⏱ 24.2s
      1. [score 0.728] Propectus-2.PDF p.16  13 / 17 Ces commissions sont calculées sur la base d’un pourcentage des frais de gestion f…
      2. [score 0.720] FR001400EVS9.pdf p.13  0.30 % maximum Frais indirects maximum Actif net 1,00% Le FCP investira dans des OPC dont …
      3. [score 0.718] 20220125T131406485Z_P-FR0013308202-Z-20220120-FR.pdf p.46  20 000 euros TTC par an. 22. FRAIS DE CONSTITUTION Le Fonds remboursera à la Société de Ge…
      4. [score 0.708] 990000075909.pdf p.12  0 à 20€ selon la place est perçu par le dépositaire. FCPE Commission de surperformance Act…
      5. [score 0.695] FR001400NKV7.pdf p.18  12 heures par le dépositaire. L'échange est effectué sur la base de la prochaine valeur li…
      6. [score 0.633] FR0014002D96.pdf p.16  15 000 euros annuels maximum 3 Frais indirects maximum (commissions et frais de gestion fi…
   ● contexte — 6 passages transmis au générateur  ⏱ 0.0s
   ● generate — rédaction ancrée sur les passages retenus  ⏱ 59.1s
   ● ground_check — vérification anti-hallucination : ✓ ancrée (grounded)  ⏱ 0.0s
   ⏱ total récupération+génération : 83.3s

   Réponse ancrée du RAG :
   Les frais de gestion financière et administrative varient selon les
   fonds et les parts, allant de 0,75 % à 1,55 % TTC maximum [1] [4] [5].
   Les fonds peuvent également supporter des frais de constitution allant
   jusqu'à 0,30 % TTC ou 12 000 euros minimum, ainsi que des frais
   indirects liés aux OPC cibles pouvant atteindre 3,00 % TTC [1] [2] [3]
   [6]. Concernant les commissions, les commissions de souscription sont
   généralement nulles mais peuvent atteindre 2 % maximum pour certains
   fonds, tandis que les commissions de rachat sont le plus souvent
   inexistantes [1] [3] [5] [6]. Les commissions de mouvement sont soit
   nulles, soit prélevées par le dépositaire sous forme de forfait allant
   jusqu'à 144 euros ou d'un taux de 0,05 % TTC maximum [1] [3] [4] [5].
   Enfin, une commission de surperformance de 20 % TTC peut s'appliquer sur
   la surperformance annuelle par rapport à un indice de référence, bien
   qu'elle soit absente pour certains fonds [1] [2] [4] [5] [6].

┌────────────────────────────────────────────────────────────────────────────┐
│ 3  SYNTHÈSE — l'agent rédige la réponse client                            │
└────────────────────────────────────────────────────────────────────────────┘
   Selon les fonds sélectionnés, les frais de gestion et administratifs
   varient de 0,75 % à 1,55 % TTC, auxquels peuvent s'ajouter des frais de
   constitution, des coûts indirects et d'éventuelles commissions de
   souscription ou de mouvement. Par ailleurs, une commission de
   surperformance de 20 % TTC peut s'appliquer en cas de résultats
   supérieurs à l'indice de référence, alors que les frais de rachat sont
   le plus souvent inexistants.
   ⏱ étape : 35.9s

  ⏱ TOTAL QUESTION 2 : 132.1s


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  QUESTION 3/3  « Qui gère les fonds (société de gestion) et par quelle autorité sont-ils agréés ? »
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

┌────────────────────────────────────────────────────────────────────────────┐
│ 1  PLANIFICATION — l'agent décompose la tâche                             │
└────────────────────────────────────────────────────────────────────────────┘
   1. Lister les documents disponibles dans documents/ pour identifier les fonds couverts
   2. Rechercher dans les documents les informations sur les sociétés de gestion qui gèrent les fonds
   3. Rechercher dans les documents les informations sur les autorités ayant agréé les sociétés de gestion
   4. Synthétiser les informations trouvées et écrire le rapport final avec write_file
   ⏱ étape : 35.6s

┌────────────────────────────────────────────────────────────────────────────┐
│ 2  RÉCUPÉRATION — dense BGE-M3 → parent-child → reranker → génération ancrée│
└────────────────────────────────────────────────────────────────────────────┘
   ● retrieve — dense BGE-M3 → parent-child → reranker (top 6)  ⏱ 26.2s
      1. [score 0.728] 20220125T131406485Z_P-FR0013308202-Z-20220120-FR.pdf p.37  333 575, agréée comme société de gestion de portefeuille par l'AMF sous le numéro GP 99-01…
      2. [score 0.727] FR001400AEI4.pdf p.24  TITRE 2 - FONCTIONNEMENT DU FONDS Article 5 - La Société de Gestion La gestion du fonds et…
      3. [score 0.726] FR0013245115.pdf p.20  TITRE 2 - FONCTIONNEMENT DU FONDS Article 5 - La Société de Gestion La gestion du fonds es…
      4. [score 0.726] FR0013306677.pdf p.20  TITRE 2 - FONCTIONNEMENT DU FONDS Article 5 - La Société de Gestion La gestion du fonds es…
      5. [score 0.726] FR0013297074.pdf p.21  TITRE 2 - FONCTIONNEMENT DU FONDS Article 5 - La Société de Gestion La gestion du fonds es…
      6. [score 0.726] FR0013288362.pdf p.24  TITRE 2 - FONCTIONNEMENT DU FONDS Article 5 - La Société de Gestion La gestion du fonds es…
   ● contexte — 6 passages transmis au générateur  ⏱ 0.0s
   ● generate — rédaction ancrée sur les passages retenus  ⏱ 14.7s
   ● ground_check — vérification anti-hallucination : ✓ ancrée (grounded)  ⏱ 0.0s
   ⏱ total récupération+génération : 40.9s

   Réponse ancrée du RAG :
   La société de gestion est la société qui gère les fonds, et elle est
   agréée par l'Autorité des marchés financiers (AMF) sous le numéro GP
   99-015 [1]. Elle est également agréée conformément à la directive
   européenne 2011/61/UE [1].

┌────────────────────────────────────────────────────────────────────────────┐
│ 3  SYNTHÈSE — l'agent rédige la réponse client                            │
└────────────────────────────────────────────────────────────────────────────┘
   Notre société de gestion, responsable de la gestion des fonds, est
   agréée par l'Autorité des marchés financiers (AMF) sous le numéro GP
   99-015. Elle est également agréée en conformité avec la directive
   européenne 2011/61/UE.
   ⏱ étape : 9.6s

  ⏱ TOTAL QUESTION 3 : 86.1s

══════════════════════════════════════════════════════════════════════════════
  Fin de la démo — 3 questions traitées de bout en bout.
  plan → retrieval + reranker → génération ancrée & citée → synthèse client
══════════════════════════════════════════════════════════════════════════════
```
