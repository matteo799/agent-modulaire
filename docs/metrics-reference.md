# Gold Portfolio — Métriques d'optimisation

*Note de référence — définitions, formules, avantages / inconvénients et comportement typique des objectifs proposés par l'optimiseur.*

---

## Cadre commun

Tous les objectifs partagent le même moteur :

- **Long-only**, poids ∈ [0, plafond], Σ poids = 100 %, ≤ 5 fonds par catégorie et ≤ 15 lignes.
- **Covariance** estimée par rétrécissement **Ledoit-Wolf** (matrice toujours bien conditionnée, définie positive).
- **Rendements en excès** du taux sans risque `rf` (le même `rf` constant est appliqué sur toute la fenêtre — voir la mise en garde plus bas).
- Sélection combinatoire des fonds (énumération ou Monte-Carlo) × optimisation des poids pour l'objectif choisi.

On distingue **deux familles** d'objectifs, dont les comportements sont radicalement différents :

| Famille | Principe | Tendance d'allocation |
|---|---|---|
| **Ratios rendement / risque** (Sharpe, Sortino, STARR, Martin) | Maximiser `excès de rendement ÷ mesure de risque` | **Défensive** : se réfugie dans le peu volatil (monétaire / obligataire), délaisse les actions |
| **Rendement max sous budget** (CVaR, drawdown) | Maximiser le rendement **sous un plafond de risque que vous fixez** | **Offensive** : tilt actions jusqu'à saturer le budget de risque |

> **Pourquoi cette dichotomie ?** Un ratio divise par une mesure de risque *positivement homogène* : il récompense mécaniquement le **rendement par unité de risque**, donc favorise les actifs peu risqués (la « volatilité haussière » est traitée comme du risque au même titre que la baisse). À l'inverse, un objectif « rendement max sous budget » ne pénalise **pas** la volatilité haussière : il cherche le rendement le plus élevé tant que le risque de perte reste sous le plafond → il prend de l'action tant qu'il « a droit » au risque.

Notations : `R` = rendement annualisé (arithmétique), `rf` = taux sans risque, `excès = R − rf`, `σ` = volatilité annualisée, `α` = 5 %.

---

## Famille 1 — Ratios rendement / risque

### 1. Ratio de Sharpe

- **Définition** : `Sharpe = (R − rf) / σ`, où `σ` est la volatilité annualisée (écart-type des rendements, hausses **et** baisses).
- **Mesure** : rendement excédentaire par unité de **volatilité totale**.
- **Avantages** :
  - Standard universel, immédiatement compris par tout gérant.
  - **Vérifiable** directement depuis les chiffres affichés : `(R − rf) / σ` redonne exactement le Sharpe.
  - Solution analytique (portefeuille tangent long-only), optimum global convexe.
- **Inconvénients** :
  - Pénalise la **volatilité haussière** autant que la baissière : un fonds qui monte fort et régulièrement est « puni ».
  - Suppose implicitement des rendements quasi-normaux ; aveugle aux queues épaisses et aux drawdowns.
  - **Tendance au refuge** : en régime de taux élevés, privilégie fortement le **monétaire / obligataire** et délaisse les actions (meilleur rendement/volatilité du cash).
- **Comportement typique** : portefeuille **défensif**, dominé par le peu volatil.

### 2. Ratio de Sortino

- **Définition** : `Sortino = (R − rf) / σ_baisse`, où `σ_baisse` ne compte que les rendements **inférieurs** au seuil minimal acceptable (ici `rf`).
- **Mesure** : rendement excédentaire par unité de **risque de baisse** uniquement.
- **Avantages** :
  - Ne pénalise **pas** la volatilité haussière → plus juste pour les stratégies asymétriques (momentum, convexité positive).
  - Tolère donc **plus d'actions** que le Sharpe à risque égal.
- **Inconvénients** :
  - Toujours un ratio → reste structurellement défensif (refuge possible dans le peu volatil).
  - `σ_baisse` estimé sur moins de points (seulement les baisses) → **plus bruité**, sensible à la fenêtre.
  - Dépend du seuil de référence choisi (ici `rf`).
- **Comportement typique** : défensif, mais **un peu plus tolérant aux actions** que le Sharpe.

### 3. STARR — Rendement / CVaR

- **Définition** : `STARR = (R − rf) / CVaR_α`, où `CVaR_α` (Expected Shortfall à 5 %) est la **perte moyenne dans les 5 % de pires journées**, annualisée.
- **Mesure** : rendement excédentaire par unité de **risque de queue** (sévérité des pertes extrêmes).
- **Avantages** :
  - Mesure de risque **cohérente** (sous-additive) et focalisée sur ce qui fait mal : les pertes extrêmes.
  - Beaucoup plus pertinent que la volatilité pour des distributions à queue épaisse.
- **Inconvénients** :
  - `CVaR` estimé empiriquement sur peu d'observations de queue → **instable** sur historique court.
  - Reste un ratio → tendance défensive ; évite les actifs à queue gauche épaisse (souvent les actions).
- **Comportement typique** : fuit les actifs à **risque extrême**, favorise obligataire / monétaire à queue fine.

### 4. Martin — Rendement / Ulcer

