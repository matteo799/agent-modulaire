# Rapport golden — question_test.yaml

Version : `fonds-tools-v2.0` — 19 question(s) — temps total : 4015s

**Couverture d'outils globale : 14/15 questions** (les outils attendus ont bien été appelés).

**Outils exercés : 10/11** — calculator, list_documents, metric_martin, metric_rdt_max_cvar, metric_rdt_max_drawdown, metric_sharpe, metric_sortino, metric_starr, rag_search, write_file  ·  _manquants :_ read_file

## Synthèse par catégorie

| Catégorie | Q | Couverture outils | Latence moy. | Tokens moy. |
|---|---|---|---|---|
| lookup | 4 | 4/4 | 328.8s | ~11134 |
| comparaison | 2 | 1/2 | 300.6s | ~20638 |
| calcul | 1 | 1/1 | 228.9s | ~24266 |
| metrique-gardefou | 2 | 2/2 | 73.8s | ~9923 |
| metrique-calcul | 2 | 2/2 | 90.0s | ~13362 |
| metrique-selection | 4 | — | 196.7s | ~16360 |
| metrique-budget | 2 | 2/2 | 173.9s | ~19286 |
| hors-corpus | 2 | 2/2 | 203.7s | ~6628 |

> La justesse de la réponse reste à valider à l'œil (le critère « réponse attendue » n'est pas une chaîne exacte). La **couverture d'outils**, la **latence** et les **tokens** sont mesurés automatiquement. Coût en tokens = estimation (count_tokens du client), pour comparer, pas pour facturer.

---

## v2-01-identite  ·  `lookup`

**Question :** Quelles sont les caractéristiques générales du fonds : dénomination, forme juridique et durée de vie ?

**Outils attendus :** ['rag_search']  ·  **appelés :** ['list_documents', 'rag_search', 'write_file']  ·  **couverture :** ✓  ·  **latence :** 266.1s  ·  **tokens :** ~13856

**Réponse attendue (critère) :**

Nom du fonds, forme juridique (FCP, SICAV, SCPI, FIA…), durée d'existence
prévue, telles qu'indiquées dans le document.

**Réponse obtenue :**

# Rapport Final - Caractéristiques Générales du Fonds

## 1. Dénomination
Trois fonds ont été identifiés :
- **FR0012829364** : ACTICCIA VIE 90 N°2
- **FR001400IPY0** : OPT'IN SELECTION PERFORMANCE
- **FR0011759299** : GAY-LUSSAC SMALLCAPS

## 2. Forme Juridique
Tous les fonds sont des **Fonds Commun de Placement (FCP)** soumis au **droit français**.

## 3. Durée de Vie
| Fond | Date de création | Date d’agrément | Durée de vie prévue |
|------|------------------|-----------------|---------------------|
| ACTICCIA VIE 90 N°2 | 3 septembre 2015 | 1er juillet 2015 | 99 ans |
| OPT’IN SELECTION PERFORMANCE | 02/10/2023 | – | 99 ans |

## Synthèse
Les fonds analysés sont des **FCP de droit français** disposant d’une **durée de vie de 99 ans**, ce qui constitue la durée standard pour ce type de véhicule d’investissement collectif en France.

---

## v2-02-frais-courants  ·  `lookup`

**Question :** Quels sont les frais courants annuels du fonds ?

**Outils attendus :** ['rag_search']  ·  **appelés :** ['list_documents', 'rag_search', 'write_file']  ·  **couverture :** ✓  ·  **latence :** 309.4s  ·  **tokens :** ~10336

**Réponse attendue (critère) :**

Un pourcentage de frais courants (ongoing charges) tiré du document ;
« Néant » accepté si le document l'indique. Pas de valeur inventée.

**Réponse obtenue :**

Voici les frais courants annuels du fonds FCPI Amundi Avenir Innovation 4 :

