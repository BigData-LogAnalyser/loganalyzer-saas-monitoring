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

## Architecture

- Flask : interface web et API.
- Logstash : parsing et normalisation des logs.
- Elasticsearch : indexation, recherche et agrégations.
- Kibana : visualisations et dashboards.
- MongoDB : métadonnées des imports et historique.
- Redis : cache des indicateurs.
- Docker Compose : déploiement des services.

## État du projet

Les modules d’import, de suivi, de recherche, de détail et d’export CSV,
de consultation des fichiers, d’historique, de KPI et de cache Redis
sont implémentés et disposent de validations documentées.

L’interface comporte six écrans, dont une page intégrant le dashboard
Kibana. Swagger est accessible depuis l’en-tête du tableau de bord
et s’ouvre dans un nouvel onglet.

L’environnement Docker comprend sept services :
Flask, Elasticsearch, Logstash, Kibana, MongoDB, Redis et le tracker.
Le tableau de bord surveille six services ; le tracker dispose
de son contrôle de santé Docker.

SCRUM-27 porte sur la revue du socle, la traçabilité des preuves,
les parcours de démonstration et les écarts restants.
L’implémentation des modules ne signifie pas que tous les critères
de l’énoncé sont déjà déclarés conformes.

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
- [Générer les logs synthétiques](docs/generateur.md)
- [Importer et prévisualiser des logs](docs/import.md)
- [Ingestion et normalisation des logs](docs/ingestion.md)
- [Suivi des imports](docs/suivi-imports.md)

- [Rapport technique — ingestion](docs/rapport.md)

- [Recherche et filtres : API, vérifications et limites](docs/recherche.md)

[Détail des logs et export CSV — SCRUM-20](docs/detail-export.md)

[Consultation des fichiers importés — SCRUM-21](docs/fichiers.md)

[Historique des recherches — SCRUM-22](docs/historique-recherches.md)

[Dashboard SaaS — SCRUM-23](docs/dashboard.md)

[Formules des KPI](docs/formules-kpi.md)

[Cache Redis des KPI — SCRUM-24](docs/cache-redis.md)

[Guide utilisateur illustré](docs/guide-utilisateur.md)

[Dashboard Kibana : configuration, lecture et validation](docs/kibana.md)

- [Validation du socle et matrice de couverture](docs/validation-socle.md)

- [Parcours de démonstration](docs/parcours-demonstration.md)

- [Défauts et écarts priorisés](docs/defauts-socle.md)
