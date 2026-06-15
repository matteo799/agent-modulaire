# Mémoire de travail

### Étape : Utiliser rag_search pour rechercher les risques associés au projet Alpha dans les documents internes
Outil : rag_search
Résultat :
[projet_alpha.md — score 0.62]
# Projet Alpha — Note interne

## Contexte

Le projet Alpha vise à migrer le système de facturation vers une nouvelle
plateforme cloud d'ici décembre 2026. Le budget alloué est de 450 000 €
et l'équipe compte 8 personnes.

## Risques identifiés

### Risque technique
La base de données actuelle utilise un schéma propriétaire non documenté.
La migration des 12 millions d'enregistrements pourrait entraîner des pertes
de données si le mapping n'est pas validé par des tests exhaustifs.

### Risque de planning
Deux développeurs seniors quittent l'entreprise en septembre 2026. Sans plan
de transfert de connaissances, le projet pourrait prendre 3 à 4 mois de retard.

### Risque financier
Le fournisseur cloud a annoncé une hausse tarifaire de 15 % applicable en 2027.
Le coût d'exploitation annuel p

[projet_alpha.md — score 0.57]
mois de retard.

### Risque financier
Le fournisseur cloud a annoncé une hausse tarifaire de 15 % applicable en 2027.
Le coût d'exploitation annuel passerait de 80 000 € à 92 000 €, ce qui n'est
pas prévu dans le budget actuel.

### Risque de conformité
Les données de facturation contiennent des informations personnelles soumises
au RGPD. L'hébergement doit rester dans l'Union européenne, ce qui exclut
deux des trois régions cloud envisagées.

## Recommandations

- Lancer un audit du schéma de base de données dès juillet 2026.
- Documenter les connaissances critiques avant le départ des seniors.
- Renégocier le contrat cloud ava

### Étape : Utiliser read_file pour lire le document contenant l'analyse initiale du projet Alpha
Outil : read_file
Résultat :
# Projet Alpha — Note interne

## Contexte

Le projet Alpha vise à migrer le système de facturation vers une nouvelle
plateforme cloud d'ici décembre 2026. Le budget alloué est de 450 000 €
et l'équipe compte 8 personnes.

## Risques identifiés

### Risque technique
La base de données actuelle utilise un schéma propriétaire non documenté.
La migration des 12 millions d'enregistrements pourrait entraîner des pertes
de données si le mapping n'est pas validé par des tests exhaustifs.

### Risque de planning
Deux développeurs seniors quittent l'entreprise en septembre 2026. Sans plan
de transfert de connaissances, le projet pourrait prendre 3 à 4 mois de retard.

### Risque financier
Le fournisseur cloud a annoncé une hausse tarifaire de 15 % applicable en 2027.
Le coût d'exploitation annuel passerait de 80 000 € à 92 000 €, ce qui n'est
pas prévu dans le budget actuel.

### Risque de conformité
Les données de facturation contiennent des informations personnelles soumises
au RGPD. L'hébergement doit rester dans l'Union européenne, ce qui exclut
deux des trois régions cloud envisagées.

## Recommandations

- Lancer un audit du schéma de base de données dès juillet 2026.
- Documenter les connaissances critiques avant le départ des seniors.
- Renégocier le contrat cloud avant la hausse tarifaire.


### Étape : Utiliser rag_search pour identifier et extraire les informations clés concernant les risques du projet Alpha
Outil : write_file
Résultat :
Fichier écrit : workspace/risques_projet_alpha.md (1026 caractères)

### Étape : Écrire un résumé des risques identifiés dans un fichier temporaire avec write_file
Outil : write_file
Résultat :
Fichier écrit : workspace/workspace/risques_projet_alpha.md (900 caractères)

### Étape : Réviser le résumé et l'affiner avant de le finaliser
Outil : write_file
Résultat :
Fichier écrit : workspace/workspace/referentiel_risques_projet_alpha.md (423 caractères)