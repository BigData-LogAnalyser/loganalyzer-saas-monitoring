# Parcours de démonstration — LogAnalyzer

## Préparation

Démarrer les services selon le guide Docker.
Ouvrir le tableau de bord et vérifier les six services.
Elasticsearch peut être dégradé sur ce cluster à un seul nœud.

Les étapes ci-dessous constituent un support de démonstration.
Elles ne déclarent pas une nouvelle exécution manuelle de tous les parcours.

Les totaux globaux évoluent après les imports de test.
Comparer les compteurs d’un import identifié, pas un total global figé.

## 1. Import valide et suivi

1. Ouvrir « Importer des logs ».
2. Sélectionner `samples/valides/logs.csv`.
3. Montrer l’aperçu et les champs contrôlés.
4. Confirmer une seule fois et suivre le traitement.
5. Montrer le résultat : 4 attendus, 4 indexés, 0 rejeté, TERMINE.
6. Retrouver cet import dans « Fichiers importés ».

Le parcours est également disponible avec les fichiers JSONL et TXT.
Une nouvelle démonstration confirmée crée un nouvel import.

## 2. Refus d’un fichier invalide

1. Sélectionner `samples/invalides/json-malforme.jsonl`.
2. Montrer le diagnostic JSON_SYNTAX.
3. Constater que la confirmation n’est pas proposée.
4. Expliquer que ce fichier n’est pas envoyé au traitement.

## 3. Import partiel et diagnostics

1. Sélectionner `samples/mixte.jsonl`.
2. Montrer que les dix premiers événements permettent la confirmation.
3. Confirmer puis attendre PARTIEL.
4. Montrer 12 attendus, 10 indexés et 2 rejetés.
5. Consulter les diagnostics des lignes 11 et 12 et leur contenu original.

Une progression de 100 % signifie que les événements sont résolus ;
elle ne signifie pas que tous sont indexés.

## 4. Recherche, détail et export

1. Dans « Fichiers importés », sélectionner un import valide.
2. Cliquer sur « Voir les logs » pour appliquer son identifiant.
3. Vérifier les quatre résultats de cet import.
4. Montrer le tri et un filtre de niveau.
5. Ouvrir le détail d’un événement et montrer les champs puis le JSON.
6. Exporter les résultats en CSV.
7. Vérifier que l’export suit les filtres affichés.

La pagination de 50 logs peut être montrée sur une recherche plus large.
L’export couvre toutes les pages dans ses limites documentées.

## 5. Historique

1. Effectuer une recherche identifiable.
2. Ouvrir l’historique et retrouver ses critères.
3. Cliquer sur « Relancer ».
4. Montrer que les critères sont réappliqués.

L’historique est commun à l’application.
Le nombre mémorisé correspond à l’exécution passée.

## 6. KPI et cache Redis

1. Ouvrir le tableau de bord et choisir une période.
2. Expliquer le périmètre propre à chacune des quatre cartes.
3. Montrer les indicateurs SaaS, leurs unités et les filtres.
4. Présenter les preuves MISS/HIT et d’expiration conservées
   dans la documentation du cache.

Les utilisateurs actifs sont distincts sur une période,
pas des connexions simultanées.
Le cache peut conserver un calcul pendant sa durée de vie.

## 7. Kibana

1. Ouvrir « Visualisations Kibana ».
2. Sélectionner le 26 novembre 2026 en heure de Tunis.
3. Montrer 2 utilisateurs, 2 erreurs HTTP 5xx pour task-service
   et le point HTTP à environ 458,33 ms pour /api/tasks.
4. Sélectionner le 25 novembre : graphiques sans résultat et carte N/A.
5. Montrer l’ouverture directe dans Kibana.
6. Présenter l’export NDJSON et la restauration déjà validée.

La période Kibana est indépendante du tableau de bord Flask.

## 8. Interface et documentation

1. Montrer la navigation sur ordinateur puis à 720 et 324 px.
2. Vérifier notamment la nouvelle page Kibana et l’accès à ses commandes.
3. Ouvrir puis fermer une popup au bouton et avec Échap.
4. Ouvrir Swagger depuis le tableau de bord dans un nouvel onglet.
5. Présenter le guide, la matrice de couverture et les écarts connus.

## Preuves et portée

- [Matrice de couverture](validation-socle.md)
- [Registre des écarts](defauts-socle.md)
- [Guide utilisateur](guide-utilisateur.md)
- [Validation et configuration Kibana](kibana.md)
- [Validation du cache](cache-redis.md)

Le scénario HTTP 503 est démontrable par son bilan automatisé.
Il n’est pas nécessaire d’arrêter Logstash pendant la soutenance.
