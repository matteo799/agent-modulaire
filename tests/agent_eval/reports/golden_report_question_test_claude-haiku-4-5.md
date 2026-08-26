# Rapport golden — question_test.yaml

Version : `fonds-tools-v2.0` — 19 question(s) — temps total : 8643s

**Couverture d'outils globale : 12/15 questions** (les outils attendus ont bien été appelés).

**Outils exercés : 10/11** — calculator, list_documents, metric_martin, metric_rdt_max_cvar, metric_rdt_max_drawdown, metric_sharpe, metric_sortino, metric_starr, rag_search, write_file  ·  _manquants :_ read_file

## Synthèse par catégorie

| Catégorie | Q | Couverture outils | Latence moy. | Tokens moy. |
|---|---|---|---|---|
| lookup | 4 | 4/4 | 265.1s | ~10830 |
| comparaison | 2 | 0/2 | 497.9s | ~26230 |
| calcul | 1 | 0/1 | 343.0s | ~37727 |
| metrique-gardefou | 2 | 2/2 | 93.4s | ~9478 |
| metrique-calcul | 2 | 2/2 | 65.9s | ~8748 |
| metrique-selection | 4 | — | 169.4s | ~16733 |
| metrique-budget | 2 | 2/2 | 2116.5s | ~12410 |
| hors-corpus | 2 | 2/2 | 507.3s | ~6592 |

> La justesse de la réponse reste à valider à l'œil (le critère « réponse attendue » n'est pas une chaîne exacte). La **couverture d'outils**, la **latence** et les **tokens** sont mesurés automatiquement. Coût en tokens = estimation (count_tokens du client), pour comparer, pas pour facturer.

---

## v2-01-identite  ·  `lookup`

**Question :** Quelles sont les caractéristiques générales du fonds : dénomination, forme juridique et durée de vie ?

**Outils attendus :** ['rag_search']  ·  **appelés :** ['list_documents', 'rag_search']  ·  **couverture :** ✓  ·  **latence :** 185.9s  ·  **tokens :** ~18490

**Réponse attendue (critère) :**

Nom du fonds, forme juridique (FCP, SICAV, SCPI, FIA…), durée d'existence
prévue, telles qu'indiquées dans le document.

**Réponse obtenue :**

# Caractéristiques générales du fonds identifié

D'après les résultats de l'analyse des documents disponibles, voici les caractéristiques générales du fonds pour lequel les informations ont été trouvées :

---

## Fonds : **FCPR AMUNDI MEGATENDANCES PME ETI**

| Caractéristique | Détail |
|---|---|
| **Dénomination** | FCPR AMUNDI MEGATENDANCES PME ETI |
| **Forme juridique** | Copropriété d'instruments financiers et de dépôts (sans personnalité morale). La Société de Gestion représente le Fonds à l'égard des tiers conformément à l'article L. 214-24-35 du CMF. |
| **Durée de vie** | **Huit (8) ans** à compter de la Date de Constitution, avec possibilité de prorogation d'une (1) période d'un (1) an par la Société de gestion (sous réserve de notification aux porteurs au moins 3 mois avant l'échéance et de communication à l'AMF et au Dépositaire). |

---

## Remarque importante

Les autres documents présents dans le dossier n'ont pas permis d'extraire des informations complètes sur la dénomination, la forme juridique et la durée de vie. Cela peut s'expliquer par :

- L'absence de ces informations dans les extraits consultés
- La nature des documents (par exemple, des fiches de données, des rapports financiers, etc.) qui ne contiennent pas nécessairement ces éléments réglementaires

Si vous souhaitez analyser un fonds spécifique parmi les nombreux documents listés, merci de préciser le nom ou le code ISIN du fonds concerné afin que je puisse cibler la recherche.

---

## v2-02-frais-courants  ·  `lookup`

**Question :** Quels sont les frais courants annuels du fonds ?

**Outils attendus :** ['rag_search']  ·  **appelés :** ['rag_search', 'write_file']  ·  **couverture :** ✓  ·  **latence :** 210.4s  ·  **tokens :** ~7107

**Réponse attendue (critère) :**