1.  **Frais de gestion financière : 2,30 %**
    *   Il s'agit du taux maximum pouvant être prélevé par le gestionnaire.
    *   Ce taux inclut la commission de rétrocession versée au distributeur, fixée à 0,75 %.
    *   **Assiette de prélèvement :** Sur la collecte nette réalisée entre le 29 décembre 2023 et le 28 février 2025 (diminuée des rachats éventuels), puis sur le montant investi moins les provisions à 100% et/ou les sociétés en procédure collective, et moins les cessions pour les années suivantes.

2.  **Frais récurrents de fonctionnement : 0,5373 %**
    *   Ces frais couvrent la rémunération des différents intervenants ainsi que les autres frais de fonctionnement courant du fonds.

L'ensemble de ces deux éléments constitue les frais récurrents de gestion et de fonctionnement annuels du fonds.

---

## v2-03-sri  ·  `lookup`

**Question :** Quel est l'indicateur synthétique de risque (SRI) du fonds, sur une échelle de 1 à 7 ?

**Outils attendus :** ['rag_search']  ·  **appelés :** ['list_documents', 'rag_search', 'write_file']  ·  **couverture :** ✓  ·  **latence :** 199.3s  ·  **tokens :** ~10112

**Réponse attendue (critère) :**

Le niveau SRI (ou SRRI) sur 7 tel qu'indiqué ; refus si absent du document.

**Réponse obtenue :**

**Réponse à la question initiale :**  
Quel est l'indicateur synthétique de risque (SRI) du fonds FR0010272377, sur une échelle de 1 à 7 ?

**Réponse obtenue :**  
La valeur du SRI du fonds FR0010272377 sur une échelle de 1 à 7 n'a pas été trouvée dans les documents consultés. Ces documents ne contiennent pas cet indicateur spécifique.

**Note :**  
Le SRI (Synthetic Risk Indicator) est généralement fourni dans les documents KIID ou DICI des fonds. Il n'a pas été identifié dans les extraits consultés.

---

## v2-04-sfdr  ·  `lookup`

**Question :** Sous quel article du règlement SFDR le fonds est-il classé (6, 8 ou 9) ?

**Outils attendus :** ['rag_search']  ·  **appelés :** ['rag_search', 'write_file']  ·  **couverture :** ✓  ·  **latence :** 540.7s  ·  **tokens :** ~10234

**Réponse attendue (critère) :**

L'article SFDR (6/8/9) si le document le mentionne ; sinon refus explicite.

**Réponse obtenue :**

**Classification SFDR du fonds**

D'après l'analyse des documents internes, le fonds est classé sous :

**Article 8 du Règlement SFDR (UE) 2019/2088**

Ce classement signifie que le fonds promeut des caractéristiques environnementales ou sociales, sans avoir d'investissement durable comme objectif principal (ce qui serait l'Article 9).

Sources : FR0013443371.pdf et FR0010913632.pdf

---

## v2-05-compare-frais  ·  `comparaison`

**Question :** Compare les frais courants de deux fonds du corpus et donne l'écart entre les deux.

**Outils attendus :** ['list_documents', 'calculator']  ·  **appelés :** ['list_documents', 'rag_search', 'calculator', 'write_file']  ·  **couverture :** ✓  ·  **latence :** 113.7s  ·  **tokens :** ~17926

**Réponse attendue (critère) :**

Identifie deux fonds (via list_documents), donne les frais courants de
CHACUN, puis l'écart calculé via calculator (pas de soustraction « de tête »).

**Réponse obtenue :**

Les documents fournis ne permettent pas de répondre à cette question.

---

## v2-06-compare-sri  ·  `comparaison`

**Question :** Parmi deux fonds du corpus, lequel est le plus risqué selon leur SRI, et de combien de niveaux ?

**Outils attendus :** ['list_documents', 'calculator']  ·  **appelés :** ['list_documents', 'rag_search', 'write_file']  ·  **couverture :** ✗  ·  **latence :** 487.5s  ·  **tokens :** ~23349