- **Définition** : `Martin = (R − rf) / Ulcer`, où l'**Ulcer Index** = racine de la moyenne des drawdowns au carré (mesure **profondeur × durée** des pertes sous le dernier plus-haut).
- **Mesure** : rendement excédentaire par unité de **douleur de drawdown** (pénalise les baisses profondes ET longues).
- **Avantages** :
  - Capture l'expérience réellement vécue par l'investisseur (le « temps passé sous l'eau »).
  - Idéal pour comparer des profils de **régularité** ; favorise les courbes qui montent sans à-coups.
- **Inconvénients** :
  - Métrique **path-dependent** (dépend de l'ordre des rendements) → très sensible à la fenêtre.
  - Reste un ratio → défensif ; pénalise lourdement les actions à drawdowns profonds.
- **Comportement typique** : privilégie les actifs **réguliers et peu sujets aux drawdowns** (obligataire de qualité, monétaire).

---

## Famille 2 — Rendement maximal sous budget de risque

> Ces deux objectifs **inversent la logique** : au lieu de minimiser le risque par unité de rendement, ils **maximisent le rendement** tant que le risque de perte reste sous un **plafond explicite que vous choisissez**. La volatilité haussière n'est jamais pénalisée.

### 5. Rendement max sous budget de CVaR

- **Définition** : maximiser `R` **sous contrainte** `CVaR_α ≤ budget` (budget annualisé que vous fixez, ex. 8 %).
- **Mesure** : le meilleur rendement atteignable sans que la perte de queue dépasse votre tolérance.
- **Formulation** : programme **linéaire convexe** (Rockafellar-Uryasev) → optimum global, contrainte respectée exactement.
- **Avantages** :
  - **Pilotable** : vous fixez le risque de queue acceptable, l'optimiseur va chercher le rendement.
  - Ne punit pas la performance haussière → exploite pleinement les actions.
  - Le budget a une **interprétation directe** en perte extrême.
- **Inconvénients** :
  - Le résultat dépend du budget choisi (paramètre à justifier).
  - `CVaR` historique → sensible à l'échantillon de queue.
- **Comportement typique** : portefeuille **tilté actions**, poussé jusqu'à saturer le budget de CVaR.

### 6. Rendement max sous budget de drawdown

- **Définition** : maximiser `R` **sous contrainte** `|drawdown maximal| ≤ budget` (ex. 20 %).
- **Mesure** : le meilleur rendement atteignable sans jamais dépasser la perte maximale que vous acceptez.
- **Formulation** : contrainte **non convexe** (max drawdown path-dependent) → résolue par SLSQP avec pénalisation ; optimum local de bonne qualité, non certifié global.
- **Avantages** :
  - Contrainte la **plus parlante** pour un client (« je ne veux pas perdre plus de X % »).
  - N'inhibe pas la hausse → allocation **offensive** maîtrisée.
- **Inconvénients** :
  - Non convexe → solution dépendante du point de départ, pas de garantie d'optimum global.
  - Le drawdown maximal historique est **un seul chiffre** (un seul épisode) → estimateur fragile.
- **Comportement typique** : **dominé par les actions**, calibré pour rester sous le seuil de perte choisi.

---

## Tableau de synthèse

| Objectif | Formule | Pénalise la hausse ? | Optimum | Tendance d'allocation |
|---|---|---|---|---|
| **Sharpe** | (R−rf) / σ | Oui (toute vol.) | Global (convexe) | Défensive ++ (monétaire/oblig.) |
| **Sortino** | (R−rf) / σ_baisse | Non | Local (SLSQP) | Défensive + |
| **STARR** | (R−rf) / CVaR | Non (mais évite la queue gauche) | Local (SLSQP) | Défensive (fuit le risque extrême) |
| **Martin** | (R−rf) / Ulcer | Non (mais évite les drawdowns) | Local (SLSQP) | Défensive (régularité) |
| **Rdt max / budget CVaR** | max R, CVaR ≤ budget | Non | Global (LP convexe) | Offensive (tilt actions) |
| **Rdt max / budget drawdown** | max R, \|MaxDD\| ≤ budget | Non | Local (non convexe) | Offensive ++ (actions) |

---

## Mises en garde transversales (à connaître pour la présentation)

1. **Effet « refuge » des ratios.** Toute mesure de risque positivement homogène fait tendre le ratio vers +∞ pour un actif quasi sans risque. C'est pourquoi les 4 ratios privilégient le monétaire/obligataire : c'est mathématiquement attendu, pas un défaut. La famille « rendement max sous budget » est la **seule façon d'obtenir plus de rendement** — au prix d'un risque de baisse explicitement accepté.

2. **Taux sans risque constant.** `rf` est appliqué de façon **constante** sur toute la fenêtre. Sur un historique long incluant les années de taux bas (2017-2021), le monétaire affiche un excès de rendement **négatif** vs un `rf` actuel élevé → les ratios le délaissent et basculent vers les actions. Un **taux variable dans le temps** corrigerait ce biais (prévu en V2). À fenêtre de régime de taux homogène, le comportement redevient stable.

3. **In-sample vs out-of-sample.** Toutes ces métriques sont optimisées **dans l'échantillon** : elles surestiment la performance future. Le backtest walk-forward (ré-optimisation sur in-sample, test sur out-of-sample) donne la lecture honnête.

4. **Rendement arithmétique vs CAGR.** Les ratios utilisent le rendement **arithmétique** annualisé (convention standard). Le **CAGR** (géométrique, qui colle à la courbe composée) est affiché séparément ; il peut être au-dessus ou en dessous de l'arithmétique selon l'équilibre rendement/volatilité.

---

*Pour la dérivation mathématique complète (formulation des programmes d'optimisation, conditions d'optimalité, robustesse bootstrap), voir la note de recherche `note_recherche_gold_portfolio.pdf`.*
