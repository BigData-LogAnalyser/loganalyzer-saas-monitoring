# Générateur de logs synthétiques

SCRUM-14 — LogAnalyzer

## Objectif

Le programme generator/generate.py simule l'activité d'un SaaS
de gestion de projets et de tâches.

Il produit les mêmes événements dans trois formats conformes
à la structure définie dans le contrat SCRUM-10.

- CSV avec séparateur point-virgule et en-tête de 18 colonnes.
- JSON Lines avec un objet par ligne.
- TXT avec 18 champs séparés par de vraies tabulations.

Les familles générées sont http, application, sql et business.
Toutes les données sont synthétiques.

## Installation

Depuis la racine du dépôt, activer l'environnement Python.

```bash
source .venv/bin/activate
```

Installer les dépendances du générateur.

```bash
python -m pip install -r generator/requirements.txt
```

La version utilisée pendant les vérifications est Faker 40.54.0.
Faker génère les identifiants fictifs des utilisateurs, organisations
et requêtes. Le module random de Python choisit notamment les dates,
les familles, les durées et les erreurs.

Les services Docker peuvent rester arrêtés pendant la génération.

## Exemple d'utilisation

```bash
python generator/generate.py \
  --count 100 \
  --start 2026-11-04T08:00:00Z \
  --end 2026-11-04T09:00:00Z \
  --seed 42 \
  --scenario normal \
  --output ~/jeux-logs/normal-100
```

Cette commande crée 100 événements valides, représentés dans chacun
des trois formats, et un jeu séparé de six événements invalides.

Le dossier de sortie doit être nouveau. Le programme refuse de
réutiliser un dossier existant pour éviter d'écraser des données.

## Paramètres

| Paramètre | Utilité | Valeur par défaut |
|---|---|---|
| --count | Nombre d'événements valides par format, supérieur ou égal à 1 | 1000 |
| --start | Début de la période avec fuseau horaire | Obligatoire |
| --end | Fin de la période avec fuseau horaire | Obligatoire |
| --seed | Graine utilisée pour reproduire les choix aléatoires | 42 |
| --scenario | normal, erreurs, lenteurs ou pic | normal |
| --output | Nouveau dossier où écrire les fichiers | Obligatoire |

La période doit durer au moins une milliseconde.
Les événements générés utilisent des dates UTC avec trois décimales
et le suffixe Z. La borne de fin est exclue.

Les événements sont écrits dans l'ordre de génération.
Le fichier n'est pas trié par date.

## Scénarios

| Scénario | Comportement |
|---|---|
| normal | Activité répartie sur la période avec une probabilité d'erreur de 3 % |
| erreurs | Probabilité d'erreur portée à 40 % |
| lenteurs | Durées HTTP de 3001 à 8000 ms et SQL de 1001 à 5000 ms |
| pic | Probabilité de 80 % de placer un événement dans les 10 % centraux de la période |

Dans les scénarios normal, erreurs et pic, les durées HTTP sont
comprises entre 20 et 500 ms et les durées SQL entre 5 et 300 ms.

Les proportions reposent sur des tirages aléatoires. Le nombre exact
d'erreurs peut donc différer du pourcentage théorique.

Le scénario pic concentre les événements dans le temps.
Les lenteurs et les erreurs massives possèdent leurs propres scénarios.

Les durées sont des valeurs simulées dans les fichiers.
Le programme n'exécute pas de véritables requêtes HTTP ou SQL.

## Organisation des résultats

| Dossier | Contenu |
|---|---|
| valides/ | logs.csv, logs.jsonl et logs.txt avec --count événements chacun |
| invalides/ | Les trois formats avec six événements incorrects chacun et attendus.json |
| reference/valides/ | Les quatre événements de référence de SCRUM-10 dans les trois formats |
| reference/attendus.json | Résultats attendus du jeu de référence et diagnostics du corpus SCRUM-10 |
| reference/README-source.md | Copie du README du corpus SCRUM-10 |

Les trois fichiers d'un même dossier représentent les mêmes événements.
Pour tester un import de 100 événements, importer un seul fichier
du dossier valides.