Un pourcentage de frais courants (ongoing charges) tiré du document ;
« Néant » accepté si le document l'indique. Pas de valeur inventée.

**Réponse obtenue :**

# Frais courants annuels du fonds

**FCPI Amundi Avenir Innovation 4**

---

| Type de frais | Taux |
|---|---|
| **Frais courants annuels (frais de gestion financière)** | **2,3%** |
| **Frais récurrents de fonctionnement** | **0,5373%** |

---

**Précisions :**

- Le taux de frais courants annuels de **2,3%** constitue la rémunération maximale de la Société de gestion.
- Si un distributeur se voit verser des frais récurrents, ceux-ci sont compris dans ce taux.

---

*Source : Document FCPI Amundi Avenir Innovation 4 FINAL - 20 septembre 2024*

---

## v2-03-sri  ·  `lookup`

**Question :** Quel est l'indicateur synthétique de risque (SRI) du fonds, sur une échelle de 1 à 7 ?

**Outils attendus :** ['rag_search']  ·  **appelés :** ['rag_search', 'write_file']  ·  **couverture :** ✓  ·  **latence :** 300.2s  ·  **tokens :** ~7685

**Réponse attendue (critère) :**

Le niveau SRI (ou SRRI) sur 7 tel qu'indiqué ; refus si absent du document.

**Réponse obtenue :**

# Indicateur Synthétique de Risque (SRI) du Fonds

**Valeur du SRI : Non disponible**

## Note

La recherche dans les documents du fonds (FR0010272377) n'a pas permis de retrouver la valeur numérique de l'indicateur synthétique de risque sur l'échelle de 1 à 7. Le document principal disponible décrit la stratégie de gestion, les caractéristiques du produit (allocation flexible, éligibilité PEA, exposition actions jusqu'à 100%, etc.) mais ne mentionne pas explicitement le score SRI.

Il est possible que :
- Le SRI soit communiqué dans un document non disponible dans la base documentaire
- Le SRI soit à déterminer selon la méthodologie de l'organisme régulateur (AMF) à partir des données de volatilité et de perte potentielle

## Rappel de l'échelle SRI
| Niveau | Profil | Volatilité indicative |
|--------|--------|----------------------|
| 1 | Très défensif | < 2% |
| 2 | Défensif | 2-5% |
| 3 | Modéré défensif | 5-8% |
| 4 | Modéré | 8-10% |
| 5 | Modéré offensif | 10-13% |
| 6 | Offensif | 13-16% |
| 7 | Très offensif | > 16% |

**Attention :** La valeur SRI ci-dessus n'est pas confirmée par les documents internes.

---

## v2-04-sfdr  ·  `lookup`

**Question :** Sous quel article du règlement SFDR le fonds est-il classé (6, 8 ou 9) ?

**Outils attendus :** ['rag_search']  ·  **appelés :** ['list_documents', 'rag_search', 'write_file']  ·  **couverture :** ✓  ·  **latence :** 363.7s  ·  **tokens :** ~10038

**Réponse attendue (critère) :**

L'article SFDR (6/8/9) si le document le mentionne ; sinon refus explicite.

**Réponse obtenue :**

**Réponse finale :**

D'après l'analyse des documents, les fonds suivants sont classés **Article 8** au sens du Règlement SFDR, car ils promeuvent des caractéristiques environnementales ou sociales :

*   Le fonds référencé **FR0013443371** est classé Article 8.
*   Le fonds référencé **FR0010913632** est classé Article 8.

En conclusion, les deux fonds analysés dans les documents disponibles sont sous le régime de l'**Article 8** du SFDR.

---

## v2-05-compare-frais  ·  `comparaison`

**Question :** Compare les frais courants de deux fonds du corpus et donne l'écart entre les deux.

**Outils attendus :** ['list_documents', 'calculator']  ·  **appelés :** ['list_documents', 'rag_search', 'write_file']  ·  **couverture :** ✗  ·  **latence :** 132.7s  ·  **tokens :** ~15841

**Réponse attendue (critère) :**

Identifie deux fonds (via list_documents), donne les frais courants de
CHACUN, puis l'écart calculé via calculator (pas de soustraction « de tête »).

**Réponse obtenue :**

