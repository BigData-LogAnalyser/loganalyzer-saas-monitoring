# Schéma MongoDB — Historique des recherches

## Emplacement

- Base : variable MONGODB_DATABASE, par défaut loganalyzer.
- Collection : search_history.
- Historique commun à l’application.
- Aucun rattachement à un utilisateur, une session ou un navigateur.

## Structure des documents

| Champ | Type BSON | Signification |
|---|---|---|
| _id | string | UUID unique d’une exécution |
| executed_at | date | Début d’exécution de la recherche en UTC |
| criteria | object | Critères validés et normalisés |
| result_count | int ou long | Nombre total de résultats observé |

## Champs de criteria

| Champ | Type BSON | Valeur sans filtre |
|---|---|---|
| general | string | Chaîne vide |
| q | string | Chaîne vide |
| level | string | Chaîne vide |
| service | string | Chaîne vide |
| start | string ou null | null |
| end | string ou null | null |
| sort | string | date |
| order | string | desc |

Les champs start et end sont des chaînes ISO 8601 UTC ou null.
Ils décrivent la période des événements recherchés.

Le champ executed_at est une date BSON.
L’API le retourne en ISO 8601 UTC avec précision à la milliseconde.

Le numéro de page n’est pas conservé dans criteria.

## Index

MongoDB crée automatiquement l’index unique _id_.

L’index composé history_recent utilise executed_at décroissant,
puis _id décroissant pour départager les dates identiques.

Cet index doit être créé lors de l’installation sur une base neuve.
Il n’impose pas l’unicité des critères de recherche.

Les documents et les index persistent dans le volume MongoDB existant.

## Règles d’enregistrement

- Une recherche réussie sur la page 1 crée une entrée.
- Une recherche sans résultat est conservée.
- Le chargement initial et la réinitialisation exécutent une recherche.
- Relancer les mêmes critères crée une nouvelle entrée.
- La navigation vers les pages suivantes ne crée pas d’entrée.
- Les filtres invalides et les échecs Elasticsearch ne créent pas d’entrée.
- Les exports CSV et la consultation de l’historique ne créent pas d’entrée.
- Les anciennes recherches ne sont pas reconstituées rétroactivement.

Les documents de logs ne sont pas copiés dans MongoDB.
Le compteur représente les résultats au moment de la recherche.
Une exécution ultérieure peut produire un nombre différent.

## Conservation et erreurs

Aucune expiration automatique ni suppression n’est prévue dans SCRUM-22.

Si l’écriture MongoDB échoue, les résultats Elasticsearch restent disponibles.
La réponse indique que l’enregistrement n’a pas pu être confirmé.
Aucune nouvelle tentative applicative automatique n’est effectuée.

Si la consultation MongoDB échoue, l’API d’historique renvoie HTTP 503.

Ce document décrit le contrat produit par l’application.
Il n’active pas de validateur de collection côté MongoDB.
