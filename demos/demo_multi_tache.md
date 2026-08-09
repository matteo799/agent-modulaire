# Démo Agent modulaire — 5 tâches multi-étapes (dataset finance)

L'**agent** traite chaque tâche de bout en bout : **planification → boucle d'outils (`rag_search`, `calculator`, `write_file`…) → rapport final**. C'est ce qu'un RAG seul ne peut pas faire (enchaîner recherches + calcul + livrable).

---

## Tâche 1

> Compare les frais de gestion de trois fonds du corpus, calcule l'écart en points de pourcentage entre le plus cher et le moins cher, et écris un rapport qui recommande le moins coûteux.

**Plan généré par l'agent :**

1. Lister les documents disponibles pour identifier les trois fonds du corpus avec l'outil list_documents.
2. Rechercher les frais de gestion du premier fonds identifié en utilisant rag_search avec le paramètre source correspondant à ce fonds.
3. Rechercher les frais de gestion du deuxième fonds identifié en utilisant rag_search avec le paramètre source correspondant à ce fonds.
4. Rechercher les frais de gestion du troisième fonds identifié en utilisant rag_search avec le paramètre source correspondant à ce fonds.
5. Calculer l'écart en points de pourcentage entre les frais du fonds le plus cher et ceux du fonds le moins cher avec l'outil calculator.
6. Rédiger et sauvegarder le rapport final recommandant le fonds le moins coûteux et mentionnant l'écart calculé avec l'outil write_file.

**Exécution — outils enchaînés :**

1. `list_documents`
2. `rag_search` (recherche documentaire)
3. `rag_search` (recherche documentaire)
4. `rag_search` (recherche documentaire)
5. `calculator` → **2.0**
6. `write_file`

**Rapport final :**

# Rapport de Recommandation sur les Frais de Gestion des Fonds

## Résumé de l'analyse

L'analyse des frais de gestion des fonds du corpus a été réalisée afin d'identifier les écarts de coûts entre les différents produits.

## Principaux résultats

| Élément | Détail |
|---------|--------|
| Écart constaté | 2,0 points de pourcentage |
| Comparaison | Entre le fonds le plus cher et le fonds le moins cher |
| Fonds identifié comme le moins coûteux | **SCPI00004859** |

## Recommandation

**Nous recommandons le fonds SCPI00004859**, étant le moins coûteux, afin d'optimiser les coûts de gestion au sein du corpus.

<sub>⏱ 213s · 6 étapes · outils : calculator, list_documents, rag_search, write_file</sub>

---

## Tâche 2

> Pour le FCPI Amundi Avenir Innovation, trouve les frais de gestion annuels et la durée de blocage recommandée, puis calcule le coût total approximatif des frais sur toute cette durée.

**Plan généré par l'agent :**