# Comparaison des frais courants de deux fonds

---

## Fonds 1 — FR0013308202
*Document daté du 20 janvier 2022*

| Type de frais | Taux |
|---|---|
| Frais de gestion financière (rémunération du gestionnaire) | 2,000 % |
| Frais de gestion financière (part du distributeur, incluse) | 0,600 % |

---

## Fonds 2

**Aucune donnée disponible** sur les frais courants dans les documents fournis.

---

## Écart entre les deux fonds

**Impossible à calculer** faute de données pour le deuxième fonds.

---

## Conclusion

La recherche de frais courants pour le deuxième fonds n'a retourné aucun résultat pertinent. **Une vérification manuelle des documents ou une recherche ciblée supplémentaire est nécessaire** pour compléter ce rapport.

---

## v2-06-compare-sri  ·  `comparaison`

**Question :** Parmi deux fonds du corpus, lequel est le plus risqué selon leur SRI, et de combien de niveaux ?

**Outils attendus :** ['list_documents', 'calculator']  ·  **appelés :** ['list_documents', 'rag_search', 'write_file']  ·  **couverture :** ✗  ·  **latence :** 863.2s  ·  **tokens :** ~36620

**Réponse attendue (critère) :**

Le SRI de deux fonds, la désignation du plus risqué, et l'écart de niveaux
calculé via calculator.

**Réponse obtenue :**

Voici la réponse struct :

.

.

**Analy.

**Analyse comparative des risques (SRI)**

*   **Fonds 1 :** FCPI Amundi Avenir Innovation 4
    *   **Niveau SRI :** Non disponible
*   **Fonds-2 :** FR0010232108
    *   **Niveau SRI :** Non disponible

**Conclusion :**

*   **Fonds le plus risqué :** Non déterminé
*   **Écart de niveaux :** Non calculé

---

## v2-07-cout-pct  ·  `calcul`

**Question :** Pour un fonds du corpus, quels sont les coûts totaux à 1 an, et combien représentent-ils en pourcentage d'un investissement de 1000 € ?

**Outils attendus :** ['calculator']  ·  **appelés :** ['list_documents', 'rag_search', 'write_file']  ·  **couverture :** ✗  ·  **latence :** 343.0s  ·  **tokens :** ~37727

**Réponse attendue (critère) :**

Les coûts totaux à 1 an tirés du document, puis le pourcentage de 1000 €
calculé via calculator. Refus si le coût n'est pas dans le document.

**Réponse obtenue :**

**RÉPONSE FINALE : ANALYSE DES COÛTS DES FONDS DU CORPUS**

Pour répondre à votre question sur les coûts totaux à 1 an et leur pourcentage pour un investissement de 1000 €, voici les résultats de l'analyse du corpus :

1.  **Pour le fonds identifié sous l'ISIN FR0013308202** : Aucune information pertinente n'a été trouvée dans les documents concernant les coûts totaux à 1 an.

2.  **Pour le fonds identifié sous l'ISIN SCPI00004859** : Seuls les coûts d'entrée ont été identifiés, représentant 8% du montant investi (déjà inclus dans le prix). Les autres composantes des coûts (frais de gestion, frais sur performance, frais de sortie) et le total des coûts à 1 an n'ont pas été trouvées dans les documents.

**CONCLUSION** :
Les documents disponibles dans le corpus ne fournissent pas les informations complètes sur les coûts totaux à 1 an pour les fonds analysés. Par conséquent, **il n'est pas possible de calculer et de présenter le pourcentage de ces coûts par rapport à un investissement de 1000 €**.

Le rapport ne peut donc pas être complété avec les données chiffrées demandées.

---

## v2-08-sharpe-isin  ·  `metrique-gardefou`

**Question :** Quel est le ratio de Sharpe du fonds FR0010544791 ?

**Outils attendus :** ['metric_sharpe']  ·  **appelés :** ['rag_search', 'metric_sharpe', 'write_file']  ·  **couverture :** ✓  ·  **latence :** 112.0s  ·  **tokens :** ~11082  ·  **métrique :** sharpe

**Réponse attendue (critère) :**