**Réponse attendue (critère) :**

Le SRI de deux fonds, la désignation du plus risqué, et l'écart de niveaux
calculé via calculator.

**Réponse obtenue :**

Pour répondre à votre demande de comparer les deux fonds selon leur niveau de SRI, il s'avère que **le corpus documentaire ne contient aucune donnée sur les niveaux SRI des fonds**.

**Résultat :**
- Aucune information n'a été trouvée pour le premier fonds.
- Aucune information n'a été trouvée pour le second fonds.

En conséquence, **la comparaison n'est pas réalisable**.

**Conclusion :**
- **Fonds le plus risqué selon le SRI** : Non déterminé.
- **Différence de niveaux SRI** : Non applicable.

Cette analyse n'a pas pu être menée en raison de l'absence d'informations exploitables dans les documents disponibles.

---

## v2-07-cout-pct  ·  `calcul`

**Question :** Pour un fonds du corpus, quels sont les coûts totaux à 1 an, et combien représentent-ils en pourcentage d'un investissement de 1000 € ?

**Outils attendus :** ['calculator']  ·  **appelés :** ['list_documents', 'rag_search', 'calculator', 'write_file']  ·  **couverture :** ✓  ·  **latence :** 228.9s  ·  **tokens :** ~24266

**Réponse attendue (critère) :**

Les coûts totaux à 1 an tirés du document, puis le pourcentage de 1000 €
calculé via calculator. Refus si le coût n'est pas dans le document.

**Réponse obtenue :**

# Coûts totaux à 1 an de chaque fonds du corpus

## Ré ré

.

.

vestissement de 1 000 €

---

## Fonds 1 : FR0013308202

| Type de frais | Taux |
|---------------|------|
| Frais de gestion | 0,599 % |
| Frais de constitution | 0,0333 % |
| **Coût total à 1 an** | **0,6323 %** |

| **Impact sur 1 000 €** | **6,32 €** |

---

## Fonds 2 : SCPI00004859

| Type de frais | Taux |
|---------------|------|
| Frais de gestion | 0,63 % |
| Frais de transaction | 0,04 % |
| **Coût total à 1 an** | **0,67 %** |
| **Impact sur 1 000 €** | **6,70 €** |

---

## Fonds 3 : FR0013308202 (document non couvert)

Aucune information sur les frais n'a été trouvée dans les documents disponibles pour ce fonds.

---

## Tableau comparatif synthétique

| Fonds | Coût total à 1 an | Impact sur 1 000 € |
|-------|-------------------|---------------------|
| FR0013308202 | 0,6323 % | 6,32 € |
| SCPI00004859 | 0,67 % | 6,70 € |
| Fonds 3 | Non disponible | Non disponible |

---

## Conclusion

Le fonds **FR0013308202** présente un coût total légèrement inférieur (0,6323 %) par rapport au fonds **SCPI00004859** (0,67 %). Sur un investissement de 1 000 €, cette différence représente 0,38 € par an en faveur du premier fonds.

---

## v2-08-sharpe-isin  ·  `metrique-gardefou`

**Question :** Quel est le ratio de Sharpe du fonds FR0010544791 ?

**Outils attendus :** ['metric_sharpe']  ·  **appelés :** ['rag_search', 'metric_sharpe', 'write_file']  ·  **couverture :** ✓  ·  **latence :** 106.9s  ·  **tokens :** ~9934  ·  **métrique :** sharpe

**Réponse attendue (critère) :**

L'outil metric_sharpe explique que le KID ne fournit pas la volatilité σ
(ni une série de rendements) → calcul IMPOSSIBLE, AUCUNE valeur inventée,
caractéristiques de la métrique rappelées.

**Réponse obtenue :**

Les documents fournis ne permettent pas de répondre à cette question.

---

## v2-09-sortino-isin  ·  `metrique-gardefou`

