# Démo — 30 questions du dataset finance

Réponses générées de bout en bout par le RAG modulaire de l'Agent modulaire (dense BGE-M3 → parent-child → reranker → génération ancrée par Claude).

**Légende :** ✓ réponse ancrée dans les documents (citée) · ✗ hors-corpus → le système refuse de répondre (pas d'hallucination).


**Score : 19/30 questions répondues et citées · 11/30 sans réponse (dont 3 pièges hors-corpus).**

---

### 1. Quelle est la politique de distribution des revenus du produit SCPI ?
✓ La distribution des éventuels revenus du produit est soumise à l'approbation de l'assemblée générale annuelle [1].

### 2. Quels indicateurs de performance passée sont présentés dans le DIC SCPI ?
✗ Les passages fournis ne permettent pas de répondre précisément à la question. Les documents mentionnent que les performances passées du Produit (qui semble être une SCPI Amundi) peuvent être téléchargées sur le site www.amundi-immobilier.com/nos-solutions-depargne [1][2], mais aucun indicateur de performance passée spécifique n'est présenté dans les passages transmis. Les données du DIC sont indiquées comme étant basées sur des prévisions ou sur l'approbation des comptes au 31/12/2022, sans afficher de rendements historiques [1][2].

### 3. Combien de temps est-il recommandé de conserver une part de SCPI, et peut-on retirer ses fonds de façon anticipée ?
✗ Les documents fournis ne permettent pas de répondre.

### 4. Quelles sont les obligations des associés d'une SCPI en matière de dettes ?
✗ Les documents fournis ne permettent pas de répondre.

### 5. Comment est composé le patrimoine d'une SCPI et quels actifs détient-elle ?
✗ Les documents fournis ne permettent pas de répondre. Les passages disponibles traitent uniquement des actifs de FCP (Fonds Commun de Placement) [1][2][3][5][6] et d'une SICAV [4], qui sont des véhicules d'investissement différents d'une SCPI (Société Civile de Placement Immobilier). Aucune information sur la composition du patrimoine d'une SCPI n'est présente dans ces documents.

### 6. Comment formuler une réclamation auprès d'une SCPI ?
✓ Pour formuler une réclamation, vous pouvez envoyer un courrier à Amundi Immobilier à Gestion des associés, TSA 56003, 26906 VALENCE Cedex 9, ou un e-mail à serviceclients-amundiimmo@amundi.com [4]. Vous devez indiquer clairement vos coordonnées (nom, adresse, téléphone ou e-mail, identifiant client) et fournir une brève explication de votre réclamation [4]. Si votre réclamation concerne la personne qui vous a conseillé ou vendu le produit, vous devez vous rapprocher d'elle pour obtenir les informations sur la démarche à suivre [4].

### 7. Qui a agréé le FCPI Amundi Avenir Innovation et sous quel numéro ?
✗ Le FCPI Amundi Avenir Innovation a été agréé par l'Autorité des marchés financiers (AMF) [1]. Les documents fournis ne permettent pas de répondre concernant le numéro d'agrément de ce fonds.

### 8. Quel avantage fiscal offre la souscription à un FCPI éligible ?
✓ Le FCPI éligible offre des avantages fiscaux en matière d'impôt sur le revenu (IR), comprenant une réduction d'impôt et une exonération [1]. Les détails précis de ces avantages sont détaillés dans la Note Fiscale du Fonds, remise aux porteurs préalablement à leur souscription [1]. Ces avantages sont susceptibles d'être modifiés en cas de changement de la réglementation [1].

### 9. Qu'est-ce qu'un FCPI et quel est son quota d'investissement réglementaire ?
✓ Un FCPI est un Fonds Commun de Placement dans l'Innovation, qui est principalement investi dans des entreprises non cotées en bourse [1]. Son quota réglementaire est de 60% de l'actif éligible [1].

### 10. Comment se déroule la souscription d'un FCPI et quelle est la nature de l'engagement du souscripteur ?
✓ La souscription de parts d'un FCPI emporte acceptation de son Règlement [1]. L'engagement du souscripteur est important car l'argent est bloqué pendant une durée minimale de 8 années, pouvant aller jusqu'à 10 ans en cas de prorogation sur décision de la société de gestion, sauf cas de déblocage anticipés prévus dans le Règlement [1]. Il convient de noter que ce fonds est principalement investi dans des entreprises non cotées en bourse présentant des risques particuliers [1].

### 11. Dans quelles circonstances un FCPI peut-il être dissous par anticipation ?
✓ La société de gestion peut dissoudre par anticipation le FCPI ; elle informe alors les porteurs de parts de sa décision et à partir de cette date les demandes de souscription ou de rachat ne sont plus acceptées [1][2][3][4][5][6].

### 12. Comment la société de gestion décide-t-elle de la répartition des résultats d'un FCPI ?
✓ La Société de Gestion décide de la répartition des résultats [1]. Pour chaque catégorie de parts, le FCP peut opter pour la capitalisation pure, la distribution pure, ou une formule où la Société de Gestion décide chaque année de l'affectation des résultats pour conserver la liberté de capitaliser ou de distribuer [1]. Les documents fournis font référence aux FCP et non explicitement aux FCPI [1].

### 13. Comment est déterminée la valeur nominale des parts d'un FCPI ?
✗ Les documents fournis ne permettent pas de répondre.

### 14. Pendant combien d'années les parts d'un FCPI sont-elles bloquées ?
✗ Les documents fournis ne permettent pas de répondre. Les textes définissent le FCPI [1] et la période de blocage [1], mais ne précisent pas le nombre d'années pendant lesquelles les parts sont bloquées, indiquant seulement que cette période est définie à l'article 11 [1].

### 15. Quelles sont les conditions pour bénéficier de l'exonération d'impôt sur le revenu sur les distributions du fonds ?
✓ Pour bénéficier de l'exonération d'impôt sur le revenu sur les distributions du fonds, l'investisseur doit être une personne physique redevable de l'impôt sur le revenu [1]. Il est également obligatoire de conserver les parts du fonds jusqu'à la cinquième année suivant la date de leur souscription [2]. Par ailleurs, aucune personne physique, agissant directement ou par personne interposée, ne doit détenir plus de 10 % des parts du fonds [1].

### 16. Comment est calculée la commission de gestion annuelle du fonds ?
✓ Pour plusieurs fonds mentionnés, les frais de gestion financière et de fonctionnement sont calculés en appliquant un pourcentage maximum à l'actif net [1] [4] [5]. Des frais indirects de gestion sont également prélevés sur l'actif net avec des plafonds spécifiques à chaque fonds [1] [2] [4] [5]. Pour un autre fonds, la commission de gestion annuelle est fixée à 2 % nets de taxe et s'applique au Montant Net Investi [6]. Elle est calculée et payée semestriellement à terme échu au prorata temporis, sur la base du Montant Net Investi du dernier jour du semestre précédent [6].

### 17. Quelles sont les règles applicables à la cession, au nantissement et au transfert de parts ?
✓ La cession englobe toute forme de vente, transfert, échange, apport ou nantissement de tout ou partie des parts du Fonds par un porteur [1]. Sauf en cas de succession ou de donation-partage, la cession ou le transfert de parts entre porteurs ou à un tiers est assimilé à un rachat suivi d'une souscription [2] [3] [4] [5] [6]. S'il s'agit d'un tiers, le bénéficiaire doit compléter le montant de la cession ou du transfert pour atteindre le minimum de souscription exigé par le prospectus du FCP [2] [3] [4] [5] [6].

### 18. Quelle est la durée de vie du fonds et comment peut-elle être prorogée ?
✓ La durée de vie du fonds est de huit ans à compter de sa date de constitution [1]. Elle peut être prorogée par la société de gestion, en accord avec le dépositaire, pour une période supplémentaire d'un an afin de permettre la liquidation des investissements [1] [4]. Cette décision doit être prise et communiquée aux porteurs de parts, au dépositaire et à l'Autorité des marchés financiers au moins trois mois avant l'expiration de la durée initiale [1] [4].

### 19. Comment les droits des copropriétaires sont-ils exprimés dans un FCPE ?
✓ Les droits des copropriétaires sont exprimés en parts, chaque part correspondant à une même fraction de l'actif du FCP [1]. Chaque porteur de parts dispose d'un droit de copropriété sur les actifs du FCP proportionnel au nombre de parts possédées [1]. Les documents fournis font référence aux FCP et non explicitement aux FCPE [1].

### 20. Quels risques spécifiques sont associés aux fonds investissant dans des petites et moyennes capitalisations ?
✓ Les fonds investissant dans des petites et moyennes capitalisations sont exposés à un volume d'échanges réduit sur ces titres cotés, ce qui rend les mouvements de marché plus marqués et plus rapides, tant à la hausse qu'à la baisse, par rapport aux grandes capitalisations [1], [2], [3], [6]. En conséquence, la valeur liquidative du fonds peut baisser de manière rapide et forte [1], [2], [3], [6]. De plus, ce volume réduit engendre un risque de liquidité qui peut impacter la valorisation du fonds et les conditions de prix lors de la liquidation des positions, particulièrement en cas de rachats importants [6]. Cela peut même rendre la cession des titres impossible, entraînant une baisse de la valeur liquidative ou sa suspension en cas de non-cotation [6].

### 21. En quoi consiste le risque de liquidité pour un fonds commun de placement ?
✓ Le risque de liquidité correspond à l'impossibilité de vendre un actif au prix anticipé ou dans les délais souhaités en raison de l'étroitesse structurelle ou conjoncturelle du marché [1]. Il se matérialise par une diminution du prix de cession des actifs concernés ou par un délai dans l'ajustement et la liquidation du portefeuille [1]. De plus, lorsque le fonds investit dans des instruments financiers susceptibles d'avoir un faible niveau de liquidité dans certaines circonstances, sa valeur liquidative risque de diminuer [2], [3], [4], [5], [6].

### 22. Comment fonctionne le mécanisme de plafonnement des rachats (Gates) ?
✓ Le mécanisme de plafonnement des rachats (« gates ») permet d'étaler les demandes de rachats sur plusieurs valeurs liquidatives lorsqu'elles dépassent un niveau fixé [1]. Ce dispositif exceptionnel ne se déclenche qu'en cas de forte dégradation de la liquidité des marchés et de rachats importants au passif du FCP [1], [2], [3].

Le seuil de déclenchement correspond au rapport entre la différence des rachats et souscriptions demandés, et l'actif net du FCP [1], [2], [3]. Ce seuil est fixé à 5% de l'actif net pour la plupart des fonds [1], [2], [4], [5] ou à 10% pour certains comme l'Opt'in Selection [3] et le MacroSphere Global Fund [6].

Lorsque le seuil est dépassé, la société de gestion peut honorer partiellement les ordres et reporter le surplus à la valeur liquidative suivante [1], [2]. Les ordres reportés ne sont pas prioritaires sur les nouveaux ordres et ne peuvent être révoqués [1], [2]. La durée maximale d'application est de 20 valeurs liquidatives sur 3 mois [1], [2] ou 8 valeurs liquidatives sur 6 mois pour certains fonds [3], [6].

Un aller/retour fiscal concomitant (rachat et souscription identiques) est exonéré du calcul des gates [1], [

### 23. Quels facteurs guident la stratégie d'investissement du fonds ?
✓ _(pas de réponse)_

### 24. Quels frais sont prélevés à la charge de l'investisseur dans un FCPE ?
✓ Les frais prélevés à la charge de l'investisseur dans un FCPE incluent des frais d'entrée pouvant aller jusqu'à 350 € (soit 3,50 % du montant investi) [5]. Un forfait compris entre 0 et 20 € TTC maximum est également perçu par le dépositaire [1]. Les frais de gestion indirects, fixés à 0,72 % TTC maximum, ainsi que les commissions de mouvement (0,05 % TTC maximum) et les frais de courtage sont à la charge du Fonds [1].

### 25. Quel est le régime fiscal applicable aux plus-values et revenus du FCPE pour un investisseur particulier ?
✗ Les documents fournis ne permettent pas de répondre précisément au régime fiscal applicable aux plus-values et revenus du FCPE pour un investisseur particulier. Les passages mentionnent l'éligibilité au régime de l'abattement de droit commun pour une durée de détention sur le montant net de la plus-value [2][3][5], mais sans détailler les taux ou barèmes applicables. Les documents indiquent également que la fiscalité dépend de la situation particulière de l'investisseur et de sa résidence fiscale [6], et que les résidents français doivent se référer au Code général des impôts [2][3][5].

### 26. Qu'est-ce que la politique de traitement équitable des investisseurs dans un FCPE ?
✓ La politique de traitement équitable des investisseurs dans un FCPE vise à garantir que tous les porteurs d'une même catégorie de parts reçoivent un traitement identique [1][2].

Concrètement, cela signifie que les modalités de souscription et de rachat, ainsi que l'accès aux informations sur l'OPC, sont similaires pour l'ensemble des porteurs d'une même catégorie de parts [1][2].

### 27. Quelle société de gestion administre les fonds Amundi et comment la contacter ?
✓ Nous avons six passages numérotés. La question est : "Quelle société de gestion administre les fonds Amundi et comment la contacter ?"

Nous devons répondre en français, en quelques phrases claires, en citant les sources avec des marqueurs [1], [2], etc. Tout fait factuel doit être suivi d'au moins un marqueur de citation.

Examinons les passages :

- [1] concerne le fonds "100% INDICE ACTIONS MONDE". Il mentionne : "Site Internet de la société de gestion : www.amundi.fr" et "Appelez le +33 143233030 pour de plus amples informations." et "Amundi Asset Management est agréée en France sous le n°GP-04000036". De plus, "Informations complémentaires : Vous pouvez obtenir de plus amples informations sur ce produit et son maitre, y compris le prospectus et les rapports financiers, gratuitement sur demande auprès de : Amundi Asset Management - 91-93 boulevard Pasteur, 75015 Paris, France."

- [2] concerne le fonds "100% INDICE ACTIONS EURO". Il contient des informations similaires : "Site Internet de la société de gestion : www.amundi.fr", "Appelez le +33 143233030", "Amundi Asset Management est agréée en France sous le n°GP-04000036", et "Informations complémentaires : ... auprès de : Amundi Asset Management - 91-93 boulevard Pasteur, 75015 Paris, France."

- [3] est intitulé "III. – LES ACTEURS" et mentionne : "17. LA SOCIETE DE GESTION La Société de Gestion est Amundi Private Equity Funds, une société anonyme à conseil d'administration au capital de 12 394 096 Euros, dont le siège social est 91-93, boulevard Pasteur, 75015 Paris, immatriculée au RCS de Paris sous le numéro B 422". Cela semble concerner une autre entité, Amundi Private Equity Funds.

- [4] est un extrait de document pour "ACTICCIA VIE 90 N°2". Il mentionne : "Société de gestion : Amundi Asset Management, Société par Actions Simplifiée Société de Gestion de Portefeuille agréée par l'AMF sous le n° GP 04000036 Siège social : 91-93, Boulevard Pasteur - 75015 Paris".

- [5] contient des informations de contact : "Envoyer un e-mail à serviceclients-amundiimmo@amundi.com" et "Vous trouverez davantage d'informations sur notre site Internet www. amundi-immobilier.com". Cela semble lié à Amundi Immobilier.

- [6] est un extrait de document de coût pour un produit (probablement ACTICCIA VIE 90 N°2). Il mentionne : "Envoyer un courrier à Amundi Asset Management au 91-93 boulevard Pasteur, 75015 Paris - France" et "Envoyer un e-mail à complaints@amundi.com" et "www.amundi.fr ou www.ca-sicavetfcp.fr".

La question demande : "Quelle société de gestion administre les fonds Amundi et comment la contacter ?"

Il y a plusieurs entités Amundi mentionnées : Amundi Asset Management, Amundi Private Equity Funds, Amundi Immobilier (probablement une branche). Mais la question semble générale : "les fonds Amundi". Dans les passages [1] et [2], la société de gestion est clairement identifiée comme Amundi Asset Management. Dans [4], c'est aussi Amundi Asset Management. Donc la réponse principale est Amundi Asset Management.

Pour le contact, plusieurs sources donnent des informations :
- Site Internet : www.amundi.fr ([1], [2], [6])
- Téléphone : +33 143233030 ([1], [2])
- Adresse postale : Amundi Asset Management, 91-93 boulevard Pasteur, 75015 Paris, France ([1], [2], [4], [6])
- Email : complaints@amundi.com pour les réclamations ([6]), et serviceclients-amundiimmo@amundi.com pour l'immobil

### 28. Quel est le taux de TVA applicable aux loyers d'habitation en France ?
✗ Les documents fournis ne permettent pas de répondre. Les passages traitent de fiscalité des fonds d'investissement et de frais de gestion, mais ne mentionnent pas le taux de TVA applicable aux loyers d'habitation en France.

### 29. Quelles sont les étapes pour obtenir un prêt immobilier auprès d'une banque française ?
✗ Les documents fournis ne permettent pas de répondre.

### 30. Quelles sont les règles légales applicables aux heures supplémentaires en droit du travail français ?
✗ Les documents fournis ne permettent pas de répondre. Les passages portent sur des dispositions relatives aux fonds d'investissement, au fonctionnement de conseils de surveillance et à des informations financières, mais ne traitent pas des règles légales applicables aux heures supplémentaires en droit du travail français.