L'outil metric_sharpe explique que le KID ne fournit pas la volatilité σ
(ni une série de rendements) → calcul IMPOSSIBLE, AUCUNE valeur inventée,
caractéristiques de la métrique rappelées.

**Réponse obtenue :**

# Ratio de Sharpe — Fonds FR0010544791

**Calcul du Ratio de Sharpe impossible** pour le fonds FR0010544791.

Le calcul requiert le rendement annualisé du fonds (R) et la volatilité (σ), qui ne sont pas disponibles dans la documentation du fonds (KID/DICI). Aucune valeur chiffrée n'a pu être extraite des documents internes.

Le ratio de Sharpe est une métrique standard de rendement/risque qui utilise la volatilité totale (hausses et baisses) et pénalise les rendements à la hausse.

Aucune valeur n'a été inventée. Le ratio de Sharpe ne peut pas être calculé pour ce fonds avec les informations disponibles.

---

## v2-09-sortino-isin  ·  `metrique-gardefou`

**Question :** Donne-moi le ratio de Sortino du fonds FR0010544791.

**Outils attendus :** ['metric_sortino']  ·  **appelés :** ['metric_sortino', 'write_file']  ·  **couverture :** ✓  ·  **latence :** 74.7s  ·  **tokens :** ~7875  ·  **métrique :** sortino

**Réponse attendue (critère) :**

metric_sortino indique qu'une série de rendements est requise, absente d'un
KID → pas de calcul, pas de chiffre inventé.

**Réponse obtenue :**

**Réponse finale concernant le ratio de Sortino du fonds FR0010544791 :**

Le calcul du ratio de Sortino pour le fonds FR0010544791 est **impossible** avec les informations actuellement disponibles.

**Raison** : Cette métrique nécessite une série historique de rendements (historique de la valeur liquidative) pour calculer la déviation à la baisse. Les documents internes consultés (KID/DICI) ne contiennent pas cette série de rendements, ni les données agrégées nécessaires pour le calcul.

**Note** : Aucune valeur n'a été inventée pour produire cette réponse.

---

## v2-10-sortino-serie  ·  `metrique-calcul`

**Question :** Voici les rendements mensuels d'un fonds : 0.02, -0.03, 0.015, -0.01, 0.025, -0.005, 0.01, -0.02. Calcule son ratio de Sortino avec un taux sans risque de 2 %.

**Outils attendus :** ['metric_sortino']  ·  **appelés :** ['calculator', 'metric_sortino', 'write_file']  ·  **couverture :** ✓  ·  **latence :** 63.3s  ·  **tokens :** ~10060  ·  **métrique :** sortino

**Réponse attendue (critère) :**

metric_sortino est appelé avec la série de rendements et rf=2 % ; un ratio
numérique est renvoyé (calcul réel, pas un garde-fou).

**Réponse obtenue :**

## Rapport Final – Ratio de Sortino

---

### Données d'entrée

| Élément | Valeur |
|---|---|
| **Rendements mensuels du fonds** | 0.02, -0.03, 0.015, -0.01, 0.025, -0.005, 0.01, -0.02 |
| **Taux sans risque annuel** | 2 % |
| **Taux sans risque mensuel** | 0.17 % |
| **Nombre de rendements** | 8 |

---

### Résultat

Le **ratio de Sortino** du fonds est de **0,7353**, calculé sur la base de 8 rendements mensuels et d'un taux sans risque mensuel de 0,17 %.

---

## v2-11-sharpe-scalars  ·  `metrique-calcul`

**Question :** Un fonds affiche une performance annualisée de 8 % et une volatilité de 12 %. Quel est son ratio de Sharpe pour un taux sans risque de 2 % ?

**Outils attendus :** ['metric_sharpe']  ·  **appelés :** ['metric_sharpe', 'write_file']  ·  **couverture :** ✓  ·  **latence :** 68.6s  ·  **tokens :** ~7435  ·  **métrique :** sharpe

**Réponse attendue (critère) :**

metric_sharpe calcule (0.08 − 0.02) / 0.12 ≈ 0.5 à partir des entrées
fournies (R, σ, rf).

**Réponse obtenue :**

### Calcul du ratio de Sharpe