**Question :** Donne-moi le ratio de Sortino du fonds FR0010544791.

**Outils attendus :** ['metric_sortino']  ·  **appelés :** ['rag_search', 'metric_sortino', 'write_file']  ·  **couverture :** ✓  ·  **latence :** 40.6s  ·  **tokens :** ~9912  ·  **métrique :** sortino

**Réponse attendue (critère) :**

metric_sortino indique qu'une série de rendements est requise, absente d'un
KID → pas de calcul, pas de chiffre inventé.

**Réponse obtenue :**

Les documents fournis ne permettent pas de répondre à cette question.

---

## v2-10-sortino-serie  ·  `metrique-calcul`

**Question :** Voici les rendements mensuels d'un fonds : 0.02, -0.03, 0.015, -0.01, 0.025, -0.005, 0.01, -0.02. Calcule son ratio de Sortino avec un taux sans risque de 2 %.

**Outils attendus :** ['metric_sortino']  ·  **appelés :** ['metric_sortino', 'calculator', 'write_file']  ·  **couverture :** ✓  ·  **latence :** 94.0s  ·  **tokens :** ~13466  ·  **métrique :** sortino

**Réponse attendue (critère) :**

metric_sortino est appelé avec la série de rendements et rf=2 % ; un ratio
numérique est renvoyé (calcul réel, pas un garde-fou).

**Réponse obtenue :**

**Analyse du Ratio de Sortino**

**Données de base**
- Rendements mensuels du fonds : 0.02, -0.03, 0.015, -0.01, 0.025, -0.005, 0.01, -0.02
- Taux sans risque (rf) : 2.00%

**Résultats du calcul**
- Ratio de Sortino : 0.6467
- Prime de risque (rendement moyen - rf) : -0.019375

**Interprétation**
Le ratio de Sortino mesure le rendement excédentaire par rapport au taux sans risque, ajusté par la volatilité à la baisse (downside deviation). Contrairement au ratio de Sharpe, il ne pénalise pas la volatilité haussière.

Un ratio de Sortino de 0.6467 indique que le fonds génère 0.6467 unité de rendement excédentaire pour chaque unité de risque à la baisse. Cependant, la prime de risque négative (-0.019375) montre que le rendement moyen du fonds est inférieur au taux sans risque de 2%.

Ce ratio positif mais modéré, combiné à une prime de risque négative, suggère que le fonds a une volatilité à la baisse relativement contenue, mais que son rendement global reste insuffisant pour compenser le taux sans risque. Le profil est défensif (tolérant aux actions) mais le rendement n'est pas attractif.

**Conclusion**
Le fonds présente un profil de risque modéré avec une volatilité à la baisse maîtrisée, mais son rendement ne justifie pas l'investissement par rapport au taux sans risque.

---

## v2-11-sharpe-scalars  ·  `metrique-calcul`

**Question :** Un fonds affiche une performance annualisée de 8 % et une volatilité de 12 %. Quel est son ratio de Sharpe pour un taux sans risque de 2 % ?

**Outils attendus :** ['metric_sharpe']  ·  **appelés :** ['metric_sharpe', 'write_file']  ·  **couverture :** ✓  ·  **latence :** 85.9s  ·  **tokens :** ~13257  ·  **métrique :** sharpe

**Réponse attendue (critère) :**

metric_sharpe calcule (0.08 − 0.02) / 0.12 ≈ 0.5 à partir des entrées
fournies (R, σ, rf).

**Réponse obtenue :**

Le ratio de Sharpe du fonds est de 0.5000, avec un taux sans risque de 2.00%.

---

## v2-12-best-ratio-ambigu  ·  `metrique-selection`

**Question :** Quelle est la meilleure métrique rendement/risque pour évaluer ce fonds ?

**Outils attendus :** —  ·  **appelés :** ['rag_search', 'metric_sharpe', 'write_file']  ·  **couverture :** —  ·  **latence :** 227.4s  ·  **tokens :** ~15405  ·  **métrique :** sharpe