1. Rechercher les frais de gestion annuels du FCPI Amundi Avenir Innovation dans les documents internes
2. Rechercher la durée de blocage recommandée du FCPI Amundi Avenir Innovation dans les documents internes
3. Calculer le coût total approximatif des frais sur toute la durée de blocage (frais annuels × nombre d'années) à l'aide de calculator
4. Écrire le rapport final récapitulant les frais de gestion, la durée de blocage et le coût total calculé

**Exécution — outils enchaînés :**

1. `rag_search` (recherche documentaire)
2. `rag_search` (recherche documentaire)
3. `rag_search` (recherche documentaire)
4. `write_file`

**Rapport final :**

Voici la réponse structurée et claire reprenant intégralement les informations du livrable :

# Réponse concernant le FCPI Amundi Avenir Innovation

Après analyse des documents internes disponibles, voici les informations obtenues :

| Paramètre | Détail |
| :--- | :--- |
| **Frais de gestion annuels** | Non trouvés dans les documents disponibles. |
| **Durée de blocage recommandée** | **8 ans minimum** (jusqu'au 31 décembre 2031), pouvant aller jusqu'à 10 ans en cas de prorogation. |
| **Coût total approximatif des frais** | **Impossible à calculer** dans les conditions actuelles. |

**Conclusion :** Le calcul du coût total des frais sur la durée de détention n'est pas réalisable car le taux des frais de gestion annuels n'est pas renseigné dans les sources consultées. La seule information certaine est celle relative à la durée de blocage.

*Date de la réponse : généré à partir des documents internes disponibles*

<sub>⏱ 321s · 4 étapes · outils : rag_search, write_file</sub>

---

## Tâche 3

> Pour un FCPI, une SCPI et un FCPE du corpus, extrais la société de gestion, les frais de gestion, la durée de blocage ou de placement recommandée et l'éventuel avantage fiscal, et produis un tableau comparatif.

**Plan généré par l'agent :**

1. Lister les documents disponibles pour identifier un FCPI, une SCPI et un FCPE dans le corpus.
2. Rechercher les informations du premier fonds identifié (FCPI) concernant la société de gestion, les frais, la durée de blocage et l'avantage fiscal via rag_search en ciblant ce fonds avec le paramètre source.
3. Rechercher les informations du deuxième fonds identifié (SCPI) concernant la société de gestion, les frais, la durée de placement recommandée et l'avantage fiscal via rag_search en ciblant ce fonds avec le paramètre source.
4. Rechercher les informations du troisième fonds identifié (FCPE) concernant la société de gestion, les frais, la durée de blocage et l'avantage fiscal via rag_search en ciblant ce fonds avec le paramètre source.
5. Écrire le tableau comparatif final synthétisant les données extraites pour les trois fonds dans un fichier via write_file.

**Exécution — outils enchaînés :**

1. `list_documents`
2. `rag_search` (recherche documentaire)
3. `rag_search` (recherche documentaire)
4. `rag_search` (recherche documentaire)
5. `write_file`

**Rapport final :**

# Tableau comparatif de trois types de fonds

| Critère | FCPI | SCPI | FCPE |
| :--- | :--- | :--- | :--- |
| **Fonds analysé** | Document FR0013308202 | Document SCPI00004859 | Document FR0013308202 |
| **Société de gestion** | Non disponible dans les documents | Non disponible dans les documents | Non disponible dans les documents |
| **Frais de gestion** | Non disponible dans les documents | Non disponible dans les documents | Non disponible dans les documents |
| **Durée de blocage / placement recommandé** | Non disponible dans les documents | Non disponible dans les documents | 8 ans (durée de vie du fonds) |
| **Avantage fiscal** | Non disponible dans les documents | Non disponible dans les documents | Non disponible dans les documents |

## Observations

* **FCPI** : La recherche n'a retourné aucun passage pertinent concernant la société de gestion, les frais, la durée de blocage ou l'avantage fiscal.
* **SCPI** : La recherche n'a retourné aucun passage pertinent concernant les critères demandés.
* **FCPE** : Seule la durée de vie du fonds a été trouvée dans le règlement : **8 ans** à compter de la date de constitution, avec possibilité de prorogation d'un an par la société …

<sub>⏱ 280s · 5 étapes · outils : list_documents, rag_search, write_file</sub>

---

## Tâche 4

> Si j'investis 10 000 euros dans un FCPI éligible dont les frais de gestion sont ceux du prospectus, calcule le montant des frais la première année et estime la réduction d'impôt sur le revenu correspondante.

**Plan généré par l'agent :**

1. Search for information on X
2. Synthesize the results
3. Write the final report

**Exécution — outils enchaînés :**

1. `rag_search` (recherche documentaire)
2. `write_file`
3. `write_file`

**Rapport final :**

# Réponse à votre demande

Vous avez demandé de calculer les frais de gestion pour la première année et d'estimer la réduction d'impôt sur le revenu correspondante, dans le cadre d'un investissement de 10 000 € dans un FCPI éligible.

Après analyse des documents disponibles, notamment du prospectus du FCPI Amundi Avenir Innovation 4, nous ne sommes pas en mesure de fournir ces calculs. En effet :

1.  **Frais de gestion :** Le taux ou le montant des frais de gestion pour la première année n'est pas précisé dans les extraits du prospectus consultés.
2.  **Réduction d'impôt :** Le taux exact de la réduction d'impôt sur le revenu n'est pas mentionné dans le prospectus. Ce document indique explicitement que les avantages fiscaux sont détaillés dans une "Note Fiscale" séparée, qui n'a pas été fournie dans notre base documentaire.

Par conséquent, les informations chiffrées nécessaires pour réaliser les calculs demandés sont absentes des documents que nous avons à disposition.

Pour obtenir ces données, il vous sera nécessaire de consulter la **Note Fiscale** spécifique au FCPI et de vérifier le barème des frais indiqué dans les documents contractuels complets de l'offre.

<sub>⏱ 170s · 3 étapes · outils : rag_search, write_file</sub>

---

## Tâche 5

> Identifie quels fonds du corpus offrent un avantage fiscal à l'impôt sur le revenu et lesquels imposent un blocage des parts supérieur à 5 ans, et liste-les avec leurs conditions dans un rapport.

**Plan généré par l'agent :**

1. Lister les fonds disponibles dans le corpus à l'aide de l'outil list_documents.
2. Rechercher les informations sur les avantages fiscaux et la durée de blocage des parts pour le premier fonds identifié en utilisant rag_search avec le paramètre source.
3. Rechercher les informations sur les avantages fiscaux et la durée de blocage des parts pour le deuxième fonds identifié en utilisant rag_search avec le paramètre source.
4. Rechercher les informations sur les avantages fiscaux et la durée de blocage des parts pour le troisième fonds identifié en utilisant rag_search avec le paramètre source.
5. Écrire le rapport final synthétisant les fonds offrant un avantage fiscal à l'impôt sur le revenu et ceux avec un blocage supérieur à 5 ans en utilisant write_file.

**Exécution — outils enchaînés :**

1. `list_documents`
2. `rag_search` (recherche documentaire)
3. `rag_search` (recherche documentaire)
4. `rag_search` (recherche documentaire)
5. `write_file`

**Rapport final :**

**Rapport de synthèse : Avantages fiscaux et durée de blocage des fonds**

1. **Fonds offrant un avantage fiscal à l'impôt sur le revenu :**
   Sur la base des extraits analysés, aucun avantage fiscal à l'impôt sur le revenu n'est explicitement mentionné.

2. **Fonds imposant un blocage des parts supérieur à 5 ans :**
   *   **Fonds FR0013308202** (Document : 20220125T131406485Z_P-FR0013308202-Z-20220120-FR.pdf) :
        *   La durée de vie du fonds est fixée à 8 ans à compter de sa constitution (prorogeable d'1 an).
        *   Cette durée implique un blocage des parts supérieur à 5 ans.

**Note :** Les recherches ciblées sur les deuxième et troisième fonds de la liste (SCPI00004859 et SCPI00004009) n'ont pas retourné de passages pertinents concernant ces critères spécifiques.

<sub>⏱ 191s · 5 étapes · outils : list_documents, rag_search, write_file</sub>

---