**Données du fonds :**
*   Performance annualisée : 8,00 %
*   Volatilité : 12,00 %
*   Taux sans risque : 2,00 %

**Formule du ratio de Sharpe :**
(Performance annualisée - Taux sans risque) / Volatilité

**Application numérique :**
(8 - 2) / 12 = 0,5000

**Résultat :**
Le ratio de Sharpe du fonds est de 0,5000.

---

## v2-12-best-ratio-ambigu  ·  `metrique-selection`

**Question :** Quelle est la meilleure métrique rendement/risque pour évaluer ce fonds ?

**Outils attendus :** —  ·  **appelés :** ['list_documents', 'rag_search', 'metric_sharpe', 'write_file']  ·  **couverture :** —  ·  **latence :** 189.2s  ·  **tokens :** ~15328  ·  **métrique :** sharpe

**Réponse attendue (critère) :**

La sélection détecte une AMBIGUÏTÉ (Sharpe vs Sortino) et pose une question
de clarification au lieu de trancher arbitrairement.

**Réponse obtenue :**

# Réponse finale : Évaluation rendement/risque du fonds FR0013280211

## Fonds analysé
- **ISIN :** FR0013280211
- **Objectif :** Performance annualisée nette supérieure à 5%, dominante actions, Union Européenne et OCDE.

---

## Métrique recommandée : Ratio de Sharpe

**Résultat du calcul : IMPOSSIBLE**
Le calcul du Ratio de Sharpe n'a pas pu être effectué pour ce fonds, car les données requises (rendement annualisé R et volatilité σ) ne sont pas disponibles dans son KID/DICI.

---

## Présentation du Ratio de Sharpe

### Formule
**Sharpe = (R − rf) / σ**
Où :
- **R** = rendement annualisé du fonds
- **rf** = taux sans risque
- **σ** = volatilité (écart-type) des rendements

### Ce que mesure le Sharpe
Le Ratio de Sharpe est la métrique rendement/risque la plus standardisée. Il mesure le **rendement excédentaire par unité de risque total** (volatilité).

### Caractéristiques clés
| Critère | Valeur |
|---|---|
| **Type** | Ratio défensif ++ (refuge monétaire/obligataire) |
| **Pénalise la hausse** | OUI |
| **Risque mesuré** | Volatilité totale (hausses ET baisses) |
| **Comparabilité** | Universelle (standard mondial) |

### Avantages
- Standard universel, immédiatement compris par tous les investisseurs
- Vérifiable directement : (R − rf) / σ
- Optimum global convexe (portefeuille tangent)

### Inconvénients
- Pénalise la volatilité haussière autant que la baissière
- Suppose des rendements quasi-normaux
- Aveugle aux queues épaisses (risques extrêmes)
- Tendance au refuge monétaire/obligataire en régime de taux élevés

---

## Recommandation complémentaire
Pour évaluer ce fonds d'orientation/actions, il serait pertinent de compléter par :
- **Ratio de Sortino** (ne pénalise pas la hausse)
- **STARR** (protège contre les pertes extrêmes)
- **Ratio de Martin** (mesure la régularité / drawdown)

Ces métriques offrent une vision plus complète du profil rendement/risque pour un fonds actions.

---

## v2-13-downside-intent  ·  `metrique-selection`

**Question :** Je veux une métrique qui ne pénalise pas la hausse : je crains surtout les baisses. Laquelle ?

**Outils attendus :** —  ·  **appelés :** ['rag_search', 'metric_sortino', 'write_file']  ·  **couverture :** —  ·  **latence :** 169.8s  ·  **tokens :** ~11377  ·  **métrique :** sortino

**Réponse attendue (critère) :**

La sélection retient Sortino SANS demander de clarification, en justifiant
par le risque de baisse.

**Réponse obtenue :**

**Métrique recommandée : Le ratio de Sortino**

Ce ratio est spécialement adapté à votre besoin car il ne pénalise pas la volatilité à la hausse. Il se concentre uniquement sur le risque de baisse.

**Caractéristiques techniques :**
*   **Formule :** (R − rf) / σ_baisse
*   **Principe :** Son dénominateur (σ_baisse) ne retient que la volatilité des rendements situés sous le seuil MAR (Minimum Acceptable Return), généralement fixé au taux sans risque (rf). La volatilité haussière n'est donc pas incluse.