**Réponse attendue (critère) :**

La sélection détecte une AMBIGUÏTÉ (Sharpe vs Sortino) et pose une question
de clarification au lieu de trancher arbitrairement.

**Réponse obtenue :**

# Rapport d'évaluation : Métrique rendement/risque

## 1. Informations sur le fonds
- **ISIN** : FR0010883017 (Part A)
- **Objectif de gestion** : Réalisation d'une performance annualisée nette de frais supérieure à 50% Ester + 50% Bloomberg indice Euro Corporate Bonds 1-5 ans.
- **Profil** : Exposition principale et diversifiée aux instruments de taux et de crédit, avec possibilité d'intervenir sur les marchés actions pour ajuster le risque global.

## 2. Résultats et interprétation du Ratio de Sharpe
Le calcul numérique du Ratio de Sharpe n'a pas pu être effectué car le rendement annualisé (R) et la volatilité (σ) ne figurent pas dans les documents internes disponibles.

Cependant, l'interprétation de cette métrique pour ce fonds est la suivante :
- **Formule** : (R − rf) / σ
- **Famille** : Ratio défensif ++ (refuge monétaire / obligataire).
- **Mesure de risque** : Volatilité totale (hausses ET baisses).
- **Pénalisation de la hausse** : Oui, le ratio pénalise la volatilité haussière autant que la baissière.
- **Pertinence pour ce fonds** : Le fonds ayant un profil très défensif (monétaire et obligations d'entreprises investment grade 1-5 ans), le Ratio de Sharpe est la métrique standard et universelle pour ce type d'actif. Il est particulièrement adapté pour comparer des portefeuilles obligataires où la distribution des rendements est supposée quasi-normale. 
- **Limites** : Il suppose des rendements quasi-normaux, est aveugle aux queues épaisses, et sa tendance au refuge monétaire/obligataire en régime de taux élevés peut masquer la valeur ajoutée d'une gestion active du crédit ou des ajustements actions.

## 3. Conclusion
Le Ratio de Sharpe est la métrique rendement/risque standard la plus adaptée pour une évaluation universelle de ce fonds à dominante taux/crédit. Si l'analyse nécessitait de ne pas pénaliser la volatilité haussière (liée aux ajustements actions) ou de se concentrer sur les pertes extrêmes, il faudrait se tourner vers le Ratio de Sortino ou le STARR, sous réserve de disposer de l'historique des rendements.

---

## v2-13-downside-intent  ·  `metrique-selection`

**Question :** Je veux une métrique qui ne pénalise pas la hausse : je crains surtout les baisses. Laquelle ?

**Outils attendus :** —  ·  **appelés :** ['metric_sortino', 'write_file']  ·  **couverture :** —  ·  **latence :** 143.9s  ·  **tokens :** ~11751  ·  **métrique :** sortino

**Réponse attendue (critère) :**

La sélection retient Sortino SANS demander de clarification, en justifiant
par le risque de baisse.

**Réponse obtenue :**

# Ratio de Sortino : La métrique recommandée

---

## Votre préoccupation

Vous souhaitez une métrique de performance qui **ne pénalise pas la hausse**, car votre principale crainte porte sur les baisses de valeur.

---

## Notre recommandation : Le Ratio de Sortino

### Formule
$$\text{Ratio de Sortino} = \frac{R - r_f}{\sigma_{\text{baisse}}}$$

### Caractéristiques essentielles
- **Famille** : Ratio défensif, plus tolérant aux actions que le Sharpe
- **Mesure de risque** : Risque de baisse uniquement (sous le seuil MAR = taux sans risque $r_f$)
- **Pénalise la hausse** : **NON**

---

## Avantages pour votre profil

| Avantage | Explication |
|----------|-------------|
| **Ne pénalise pas la volatilité haussière** | Contrairement au Sharpe, le Sortino ignore les fluctuations positives, ce qui correspond exactement à votre demande. |
| **Tolère plus d'actions à risque égal** | Permet d'investir dans des actifs plus offensifs sans pénaliser les performances haussières. |
| **Concentré sur le risque de perte** | Mesure uniquement la volatilité à la baisse, qui est votre souci principal. |

---

## Quand l'utiliser ?

- Le client se soucie surtout de la **volatilité à la baisse**
- Stratégies asymétriques (momentum, convexité positive)
- On ne veut **PAS pénaliser la hausse**

---

## Inconvénients à noter

- Reste un ratio → structurellement défensif
- $\sigma_{\text{baisse}}$ estimé sur moins de points → plus bruité
- Dépend du seuil de référence ($r_f$)

---

## Conclusion

Le **Ratio de Sortino** est la métrique recommandée pour votre profil car il répond parfaitement à votre besoin : **mesurer le rendement ajusté au risque de baisse sans pénaliser les performances haussières**. Cette approche est particulièrement adaptée aux profils qui craignent les baisses mais veulent profiter des hausses.

---

## v2-14-tail-risk  ·  `metrique-selection`

**Question :** Je veux surtout me protéger contre les pertes extrêmes / les queues de distribution. Quelle métrique ?

**Outils attendus :** —  ·  **appelés :** ['rag_search', 'metric_starr', 'write_file']  ·  **couverture :** —  ·  **latence :** 240.5s  ·  **tokens :** ~11936  ·  **métrique :** starr

**Réponse attendue (critère) :**

La sélection oriente vers STARR (rendement / CVaR), métrique de risque de queue.

**Réponse obtenue :**

# Métrique recommandée : STARR (Stable Tail Adjusted Risk-Return Ratio)

---

## Contexte

Vous exprimez une préoccupation prioritaire concernant la protection contre les pertes extrêmes et les risques liés aux queues de distribution (risques de queue gauche).

---

## Recommandation

La métrique **STARR** est la mesure la plus appropriée pour répondre à ce besoin spécifique.

---

## Pourquoi le STARR ?

**Objectif :** Le STARR mesure le rendement excédentaire rapporté au risque de perte extrême (CVaR à 5%). Il est conçu pour pénaliser spécifiquement les actifs présentant des queues de distribution lourdes.

**Adequation :** C'est la métrique recommandée lorsque vous vous souciez des **pertes extrêmes** et souhaitez éviter les actifs à queue gauche épaisse.

**Caractéristiques :**

| Élément | Détail |
|---|---|
| **Formule** | (R − r_f) / CVaR_5% |
| **Ne pénalise pas la hausse** | Contrairement au Sharpe |
| **Mesure de risque cohérente** | Sous-additive, focalisée sur les pertes sévères |
| **Tendance défensive** | Orienté vers la fuite du risque extrême |

---

## Avantages pour vous

- ✅ **Alignement direct** avec votre objectif de protection contre les événements extrêmes.
- ✅ **Comparaison fiable** des profils de risque de queue entre différents fonds.

---

## Points de vigilance

- ⚠️ L'estimation de la CVaR nécessite une **série de rendements historiques suffisamment longue** pour être stable. Sur des historiques courts, la mesure peut être instable.
- ⚠️ En tant que ratio, il conserve une **tendance défensive globale**.

---

## Conclusion

> Le STARR est la **métrique de référence** pour évaluer et sélectionner des fonds en optimisant la protection contre les pertes extrêmes, en phase directe avec votre demande.

---

## v2-15-regularite  ·  `metrique-selection`

**Question :** Je cherche un fonds régulier, qui minimise le temps passé sous l'eau (drawdowns). Quelle métrique ?

**Outils attendus :** —  ·  **appelés :** ['list_documents', 'rag_search', 'metric_martin', 'write_file']  ·  **couverture :** —  ·  **latence :** 175.2s  ·  **tokens :** ~26347  ·  **métrique :** martin

**Réponse attendue (critère) :**

La sélection oriente vers Martin (rendement / Ulcer), métrique de régularité
des drawdowns.

**Réponse obtenue :**

Les documents fournis ne permettent pas de répondre à cette question.

---

## v2-16-budget-cvar  ·  `metrique-budget`

**Question :** Explique l'objectif « rendement maximal sous budget de CVaR » et dans quel cas l'utiliser.

**Outils attendus :** ['metric_rdt_max_cvar']  ·  **appelés :** ['metric_rdt_max_cvar', 'rag_search', 'write_file']  ·  **couverture :** ✓  ·  **latence :** 120.3s  ·  **tokens :** ~15985  ·  **métrique :** rdt_max_cvar

**Réponse attendue (critère) :**

Explication de l'objectif (maximiser R sous CVaR ≤ budget fixé), tendance
offensive ; mention que le calcul réel nécessite un univers multi-fonds +
rendements (non disponible).

**Réponse obtenue :**

# Objectif « Rendement maximal sous budget de CVaR »

## Définition

Cet objectif consiste à **maximiser le rendement attendu** d'un portefeuille tout en respectant une **contrainte de perte extrême** (CVaR à 5 %) fixée par l'utilisateur.

> **Formule :** max R sous contrainte CVaR_5% ≤ budget

---

## Caractéristiques

| Critère | Description |
|---|---|
| **Famille** | Budget (offensif — tilt actions jusqu'à saturer le budget) |
| **Mesure de risque** | Budget de perte de queue **fixé** par l'utilisateur |
| **Pénalise la hausse ?** | Non |
| **Données requises** | Un univers multi-fonds + une matrice de rendements |
| **Tendance** | Offensif (exploite pleinement les actions) |

---

## Avantages

- **Pilotable** : on fixe le risque de queue, l'optimiseur cherche le rendement.
- **Ne punit pas la hausse** : exploite pleinement les actions.
- **Budget interprétable directement** en perte extrême.

---

## Inconvénients

- Le résultat dépend du budget choisi (à justifier).
- CVaR historique → sensible à l'échantillon de queue.

---

## Cas d'utilisation

Cet objectif est à utiliser lorsque :

- Le client souhaite **maximiser le rendement** sous un **plafond de perte extrême** qu'il fixe lui-même (ex. CVaR ≤ 8 %).
- On recherche une **allocation offensive maîtrisée**.
- Le client raisonne en termes de **perte extrême maximale acceptable**.

---

## Exemple concret

Dans le document FR001400NKV7.pdf (*MacroSphere Global Fund*), on trouve un exemple de gestion active avec une contrainte de risque similaire : une « Value-at-Risk » (VaR) ex ante maximum de 20 % à un horizon de 20 jours et avec un intervalle de confiance de 99 %. Cela illustre l'approche de gestion active sous contrainte de risque, bien que ce soit une VaR et non une CVaR.

---

## Conclusion

L'objectif « Rendement maximal sous budget de CVaR » est un outil d'optimisation de portefeuille qui permet de maximiser le rendement tout en maîtrisant le risque de perte extrême. Il est particulièrement adapté aux investisseurs qui souhaitent une allocation offensive tout en fixant un plafond de perte extrême acceptable.

---

## v2-17-budget-drawdown  ·  `metrique-budget`

**Question :** À quoi sert l'objectif « rendement maximal sous budget de drawdown » et quelles sont ses limites ?

**Outils attendus :** ['metric_rdt_max_drawdown']  ·  **appelés :** ['rag_search', 'metric_rdt_max_drawdown', 'write_file']  ·  **couverture :** ✓  ·  **latence :** 227.5s  ·  **tokens :** ~22587  ·  **métrique :** rdt_max_drawdown

**Réponse attendue (critère) :**

Explication (maximiser R sous |MaxDD| ≤ budget), contrainte parlante pour
un client, limites (non convexe, estimateur fragile) ; calcul réel non
disponible.

**Réponse obtenue :**

# Rendement maximal sous budget de drawdown

## Définition

L'objectif « rendement maximal sous budget de drawdown » cherche à **maximiser le rendement d'un portefeuille tout en respectant une contrainte sur le drawdown maximal** :

> **max R sous contrainte |MaxDD| ≤ budget**

Le budget de drawdown correspond au niveau de perte maximum que l'utilisateur accepte (par exemple : « je ne veux pas perdre plus de 15 % »).

---

## Caractéristiques

| Propriété | Valeur |
|---|---|
| **Famille** | Budget (offensif ++) |
| **Tendance** | Dominé par les actions |
| **Mesure de risque** | Budget de drawdown maximal **fixé** |
| **Pénalise la hausse** | Non |
| **Données requises** | Univers multi-fonds + matrice de rendements |

---

## Cas d'utilisation

Cet objectif est pertinent dans les situations suivantes :

- Le client raisonne en termes de **perte maximale acceptable** (« je ne veux pas perdre plus de X % »)
- Le drawdown est la **contrainte la plus parlante** pour un client
- On cherche une **allocation offensive** tout en restant sous un seuil de perte déterminé

---

## Avantages

- **Contrainte la plus parlante pour un client** : le drawdown est un concept facilement compréhensible par un investisseur
- **N'inhibe pas la hausse** : permet une allocation offensive tout en la maintenant maîtrisée

---

## Limites

1. **Non convexe** : la solution dépend du point de départ de l'optimisation, ce qui peut mener à des résultats différents selon l'initialisation
2. **Estimateur fragile** : le max drawdown historique ne correspond qu'à **un seul épisode**, ce qui en fait un estimateur peu robuste
3. **Nécessite des données spécifiques** : un univers multi-fonds et une matrice de rendements sont requis pour le calcul

---

## Conclusion

Cet objectif est adapté aux clients souhaitant une **allocation offensive tout en maîtrisant leur perte maximale**. Cependant, sa **fragilité statistique** (basée sur un seul épisode historique) et sa **non-convexité** nécessitent une utilisation prudente.

---

## v2-18-hors-corpus-geo  ·  `hors-corpus`

**Question :** Quelle est la capitale de l'Australie ?

**Outils attendus :** ['rag_search']  ·  **appelés :** ['rag_search', 'write_file']  ·  **couverture :** ✓  ·  **latence :** 65.6s  ·  **tokens :** ~6602

**Réponse attendue (critère) :**

Refus : les documents fournis ne permettent pas de répondre. AUCUNE réponse
depuis les connaissances générales du modèle.

**Réponse obtenue :**

## Réponse

Après consultation des documents internes, aucune information n'est disponible concernant la capitale de l'Australie.

En effet, les documents consultés sont exclusivement d'ordre financier (fiches SCPI, documents de fonds) et ne couvrent pas ce sujet de géographie.

**Conclusion : l'information demandée n'est pas disponible dans les documents à disposition.**

---

## v2-19-hors-corpus-meteo  ·  `hors-corpus`

**Question :** Quel temps fera-t-il demain à Paris ?

**Outils attendus :** ['rag_search']  ·  **appelés :** ['rag_search', 'write_file']  ·  **couverture :** ✓  ·  **latence :** 341.8s  ·  **tokens :** ~6655

**Réponse attendue (critère) :**

Refus explicite (hors corpus), pas de réponse inventée.

**Réponse obtenue :**

Je suis désolé, mais je ne suis pas en mesure de répondre à votre question sur la météo à Paris pour demain. Les documents internes disponibles ne contiennent aucune information météorologique. La question "Quel temps fera-t-il demain à Paris ?" ne peut être répondue avec les outils à disposition, qui sont limités à la recherche dans les documents financiers du dossier documents/.

---
