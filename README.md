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

L’analyse et la conception initiales sont terminées.
L’environnement Docker comprend sept services opérationnels :
Flask, Elasticsearch, Logstash, Kibana, MongoDB, Redis et le tracker.

La page d’accueil Flask, l’accès à Kibana, les communications
entre services et la persistance des données ont été vérifiés.

Les fonctionnalités d’import, de recherche, de suivi des imports
et les indicateurs métier seront développés dans les prochains tickets.

## Organisation et documentation

Le suivi des tâches est effectué dans Jira.

Les documents d’analyse, d’architecture et les guides
seront ajoutés progressivement dans le dossier docs/.

Chaque fonctionnalité sera accompagnée de sa documentation
et des vérifications correspondantes.

## Documentation

- [Cadrage du projet](docs/cadrage.md)
- [Modèle de logs et correspondances ECS](docs/modele-logs.md)
- [Formats d’import et règles de validation](docs/formats-import.md)
- [Exemples de logs et résultats attendus](samples/README.md)
- [Démarrer l'environnement Docker](docs/docker.md)