**Avantages pour votre situation :**
*   **Ne pénalise pas la hausse :** Contrairement au ratio de Sharpe, il ignore la dispersion des rendements positifs.
*   **Idéal pour les stratégies asymétriques :** Il est parfaitement adapté aux approches (comme le momentum ou la convexité positive) où l'on souhaite préserver le potentiel de gains tout en maîtrisant le risque de perte.
*   **Biais défensif :** Pour un même niveau de risque de baisse, le ratio de Sortino est plus tolérant envers les actifs actions qu'un ratio de Sharpe.

**En résumé :** Le ratio de Sortino est conçu pour les investisseurs qui se préoccupent principalement des pertes, sans vouloir réduire leur potentiel de gains par une mesure de risque globale.

---

## v2-14-tail-risk  ·  `metrique-selection`

**Question :** Je veux surtout me protéger contre les pertes extrêmes / les queues de distribution. Quelle métrique ?

**Outils attendus :** —  ·  **appelés :** ['list_documents', 'rag_search', 'metric_starr', 'write_file']  ·  **couverture :** —  ·  **latence :** 145.6s  ·  **tokens :** ~21794  ·  **métrique :** starr

**Réponse attendue (critère) :**

La sélection oriente vers STARR (rendement / CVaR), métrique de risque de queue.

**Réponse obtenue :**

# Réponse Finale - Analyse STARR des Fonds

## Objectif
Vous souhaitez vous protéger contre les pertes extrêmes / les queues de distribution. La métrique retenue est le **STARR (Rendement / CVaR)** = (R − rf) / CVaR_5%.

## Fonds Analysés

| # | ISIN | Document |
|---|------|----------|
| 1 | FR0013308202 | 20220125T131406485Z_P-FR0013308202-Z-20220120-FR.pdf |
| 2 | SCPI00004859 | 20231031T151651945Z_P-SCPI00004859-Z-20231001-FR.pdf |
| 3 | SCPI00004009 | 20240304T144709802Z_P-SCPI00004009-Z-20240304-FR.pdf |
| + | 66 autres fonds | Voir liste complète dans documents/ |

## Résultats du Calcul STARR

### Fond FR0013308202 (FCPR AMUNDI MEGATENDANCES PME ETI)
- **Statut** : Calcul impossible
- **Raison** : Les données disponibles (KID/DICI) ne contiennent pas de série de rendements historiques. Le calcul du STARR requiert R (rendement) et CVaR_5% (Value at Risk conditionnelle à 5%), extraits d'une historique de valeurs liquidatives.

### Fonds 2 et 3 (SCPI)
- **Statut** : Aucune donnée pertinente trouvée dans les documents
- **Raison** : Les documents ne couvrent pas les informations nécessaires au calcul.

## Conclusion
**Aucun calcul de STARR n'a pu être réalisé** pour l'ensemble des fonds disponibles. Cette limitation est structurelle : les documents réglementaires (KID/DICI) fournis ne contiennent pas de série de rendements historiques ni de mesures de risque de queue (CVaR).

### Recommandation
Pour calculer le STARR et comparer les fonds sur leur exposition aux pertes extrêmes, il est nécessaire d'accéder à :
- Un historique de valeurs liquidatives (VL) sur au moins 3-5 ans
- Des données permettant d'estimer la CVaR_5%

La métrique STARR reste pertinente pour l'objectif de protection contre les queues de distribution, mais ne peut être appliquée qu'avec des données de marché complémentaires.

---

## v2-15-regularite  ·  `metrique-selection`

**Question :** Je cherche un fonds régulier, qui minimise le temps passé sous l'eau (drawdowns). Quelle métrique ?

**Outils attendus :** —  ·  **appelés :** ['list_documents', 'metric_martin', 'rag_search', 'write_file']  ·  **couverture :** —  ·  **latence :** 172.9s  ·  **tokens :** ~18434  ·  **métrique :** martin

**Réponse attendue (critère) :**

La sélection oriente vers Martin (rendement / Ulcer), métrique de régularité
des drawdowns.

