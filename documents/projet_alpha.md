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