Un CSV contient une ligne supplémentaire pour son en-tête.
Un TXT ou JSONL ne contient pas d'en-tête.

Le README source décrit le corpus SCRUM-10 complet.
Le générateur copie uniquement ses fichiers valides, ses résultats
attendus et son README dans reference.

Les chemins sous /tmp servent aux essais temporaires.
Leur conservation dépend du nettoyage du système.
Utiliser un dossier personnel pour conserver durablement un jeu.

## Données volontairement invalides

Le jeu invalides est construit séparément du jeu valide.
Il contient les six cas suivants.

1. Service obligatoire absent.
2. Date non reconnue.
3. Niveau FATAL hors de la liste autorisée.
4. Statut HTTP 700 hors de l'intervalle 100 à 599.
5. Durée HTTP négative.
6. Durée SQL ajoutée à un événement HTTP.

Le fichier invalides/attendus.json indique les champs concernés
et les codes de diagnostic prévus.

Une durée négative enfreint aussi la grammaire numérique CSV/TXT.
Les tests de validation détaillés devront appliquer les règles
et l'ordre de diagnostic définis pour l'importeur.

Un événement ERROR ou CRITICAL peut être valide.
Un événement invalide enfreint une règle du contrat de données.

## Reproductibilité

Une même version du code, les mêmes paramètres, la même version
de Python, les mêmes dépendances et les mêmes fichiers de référence
permettent de reproduire les fichiers.

La graine 42 est une valeur d'exemple, librement choisie.
Elle n'est pas imposée par le sujet.

Pour vérifier la reproductibilité, exécuter la même commande dans
deux dossiers de sortie différents, puis les comparer.

```bash
diff -r -s /chemin/jeu-01 /chemin/jeu-02
```

Les fichiers correspondants doivent être identiques.
Changer la graine permet de produire un autre jeu synthétique.

## Jeu de référence

Le générateur réutilise les quatre événements de samples/valides.
Leurs résultats sont décrits dans samples/attendus.json.

Pour un seul fichier de référence importé, sans filtre excluant
des événements, les résultats attendus comprennent les valeurs suivantes.

| Indicateur | Résultat |
|---|---|
| Nombre d'événements | 4 |
| Familles | 1 HTTP, 1 application, 1 SQL et 1 métier |
| Temps HTTP moyen | 125 ms |
| Taux HTTP 5xx | 0 % |
| Requêtes SQL de plus de 1000 ms | 1 |
| Utilisateurs actifs distincts HTTP et métier | 2 |
| Événements ERROR ou CRITICAL | 1 |
| Utilisations de la fonctionnalité tasks | 1 |

Ces valeurs peuvent être vérifiées directement à partir des fichiers.
Le contrôle réalisé dans SCRUM-14 recalcule ces indicateurs sans
passer par une ingestion Elasticsearch.

## Vérifications réalisées

- Deux générations identiques avec la graine 42 donnent les mêmes fichiers.
- Les scénarios ont été exécutés avec 1000 événements chacun.
- Les événements CSV, JSONL et TXT sont équivalents pour chaque scénario.
- Chaque jeu invalide contient les mêmes six événements dans les trois formats.
- Les indicateurs du jeu de référence correspondent à attendus.json.

Résultats observés avec Faker 40.54.0, la graine 42 et la période
du 4 novembre 2026 de 08:00 à 09:00 UTC.

| Scénario | Événements | Erreurs | HTTP > 3000 ms | SQL > 1000 ms | Événements entre 08:27 et 08:33 |
|---|---:|---:|---:|---:|---:|
| normal | 1000 | 24 | 0 | 0 | 101 |
| erreurs | 1000 | 385 | 0 | 0 | 101 |
| lenteurs | 1000 | 22 | 237 | 245 | 104 |
| pic | 1000 | 26 | 0 | 0 | 815 |

## Références du projet

- [Modèle des logs](modele-logs.md)
- [Formats d'import](formats-import.md)
- [Corpus et résultats attendus](../samples/README.md)