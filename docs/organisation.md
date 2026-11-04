# Organisation du dépôt et conventions

## Organisation des dossiers

| Dossier | Rôle |
|---|---|
| docs/ | Cadrage, contrat de données et documentation technique |
| samples/ | Exemples synthétiques valides, invalides et résultats attendus |
| app/ | Application Flask et API |
| app/templates/ | Pages HTML avec Jinja2 |
| app/static/ | Fichiers CSS, JavaScript et ressources de l'interface |
| generator/ | Générateur de logs synthétiques |
| tracker/ | Suivi des imports et de leur progression |
| logstash/pipeline/ | Configuration des pipelines d'ingestion |
| elasticsearch/ | Mappings et configuration des index |
| kibana/ | Configuration et exports des visualisations |
| tests/ | Tests automatisés |

Les dossiers applicatifs seront alimentés au fil de l'implémentation.
Git ne conserve pas les dossiers vides.

L'environnement Python `.venv/` reste local et n'est pas versionné.

## Branches

La branche `main` contient les changements vérifiés et intégrés.

Chaque ticket de développement utilise une branche dédiée,
nommée selon la convention :

`SCRUM-XX-description-courte`

Exemple : `SCRUM-11-preparation-environnement`.

## Commits

Chaque commit commence par la clé du ticket Jira concerné,
suivie d'une description précise.

Exemple :

`SCRUM-11 Documenter l'environnement et l'organisation du dépôt`

Un commit regroupe des changements cohérents liés au ticket.

Avant chaque commit, vérifier les fichiers ajoutés et leur contenu.
Les secrets, le fichier `.env`, l'environnement virtuel et les
données générées pendant l'exécution ne doivent pas être versionnés.

Les exemples synthétiques du dossier `samples/` sont versionnés
pour documenter et vérifier le contrat de données.

## Intégration des changements

1. Réaliser les modifications sur la branche du ticket.
2. Vérifier les changements et effectuer les contrôles adaptés.
3. Créer un commit contenant la clé Jira.
4. Publier la branche sur GitHub.
5. Ouvrir une pull request vers `main`, avec la clé Jira dans le titre.
6. Relire les modifications et vérifier les contrôles avant la fusion.

## Liaison GitHub–Jira

L'intégration GitHub–Jira doit être configurée pour le dépôt.

La clé du ticket doit figurer dans le nom de la branche,
le message du commit ou le titre de la pull request.

La liaison est considérée comme vérifiée lorsqu'une branche,
un commit ou une pull request apparaît dans la section
Développement du ticket Jira correspondant.

La présence de la clé dans un nom ne suffit pas, à elle seule,
à prouver que l'intégration fonctionne.