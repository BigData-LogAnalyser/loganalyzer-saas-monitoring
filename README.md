# LogAnalyzer — Monitoring de logs SaaS

Projet universitaire Big Data réalisé à IT Business School.

## Présentation

LogAnalyzer est une plateforme web destinée à centraliser,
rechercher et analyser des logs synthétiques représentant
l’activité d’une application SaaS.

## Objectifs

- Importer des fichiers CSV, JSON et TXT.
- Valider les fichiers et prévisualiser leur contenu.
- Normaliser les événements selon un modèle fondé sur ECS.
- Indexer et rechercher les logs dans Elasticsearch.
- Suivre les imports et conserver l’historique des recherches.
- Consulter des indicateurs et des visualisations.

## Architecture prévue

- Flask : interface web et API.
- Logstash : parsing et normalisation des logs.
- Elasticsearch : indexation, recherche et agrégations.
- Kibana : visualisations et dashboards.
- MongoDB : métadonnées des imports et historique.
- Redis : cache des indicateurs.
- Docker Compose : déploiement des services.

## État du projet

Le projet est en phase d’analyse et de conception.
L’application n’est pas encore disponible pour exécution.

Le cadrage SaaS est défini. Les maquettes et diagrammes
sont en cours de consolidation dans la documentation.

## Organisation et documentation

Le suivi des tâches est effectué dans Jira.

Les documents d’analyse, d’architecture et les guides
seront ajoutés progressivement dans le dossier docs/.

Chaque fonctionnalité sera accompagnée de sa documentation
et des vérifications correspondantes.
