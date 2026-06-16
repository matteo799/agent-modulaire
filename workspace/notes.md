# Mémoire de travail

### Étape : Chercher le budget initial du projet Alpha avec rag_search
Outil : rag_search
Résultat :
[projet_alpha.md — score 0.62]
## Contexte

Le projet Alpha vise à migrer le système de facturation vers une nouvelle
plateforme cloud d'ici décembre 2026. Le budget alloué est de 450 000 €
et l'équipe compte 8 personnes.

[projet_alpha.md — score 0.59]
### Risque financier
Le fournisseur cloud a annoncé une hausse tarifaire de 15 % applicable en 2027.
Le coût d'exploitation annuel passerait de 80 000 € à 92 000 €, ce qui n'est
pas prévu dans le budget actuel.

[projet_alpha.md — score 0.53]
### Risque de planning
Deux développeurs seniors quittent l'entreprise en septembre 2026. Sans plan
de transfert de connaissances, le projet pourrait prendre 3 à 4 mois de retard.

### Étape : Chercher la hausse annuelle du coût d'exploitation du projet Alpha avec rag_search
Outil : rag_search
Résultat :
[projet_alpha.md — score 0.74]
### Risque financier
Le fournisseur cloud a annoncé une hausse tarifaire de 15 % applicable en 2027.
Le coût d'exploitation annuel passerait de 80 000 € à 92 000 €, ce qui n'est
pas prévu dans le budget actuel.

[projet_alpha.md — score 0.68]
### Risque technique
La base de données actuelle utilise un schéma propriétaire non documenté.
La migration des 12 millions d'enregistrements pourrait entraîner des pertes
de données si le mapping n'est pas validé par des tests exhaustifs.

[projet_alpha.md — score 0.66]
## Recommandations

- Lancer un audit du schéma de base de données dès juillet 2026.
- Documenter les connaissances critiques avant le départ des seniors.
- Renégocier le contrat cloud avant la hausse tarifaire.

### Étape : Utiliser calculator pour additionner le budget initial et l'historique des hausses annuelles
Outil : calculator
Résultat :
542000

### Étape : Écrire le rapport final avec write_file
Outil : calculator
Résultat :
462000