**Réponse obtenue :**

**Réponse finale pour l'utilisateur**

Pour rechercher un fonds régulier minimisant le temps passé en drawdown, la métrique appropriée est le **Ratio de Martin** (Rendement / Ulcer Index). Cette mesure est idéale car elle évalue la douleur des drawdowns (leur profondeur et leur durée), pénalise uniquement les baisses et favorise la régularité des performances.

Sur la base de cette méthodologie, l'analyse des deux fonds suivants a été tentée :
- FR0013308202
- SCPI00004859

Cependant, **aucun ratio de Martin n'a pu être calculé**. Les documents disponibles (KID/DICI) ne fournissent pas les séries historiques de rendements (historique des VL) nécessaires au calcul de l'Ulcer Index, qui est la base de cette métrique.

**Recommandation :** Pour mener cette analyse à terme et comparer efficacement les fonds sur ce critère de régularité, il est nécessaire d'obtenir les historiques de valorisation (VL) de chaque fonds sur une période suffisante. L'approche méthodologique est pertinente pour votre besoin, mais l'accès à des données de marché ou de reporting performance détaillées est indispensable pour l'appliquer.

---

## v2-16-budget-cvar  ·  `metrique-budget`

**Question :** Explique l'objectif « rendement maximal sous budget de CVaR » et dans quel cas l'utiliser.

**Outils attendus :** ['metric_rdt_max_cvar']  ·  **appelés :** ['metric_rdt_max_cvar', 'write_file']  ·  **couverture :** ✓  ·  **latence :** 3635.7s  ·  **tokens :** ~9171  ·  **métrique :** rdt_max_cvar

**Réponse attendue (critère) :**

Explication de l'objectif (maximiser R sous CVaR ≤ budget fixé), tendance
offensive ; mention que le calcul réel nécessite un univers multi-fonds +
rendements (non disponible).

**Réponse obtenue :**

### Rendement maximal sous budget de CVaR

**Définition et Objectif**
Cet objectif vise à **maximiser le rendement attendu** d'un portefeuille multi-fonds, sous une contrainte définie par l'utilisateur : le **CVaR à 5% (la perte extrême moyenne) ne doit pas dépasser un budget fixé**.
Formule : `Max R` sous contrainte `CVaR_5% ≤ budget`.

**Caractéristiques**
*   **Famille** : Budget (approche offensive, avec un tilt actions jusqu'à la saturation du budget de risque).
*   **Mesure de risque** : Le budget de perte de queue est **fixé directement par l'utilisateur**.
*   **Pénalise la hausse** : Non, cet objectif ne pénalise pas la surperformance.
*   **Données requises** : Nécessite un univers multi-fonds et une matrice de rendements historiques.
*   *Note* : Le calcul réel de cet objectif n'est pas disponible dans le repository actuel, car il nécessite ces données d'entrée spécifiques.

**Quand l'utiliser (Cas d'usage)**
À utiliser lorsque le client souhaite **maximiser le rendement tout en imposant un plafond strict à la perte extrême**. L'allocation résultante sera **offensive mais maîtrisée**.
*Exemple concret* : Un client qui raisonne en termes de seuil de perte extrême accepté et fixe une contrainte du type `CVaR ≤ 8 %`.

**Avantages**
*   **Pilotable** : Le risque de queue est directement contrôlé via le budget, tandis que l'optimiseur se concentre sur le rendement.
*   **Performant** : Ne punissant pas la hausse, il exploite pleinement le potentiel des actions.
*   **Interprétable** : Le budget est exprimé directement en termes de perte extrême, ce qui est parlant pour le client.

**Inconvénients**
*   **Dépendance au budget** : Le résultat est sensible au niveau du budget choisi, ce qui doit être justifié.
*   **Sensibilité aux données** : Le CVaR historique est dépendant de l'échantillon de rendements passé, notamment de la queue de distribution.

---

## v2-17-budget-drawdown  ·  `metrique-budget`

**Question :** À quoi sert l'objectif « rendement maximal sous budget de drawdown » et quelles sont ses limites ?

