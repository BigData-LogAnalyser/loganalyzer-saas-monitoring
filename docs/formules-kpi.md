# SCRUM-23 — Formules des KPI du dashboard

## Sources et conventions

Les événements sont lus dans Elasticsearch, dans les index
`loganalyzer-logs-*`. Le nombre de fichiers provient de la collection
MongoDB `imports`, dans la base configurée par `MONGODB_DATABASE`.

Les calculs portent sur les documents indexés. Plusieurs imports du même
contenu peuvent donc augmenter les compteurs. Aucune déduplication métier
entre imports n’est appliquée.

Les horodatages sont stockés et retournés par l’API en UTC.
Le fuseau d’affichage et de définition du jour courant est `Africa/Tunis`.

Une période est un intervalle [début inclus, fin exclue[.
Le champ utilisé est `@timestamp`, date de l’événement.

Sans dates, la période couvre les 24 dernières heures.
Avec une fin seule, elle couvre les 24 heures précédant cette fin.
Avec un début seul, elle va de ce début à l’instant du calcul.

Les filtres exacts de service et d’organisation sont appliqués avant
les agrégations sur les logs.

## Les quatre cartes

| Carte | Formule | Périmètre |
|---|---|---|
| Total des logs | Nombre de documents indexés | Toutes les dates ; filtres service et organisation |
| Logs du jour | Nombre de documents dont @timestamp appartient au jour courant dans Africa/Tunis | Minuit local inclus à minuit local suivant exclu ; filtres service et organisation |
| Logs ERROR / CRITICAL | Nombre de documents dont log.level appartient à ERROR ou CRITICAL | Période sélectionnée ; filtres service et organisation |
| Fichiers importés | Nombre de documents imports dont confirmed_at est une date BSON | Toutes les dates et tous les statuts ; indépendant des filtres sur les logs |

Une importation confirmée compte même si son traitement est partiel ou
en échec. Un aperçu non confirmé ou annulé ne compte pas.

Le compteur des fichiers ne peut pas être déduit des seuls documents
Elasticsearch : un import confirmé peut ne produire aucun log indexé.

## Temps de réponse HTTP moyen par endpoint

Population : événements `event.dataset = saas.http`, avec un endpoint
`url.path` renseigné et une durée `event.duration` positive ou nulle.

Moyenne en ms = somme des durées admissibles en ns /
nombre d’événements mesurés / 1 000 000.

Le regroupement utilise le chemin réel de l’endpoint.
Les chemins contenant des identifiants ne sont pas regroupés
automatiquement sous une route normalisée.

Une durée absente est exclue de la moyenne.
Une liste vide est affichée comme N/D dans l’interface.

Exemple vérifié : 100, 200 et 300 ms donnent une moyenne de 200 ms.

## Taux de réponses HTTP 5xx par service

Population : événements `event.dataset = saas.http`, avec un code
`http.response.status_code` compris entre 100 et 599, regroupés par service.

Taux en pourcentage = 100 × nombre de réponses de statut 500 à 599 /
nombre de réponses de statut 100 à 599.

Un service sans réponse admissible ne possède pas de taux calculable.
L’interface affiche N/D lorsque la liste est vide.

Ce calcul est indépendant du niveau du log.
Un événement applicatif ERROR ne constitue pas nécessairement une
réponse HTTP 5xx.

Exemple vérifié : deux réponses 5xx sur quatre réponses donnent 50 %.

## Requêtes SQL lentes

Population : événements `event.dataset = saas.database`.

Une exécution est lente si :

event.duration / 1 000 000 > SQL_SLOW_THRESHOLD_MS.

Le seuil par défaut est de 1 000 ms.
Il est configurable par la variable d’environnement
`SQL_SLOW_THRESHOLD_MS` du service webapp.

Le dashboard affiche le nombre total d’exécutions dépassant le seuil
et les dix exécutions les plus lentes au maximum.

Le classement est décroissant par durée, puis par date.
L’identifiant d’événement départage les égalités restantes.

Exemple vérifié : pour 800, 1 000 et 1 200 ms, seule la dernière exécution
dépasse strictement le seuil de 1 000 ms.

## Utilisateurs actifs

Population : événements des familles `saas.http` ou `saas.business`,
avec un champ `user.id` présent et non vide.

Nombre d’utilisateurs actifs = nombre exact de valeurs user.id distinctes
dans la période et après application des filtres.

Les groupes sont parcourus avec une agrégation composite Elasticsearch.
Le calcul n’utilise pas une estimation de cardinalité.

L’identifiant user.id est supposé identifier l’utilisateur dans le jeu
simulé. Le calcul ne constitue pas une mesure des connexions simultanées.

Exemple vérifié : plusieurs événements de U1, U2 et U3 donnent trois
utilisateurs actifs.

## Utilisation des fonctionnalités

Population : événements `event.dataset = saas.business`, correspondant
aux couples action/fonctionnalité admissibles :

| Action | Fonctionnalité |
|---|---|
| project-viewed | projects |
| task-created | tasks |
| task-updated | tasks |
| report-generated | reports |

Nombre d’utilisations d’une fonctionnalité = nombre de ses événements
métier admissibles dans la période.

Les résultats sont classés par nombre d’utilisations décroissant,
puis par nom de fonctionnalité.

Les fonctionnalités sans événement admissible ne sont pas retournées.

## Vérification du jeu de référence

Le contrôle utilise les quatre événements d’un seul import existant,
avec une restriction de lecture propre au test.

| Indicateur | Valeur vérifiée |
|---|---|
| Nombre de logs | 4 |
| Logs ERROR / CRITICAL | 1 |
| Moyenne HTTP | 125 ms |
| Taux HTTP 5xx | 0 % sur une réponse |
| Exécutions SQL > 1 000 ms | 1, à 1 200 ms |
| Utilisateurs actifs | 2 |
| Utilisations de tasks | 1 |

L’horloge du test est fixée au 4 novembre 2026.
Les quatre événements appartiennent à cette journée dans Africa/Tunis.

[Résultats du jeu de référence](validation-dashboard/kpi-reference.json)

[Cas limites sur Elasticsearch](validation-dashboard/bilan-cas-limites.json)

## Cohérence et limites

Une absence d’événement produit un compteur nul.
Une moyenne ou un taux sans population admissible est présenté comme N/D.

Lorsqu’aucun cache valide n’est disponible, une panne MongoDB,
une erreur Elasticsearch, un dépassement du délai ou un résultat
Elasticsearch incomplet produit HTTP 503.
L’API ne retourne pas de chiffres partiels.
Une réponse complète déjà en cache peut être réutilisée jusqu’à
son expiration, en conservant sa date de calcul initiale.

Les agrégations composites sont parcourues par pages de 500 groupes,
avec une limite de 200 requêtes par parcours.
Le dépassement de cette limite interrompt le calcul en HTTP 503.

Les calculs utilisent plusieurs requêtes successives et les deux bases.
Ils ne constituent pas un instantané transactionnel commun.
Les validations chiffrées sont réalisées sur des données stables.

[Contrat de fraîcheur du cache Redis](cache-redis.md)
