# Comparatif — RAG rapide vs RAG avec CRAG (30 questions finance)

Même corpus, même modèle de génération (Claude). Seule différence : le mode **Rapide** (récupération → reranker → génération) vs **CRAG** (en plus : juge chaque passage, réécrit la requête si insuffisant `↻`, re-vérifie l'ancrage).

| | Répondues | Pièges hors-corpus (Q28-30) |
|---|:---:|:---:|
| **Rapide** | 19/30 | 3/3 refusés |
| **CRAG** (max 1 ↻) | 19/30 | 3/3 refusés |

**Différences : 8 questions** (Q2, Q4, Q6, Q9, Q11, Q13, Q17, Q25). ≠ marque une divergence ci-dessous.

*Légende : ✓ répondu & cité · ✗ sans réponse · `↻` réécriture corrective.*

---

### 1. Quelle est la politique de distribution des revenus du produit SCPI ?
- **Rapide** ✓ — La distribution des éventuels revenus du produit est soumise à l'approbation de l'assemblée générale annuelle [1].
- **CRAG** ✓ — La société de gestion décide de la répartition des revenus du produit [2][3][4][5]. Pendant au moins 5 ans après la clôture de la période de souscription, les revenus sont en principe capitalisés et non distribués, afin de bénéficier de l'exonération d'IR [2]. Passé ce délai, la société de gestion peut opter pour trois formules : la capitalisation pure, la distribution pure, ou la liberté de capitaliser ou distribuer chaque année [3][4][5].

### 2. Quels indicateurs de performance passée sont présentés dans le DIC SCPI ? ≠
- **Rapide** ✗ — Les passages fournis ne permettent pas de répondre précisément à la question. Les documents mentionnent que les performances passées du Produit (qui semble être une SCPI Amundi) peuvent être téléchargées sur le site www.amundi-immobilier.com/nos-solutions-depargne [1][2], mais aucun indicateur de performance passée spécifique n'est présenté dans les passages transmis. Les données du DIC sont indiquées comme étant basées sur des prévisions ou sur l'approbation des comptes au 31/12/2022, sans afficher de rendements historiques [1][2].
- **CRAG** ✓ — Les documents fournis ne précisent pas quels indicateurs de performance passée spécifiques (rendement, TRI, valeur liquidative, etc.) sont présentés dans le DIC SCPI.

### 3. Combien de temps est-il recommandé de conserver une part de SCPI, et peut-on retirer ses fonds de façon anticipée ?
- **Rapide** ✗ — Les documents fournis ne permettent pas de répondre.
- **CRAG** ✗ ↻ — Je ne sais pas répondre à cette question à partir des documents disponibles. Si tu peux préciser ta question ou fournir un contexte supplémentaire, je peux retenter.

### 4. Quelles sont les obligations des associés d'une SCPI en matière de dettes ? ≠
- **Rapide** ✗ — Les documents fournis ne permettent pas de répondre.
- **CRAG** ✓ ↻ — Les documents fournis mentionnent différents types d'obligations (titres de créances) dans lesquels le Fonds peut investir [4] :

### 5. Comment est composé le patrimoine d'une SCPI et quels actifs détient-elle ?
- **Rapide** ✗ — Les documents fournis ne permettent pas de répondre. Les passages disponibles traitent uniquement des actifs de FCP (Fonds Commun de Placement) [1][2][3][5][6] et d'une SICAV [4], qui sont des véhicules d'investissement différents d'une SCPI (Société Civile de Placement Immobilier). Aucune information sur la composition du patrimoine d'une SCPI n'est présente dans ces documents.
- **CRAG** ✗ ↻ — Je ne sais pas répondre à cette question à partir des documents disponibles. Si tu peux préciser ta question ou fournir un contexte supplémentaire, je peux retenter.

### 6. Comment formuler une réclamation auprès d'une SCPI ? ≠
- **Rapide** ✓ — Pour formuler une réclamation, vous pouvez envoyer un courrier à Amundi Immobilier à Gestion des associés, TSA 56003, 26906 VALENCE Cedex 9, ou un e-mail à serviceclients-amundiimmo@amundi.com [4]. Vous devez indiquer clairement vos coordonnées (nom, adresse, téléphone ou e-mail, identifiant client) et fournir une brève explication de votre réclamation [4]. Si votre réclamation concerne la personne qui vous a conseillé ou vendu le produit, vous devez vous rapprocher d'elle pour obtenir les informations sur la démarche à suivre [4].
- **CRAG** ✗ ↻ — Je ne sais pas répondre à cette question à partir des documents disponibles. Si tu peux préciser ta question ou fournir un contexte supplémentaire, je peux retenter.

### 7. Qui a agréé le FCPI Amundi Avenir Innovation et sous quel numéro ?
- **Rapide** ✗ — Le FCPI Amundi Avenir Innovation a été agréé par l'Autorité des marchés financiers (AMF) [1]. Les documents fournis ne permettent pas de répondre concernant le numéro d'agrément de ce fonds.
- **CRAG** ✗ ↻ — Je ne sais pas répondre à cette question à partir des documents disponibles. Si tu peux préciser ta question ou fournir un contexte supplémentaire, je peux retenter.

### 8. Quel avantage fiscal offre la souscription à un FCPI éligible ?
- **Rapide** ✓ — Le FCPI éligible offre des avantages fiscaux en matière d'impôt sur le revenu (IR), comprenant une réduction d'impôt et une exonération [1]. Les détails précis de ces avantages sont détaillés dans la Note Fiscale du Fonds, remise aux porteurs préalablement à leur souscription [1]. Ces avantages sont susceptibles d'être modifiés en cas de changement de la réglementation [1].
- **CRAG** ✓ ↻ — La souscription à un FCPI éligible permet aux personnes physiques redevables de l'impôt sur le revenu de bénéficier d'une réduction d'impôt sur le revenu prévue par l'article 199 terdecies-0 A du Code général des impôts [3]. Cette réduction s'applique pour des souscriptions réalisées jusqu'au 29 décembre 2023 pour les parts de catégorie A1 et jusqu'au 31 décembre 2024 pour les parts de catégorie A2 [3]. Les conditions détaillées pour en bénéficier figurent dans la Note Fiscale du Fonds [2].

### 9. Qu'est-ce qu'un FCPI et quel est son quota d'investissement réglementaire ? ≠
- **Rapide** ✓ — Un FCPI est un Fonds Commun de Placement dans l'Innovation, qui est principalement investi dans des entreprises non cotées en bourse [1]. Son quota réglementaire est de 60% de l'actif éligible [1].
- **CRAG** ✗ ↻ — Je ne sais pas répondre à cette question à partir des documents disponibles. Si tu peux préciser ta question ou fournir un contexte supplémentaire, je peux retenter.

### 10. Comment se déroule la souscription d'un FCPI et quelle est la nature de l'engagement du souscripteur ?
- **Rapide** ✓ — La souscription de parts d'un FCPI emporte acceptation de son Règlement [1]. L'engagement du souscripteur est important car l'argent est bloqué pendant une durée minimale de 8 années, pouvant aller jusqu'à 10 ans en cas de prorogation sur décision de la société de gestion, sauf cas de déblocage anticipés prévus dans le Règlement [1]. Il convient de noter que ce fonds est principalement investi dans des entreprises non cotées en bourse présentant des risques particuliers [1].
- **CRAG** ✓ — La souscription de parts de FCPI emporte acceptation de son Règlement [1]. Les demandes doivent être centralisées auprès du Dépositaire (CACEIS Bank) avant 12h30 la veille du jour d'établissement de la valeur liquidative, et sont exécutées sur la base de la prochaine valeur liquidative [4]. La souscription initiale minimale est d'une part, de même que les souscriptions ultérieures [4].

### 11. Dans quelles circonstances un FCPI peut-il être dissous par anticipation ? ≠
- **Rapide** ✓ — La société de gestion peut dissoudre par anticipation le FCPI ; elle informe alors les porteurs de parts de sa décision et à partir de cette date les demandes de souscription ou de rachat ne sont plus acceptées [1][2][3][4][5][6].
- **CRAG** ✗ — Les documents fournis ne permettent pas de répondre.

### 12. Comment la société de gestion décide-t-elle de la répartition des résultats d'un FCPI ?
- **Rapide** ✓ — La Société de Gestion décide de la répartition des résultats [1]. Pour chaque catégorie de parts, le FCP peut opter pour la capitalisation pure, la distribution pure, ou une formule où la Société de Gestion décide chaque année de l'affectation des résultats pour conserver la liberté de capitaliser ou de distribuer [1]. Les documents fournis font référence aux FCP et non explicitement aux FCPI [1].
- **CRAG** ✓ — La Société de Gestion décide de la répartition des résultats [1][2][3][4][5][6]. Pour chaque catégorie de parts, elle peut opter pour la capitalisation pure, la distribution pure, ou conserver la liberté de capitaliser ou/et de distribuer, auquel cas elle décide chaque année de l'affectation des résultats [1][2][4][5][6].

### 13. Comment est déterminée la valeur nominale des parts d'un FCPI ? ≠
- **Rapide** ✗ — Les documents fournis ne permettent pas de répondre.
- **CRAG** ✓ — La valeur nominale des parts d'un FCPI est de 100 € pour les catégories A1 et A2, et de 10 € pour la catégorie B [1]. La valeur initiale des parts à la constitution du fonds est de 10 € [3][4].

### 14. Pendant combien d'années les parts d'un FCPI sont-elles bloquées ?
- **Rapide** ✗ — Les documents fournis ne permettent pas de répondre. Les textes définissent le FCPI [1] et la période de blocage [1], mais ne précisent pas le nombre d'années pendant lesquelles les parts sont bloquées, indiquant seulement que cette période est définie à l'article 11 [1].
- **CRAG** ✗ ↻ — Je ne sais pas répondre à cette question à partir des documents disponibles. Si tu peux préciser ta question ou fournir un contexte supplémentaire, je peux retenter.

### 15. Quelles sont les conditions pour bénéficier de l'exonération d'impôt sur le revenu sur les distributions du fonds ?
- **Rapide** ✓ — Pour bénéficier de l'exonération d'impôt sur le revenu sur les distributions du fonds, l'investisseur doit être une personne physique redevable de l'impôt sur le revenu [1]. Il est également obligatoire de conserver les parts du fonds jusqu'à la cinquième année suivant la date de leur souscription [2]. Par ailleurs, aucune personne physique, agissant directement ou par personne interposée, ne doit détenir plus de 10 % des parts du fonds [1].
- **CRAG** ✓ ↻ — Les documents fournis indiquent que le Fonds ne propose que des parts de capitalisation [3][5], ce qui implique qu'il n'y a pas de distributions classiques de revenus aux porteurs. En revanche, l'exonération d'impôt sur le revenu sur les produits et plus-values reçus du Fonds est conditionnée à la conservation des parts jusqu'à la cinquième année suivant la date de souscription [2]. Cette exonération est susceptible d'être remise en cause en cas de non-respect de cet engagement, notamment en cas de transfert de parts, sauf exceptions réglementaires [2].

### 16. Comment est calculée la commission de gestion annuelle du fonds ?
- **Rapide** ✓ — Pour plusieurs fonds mentionnés, les frais de gestion financière et de fonctionnement sont calculés en appliquant un pourcentage maximum à l'actif net [1] [4] [5]. Des frais indirects de gestion sont également prélevés sur l'actif net avec des plafonds spécifiques à chaque fonds [1] [2] [4] [5]. Pour un autre fonds, la commission de gestion annuelle est fixée à 2 % nets de taxe et s'applique au Montant Net Investi [6]. Elle est calculée et payée semestriellement à terme échu au prorata temporis, sur la base du Montant Net Investi du dernier jour du semestre précédent [6].
- **CRAG** ✓ — La commission de gestion annuelle du fonds est fixée à 2% net de toute taxe, appliquée au Montant Net Investi [5]. Elle est calculée semestriellement à terme échu (les 1er janvier et 1er juillet), sur une base prorata temporis [5]. Le calcul porte sur le Montant Net Investi au dernier jour du semestre précédent [5].

### 17. Quelles sont les règles applicables à la cession, au nantissement et au transfert de parts ? ≠
- **Rapide** ✓ — La cession englobe toute forme de vente, transfert, échange, apport ou nantissement de tout ou partie des parts du Fonds par un porteur [1]. Sauf en cas de succession ou de donation-partage, la cession ou le transfert de parts entre porteurs ou à un tiers est assimilé à un rachat suivi d'une souscription [2] [3] [4] [5] [6]. S'il s'agit d'un tiers, le bénéficiaire doit compléter le montant de la cession ou du transfert pour atteindre le minimum de souscription exigé par le prospectus du FCP [2] [3] [4] [5] [6].
- **CRAG** ✗ ↻ — Je ne sais pas répondre à cette question à partir des documents disponibles. Si tu peux préciser ta question ou fournir un contexte supplémentaire, je peux retenter.

### 18. Quelle est la durée de vie du fonds et comment peut-elle être prorogée ?
- **Rapide** ✓ — La durée de vie du fonds est de huit ans à compter de sa date de constitution [1]. Elle peut être prorogée par la société de gestion, en accord avec le dépositaire, pour une période supplémentaire d'un an afin de permettre la liquidation des investissements [1] [4]. Cette décision doit être prise et communiquée aux porteurs de parts, au dépositaire et à l'Autorité des marchés financiers au moins trois mois avant l'expiration de la durée initiale [1] [4].
- **CRAG** ✓ ↻ — La durée de vie du fonds est de huit ans à compter de sa date de constitution [1]. Cette durée peut être prorogée par la Société de gestion pour une période d'un an, afin notamment d'assurer la liquidation des investissements [1]. Cette décision doit être prise en accord avec le Dépositaire, au moins trois mois avant l'expiration de la durée initiale, et être notifiée aux porteurs de parts et à l'Autorité des marchés financiers [1][4][6]. La durée totale, incluant les prorogations, ne peut excéder la durée prévue par l'article D.214-80 du Code monétaire et financier [2][3].

### 19. Comment les droits des copropriétaires sont-ils exprimés dans un FCPE ?
- **Rapide** ✓ — Les droits des copropriétaires sont exprimés en parts, chaque part correspondant à une même fraction de l'actif du FCP [1]. Chaque porteur de parts dispose d'un droit de copropriété sur les actifs du FCP proportionnel au nombre de parts possédées [1]. Les documents fournis font référence aux FCP et non explicitement aux FCPE [1].
- **CRAG** ✓ — Les droits des copropriétaires sont exprimés en parts, chaque part correspondant à une même fraction de l'actif du FCP [1]. Chaque porteur de parts dispose d'un droit de copropriété sur les actifs du FCP proportionnel au nombre de parts possédées [3].

### 20. Quels risques spécifiques sont associés aux fonds investissant dans des petites et moyennes capitalisations ?
- **Rapide** ✓ — Les fonds investissant dans des petites et moyennes capitalisations sont exposés à un volume d'échanges réduit sur ces titres cotés, ce qui rend les mouvements de marché plus marqués et plus rapides, tant à la hausse qu'à la baisse, par rapport aux grandes capitalisations [1], [2], [3], [6]. En conséquence, la valeur liquidative du fonds peut baisser de manière rapide et forte [1], [2], [3], [6]. De plus, ce volume réduit engendre un risque de liquidité qui peut impacter la valorisation du fonds et les conditions de prix lors de la liquidation des positions, particulièrement en cas de rachats importants [6]. Cela peut même rendre la cession des titres impossible, entraînant une baisse de la valeur liquidative ou sa suspension en cas de non-cotation [6].
- **CRAG** ✓ — Les risques spécifiques incluent une volatilité accrue en raison d'un volume de transactions plus réduit, entraînant des mouvements de marché plus marqués et plus rapides, pouvant provoquer une baisse rapide et forte de la valeur liquidative du fonds [1][2][3]. De plus, la liquidité inférieure de ces marchés peut rendre la cession des titres difficile, voire impossible dans certains cas, impactant la valorisation et les conditions de sortie [6].

### 21. En quoi consiste le risque de liquidité pour un fonds commun de placement ?
- **Rapide** ✓ — Le risque de liquidité correspond à l'impossibilité de vendre un actif au prix anticipé ou dans les délais souhaités en raison de l'étroitesse structurelle ou conjoncturelle du marché [1]. Il se matérialise par une diminution du prix de cession des actifs concernés ou par un délai dans l'ajustement et la liquidation du portefeuille [1]. De plus, lorsque le fonds investit dans des instruments financiers susceptibles d'avoir un faible niveau de liquidité dans certaines circonstances, sa valeur liquidative risque de diminuer [2], [3], [4], [5], [6].
- **CRAG** ✓ — Le risque de liquidité pour un fonds commun de placement correspond au fait de ne pas pouvoir vendre un actif au prix anticipé ou dans les délais souhaités, en raison de l'étroitesse structurelle ou conjoncturelle du marché [1]. Ce risque se matérialise par une diminution du prix de cession des actifs et/ou un délai dans la liquidation du portefeuille [1]. Lorsqu'une partie des investissements du FCP est réalisée dans des instruments financiers susceptibles d'avoir un niveau de liquidité faible dans certaines circonstances, la valeur liquidative du FCP est susceptible de diminuer [3][4].

### 22. Comment fonctionne le mécanisme de plafonnement des rachats (Gates) ?
- **Rapide** ✓ — Le mécanisme de plafonnement des rachats (« gates ») permet d'étaler les demandes de rachats sur plusieurs valeurs liquidatives lorsqu'elles dépassent un niveau fixé [1]. Ce dispositif exceptionnel ne se déclenche qu'en cas de forte dégradation de la liquidité des marchés et de rachats importants au passif du FCP [1], [2], [3].
- **CRAG** ✓ — Le mécanisme de plafonnement des rachats (« gates ») permet à la société de gestion d'étaler les demandes de rachats sur plusieurs valeurs liquidatives lorsqu'elles dépassent un seuil fixe de l'actif net du FCP [1][2][4][5]. Ce dispositif exceptionnel n'est déclenché qu'en cas de forte dégradation de la liquidité des marchés conjuguée à des rachats importants [1][2][4][5].

### 23. Quels facteurs guident la stratégie d'investissement du fonds ?
- **Rapide** ✓ — _(pas de réponse)_
- **CRAG** ✓ — La stratégie d'investissement du fonds est guidée par une analyse des cycles économiques et du contexte macroéconomique [1]. La sélection des titres repose sur une analyse de facteurs économiques, financiers et politiques [1], ainsi que sur une approche combinée de critères macroéconomiques (Top-Down) et de critères de sélection des sociétés (Bottom-Up), incluant leur stratégie, leurs perspectives financières et leur évaluation ESG [4]. L'allocation finale dépend également des convictions du gérant et de l'évolution des marchés [1].

### 24. Quels frais sont prélevés à la charge de l'investisseur dans un FCPE ?
- **Rapide** ✓ — Les frais prélevés à la charge de l'investisseur dans un FCPE incluent des frais d'entrée pouvant aller jusqu'à 350 € (soit 3,50 % du montant investi) [5]. Un forfait compris entre 0 et 20 € TTC maximum est également perçu par le dépositaire [1]. Les frais de gestion indirects, fixés à 0,72 % TTC maximum, ainsi que les commissions de mouvement (0,05 % TTC maximum) et les frais de courtage sont à la charge du Fonds [1].
- **CRAG** ✓ — Les coûts de distribution maximaux pouvant être facturés à l'investisseur par le vendeur s'élèvent à 3,50 % du montant investi ou 350 EUR [3]. Un coût annuel de 2,35 % de la valeur de l'investissement est également prélevé [3]. Le produit en lui-même ne facture aucun frais de transaction, aucune commission liée aux résultats ni aucun coût de sortie, bien que le vendeur puisse éventuellement appliquer des frais de sortie [3].

### 25. Quel est le régime fiscal applicable aux plus-values et revenus du FCPE pour un investisseur particulier ? ≠
- **Rapide** ✗ — Les documents fournis ne permettent pas de répondre précisément au régime fiscal applicable aux plus-values et revenus du FCPE pour un investisseur particulier. Les passages mentionnent l'éligibilité au régime de l'abattement de droit commun pour une durée de détention sur le montant net de la plus-value [2][3][5], mais sans détailler les taux ou barèmes applicables. Les documents indiquent également que la fiscalité dépend de la situation particulière de l'investisseur et de sa résidence fiscale [6], et que les résidents français doivent se référer au Code général des impôts [2][3][5].
- **CRAG** ✓ — Le FCP est éligible au régime de l’abattement de droit commun pour une durée de détention [1][2]. Sa qualité de copropriété le place hors du champ de l’impôt sur les sociétés, et les plus-values de cessions sont exonérées sous réserve qu’aucune personne physique ne possède plus de 10% des parts [1][2]. Selon le principe de transparence, le porteur est considéré comme détenteur direct d’une fraction des actifs du fonds [1][2]. La fiscalité applicable est celle des plus-values sur valeurs mobilières du pays de résidence de l’investisseur, et pour les résidents français, elle suit le Code général des impôts [1][2]. Les documents conseillent de consulter un conseiller fiscal pour connaître l’impact sur votre situation personnelle [1][2].

### 26. Qu'est-ce que la politique de traitement équitable des investisseurs dans un FCPE ?
- **Rapide** ✓ — La politique de traitement équitable des investisseurs dans un FCPE vise à garantir que tous les porteurs d'une même catégorie de parts reçoivent un traitement identique [1][2].
- **CRAG** ✓ — La politique de traitement équitable des investisseurs dans un FCPE garantit que la société de gestion assure un traitement équitable à tous les porteurs d'une même catégorie de parts de l'OPC [1][2]. Les modalités de souscription, de rachat et l'accès aux informations sur l'OPC sont identiques pour tous les porteurs d'une même catégorie de parts [1][2].

### 27. Quelle société de gestion administre les fonds Amundi et comment la contacter ?
- **Rapide** ✓ — Nous avons six passages numérotés. La question est : "Quelle société de gestion administre les fonds Amundi et comment la contacter ?"
- **CRAG** ✓ — La société de gestion est Amundi Asset Management [2], [4]. Vous pouvez la contacter par téléphone au +33 143233030 [1], par courrier au 91-93 boulevard Pasteur, 75015 Paris, France [6], par e-mail à complaints@amundi.com [6] ou via le site Internet www.amundi.fr [1]. Les documents citent également Amundi Private Equity Funds comme société de gestion pour certains produits [3], ainsi qu'un contact spécifique pour l'immobilier à l'adresse serviceclients-amundiimmo@amundi.com [5].

### 28. Quel est le taux de TVA applicable aux loyers d'habitation en France ?
- **Rapide** ✗ — Les documents fournis ne permettent pas de répondre. Les passages traitent de fiscalité des fonds d'investissement et de frais de gestion, mais ne mentionnent pas le taux de TVA applicable aux loyers d'habitation en France.
- **CRAG** ✗ — Je ne sais pas répondre à cette question à partir des documents disponibles. Si tu peux préciser ta question ou fournir un contexte supplémentaire, je peux retenter.

### 29. Quelles sont les étapes pour obtenir un prêt immobilier auprès d'une banque française ?
- **Rapide** ✗ — Les documents fournis ne permettent pas de répondre.
- **CRAG** ✗ ↻ — Je ne sais pas répondre à cette question à partir des documents disponibles. Si tu peux préciser ta question ou fournir un contexte supplémentaire, je peux retenter.

### 30. Quelles sont les règles légales applicables aux heures supplémentaires en droit du travail français ?
- **Rapide** ✗ — Les documents fournis ne permettent pas de répondre. Les passages portent sur des dispositions relatives aux fonds d'investissement, au fonctionnement de conseils de surveillance et à des informations financières, mais ne traitent pas des règles légales applicables aux heures supplémentaires en droit du travail français.
- **CRAG** ✗ ↻ — Je ne sais pas répondre à cette question à partir des documents disponibles. Si tu peux préciser ta question ou fournir un contexte supplémentaire, je peux retenter.
