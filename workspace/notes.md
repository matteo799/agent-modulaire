# Mémoire de travail

### Étape : Rechercher le budget initial du projet Alpha
Outil : rag_search
Résultat :
[projet_alpha.md — score 0.56]
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

### Étape : Rechercher la hausse annuelle du coût d'exploitation du projet Alpha
Outil : rag_search
Résultat :
[projet_alpha.md — score 0.73]
tarifaire.

### Étape : Calculer la nouvelle estimation totale en additionnant le budget initial et l'hypothèse de croissance annuelle
Outil : calculator
Résultat :
517500.0

### Étape : Écrire le rapport final avec les informations trouvées et le coût total calculé
Outil : write_file
Résultat :
Fichier écrit : workspace/rapport_projet_alpha.md (157 caractères)