**Outils attendus :** ['metric_rdt_max_drawdown']  ·  **appelés :** ['rag_search', 'metric_rdt_max_drawdown', 'write_file']  ·  **couverture :** ✓  ·  **latence :** 597.3s  ·  **tokens :** ~15650  ·  **métrique :** rdt_max_drawdown

**Réponse attendue (critère) :**

Explication (maximiser R sous |MaxDD| ≤ budget), contrainte parlante pour
un client, limites (non convexe, estimateur fragile) ; calcul réel non
disponible.

**Réponse obtenue :**

# Réponse finale : Objectif « Rendement Maximal sous Budget de Drawdown »

## 1. Définition
Cet objectif vise à **maximiser le rendement** d'un portefeuille tout en respectant une **contrainte stricte sur le drawdown maximal**. Mathématiquement, il s'écrit : **max R sous contrainte |MaxDD| ≤ budget**.

## 2. Caractéristiques
- Il appartient à la **famille des objectifs de type « Budget »**.
- Il génère une tendance **offensive ++**, principalement dominée par des allocations en actions.
- La mesure de risque est un **budget de drawdown maximal FIXÉ à l'avance par l'utilisateur**.
- Il **ne pénalise pas la hausse** des marchés.
- Sa mise en œuvre nécessite un **univers multi-fonds et une matrice de rendements** pour l'optimisation.

## 3. Cas d'utilisation
Cet objectif est pertinent lorsque :
- Le client formule sa contrainte en termes de « **je ne veux pas perdre plus de X %** ».
- Il s'agit de la **contrainte la plus parlante pour un client non technique**.
- L'objectif est d'obtenir une **allocation offensive tout en maîtrisant un seuil de perte maximal**.

## 4. Avantages
- **Contrainte intuitive** : le drawdown est la mesure de risque la plus facile à comprendre pour un investisseur.
- **N'inhibe pas la hausse** : l'approche est offensive et permet de capturer pleinement le potentiel de hausse du marché.
- **Allocation maîtrisée** : offre un contrôle direct et précis sur la perte maximale supportable.

## 5. Limites et inconvénients
- **Non convexe** : la solution optimale dépend du point de départ de l'algorithme d'optimisation, ce qui peut poser des problèmes de stabilité.
- **Estimateur fragile** : le drawdown maximal historique est un épisode isolé et peut ne pas être représentatif des pertes futures.
- **Calcule réel non disponible** : nécessite des données spécifiques (univers multi-fonds et matrice de rendements) pour être concrètement implémenté.

## Conclusion
L'objectif de rendement maximal sous budget de drawdown est particulièrement adapté aux clients cherchant à **maximiser leur rendement tout en contrôlant strictement leur perte maximale**. C'est l'objectif le plus intuitif pour les investisseurs non techniques. Cependant, sa **non-convexité et la fragilité de l'estimateur du drawdown historique** constituent des limites importantes à prendre en compte lors de la construction du portefeuille.

---

## v2-18-hors-corpus-geo  ·  `hors-corpus`

**Question :** Quelle est la capitale de l'Australie ?

**Outils attendus :** ['rag_search']  ·  **appelés :** ['rag_search', 'write_file']  ·  **couverture :** ✓  ·  **latence :** 568.0s  ·  **tokens :** ~6419

**Réponse attendue (critère) :**

Refus : les documents fournis ne permettent pas de répondre. AUCUNE réponse
depuis les connaissances générales du modèle.

**Réponse obtenue :**

La capitale de l'Australie n'a pas été trouvée dans les documents internes.

---

## v2-19-hors-corpus-meteo  ·  `hors-corpus`

**Question :** Quel temps fera-t-il demain à Paris ?

**Outils attendus :** ['rag_search']  ·  **appelés :** ['rag_search', 'write_file']  ·  **couverture :** ✓  ·  **latence :** 446.5s  ·  **tokens :** ~6764

**Réponse attendue (critère) :**

Refus explicite (hors corpus), pas de réponse inventée.

**Réponse obtenue :**

Je ne peux pas vous fournir de prévisions météorologiques pour demain à Paris.

Les outils dont je dispose sont dédiés à la gestion documentaire et aux analyses financières, et non à l'accès à des informations météorologiques en temps réel.

---
