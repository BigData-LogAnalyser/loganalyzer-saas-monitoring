# Cadrage du projet LogAnalyzer

Projet Big Data — ITBS  
Ticket : SCRUM-8  
Version : 1.0 — 4 novembre 2026  
Statut : proposé pour revue

## 1. Contexte, besoin et solution

Le projet simule le monitoring d’un SaaS fictif de gestion de projets et de tâches. Ce SaaS produit des traces lors de la consultation de projets, de la création ou de la modification de tâches, de la génération de rapports et des échanges avec sa base de données.

La situation de référence est la consultation manuelle de fichiers de logs dispersés et hétérogènes. Elle rend difficile la recherche d’un incident, la comparaison des événements et le calcul d’indicateurs communs. Il s’agit d’un scénario universitaire simulé, et non d’un audit d’entreprise.

LogAnalyzer est l’application web proposée pour importer, normaliser, indexer, rechercher et visualiser ces logs. Le SaaS métier lui-même ne sera pas développé : son activité sera représentée par un générateur de données synthétiques.

## 2. Utilisateurs

Un seul acteur fonctionnel, « Utilisateur », représente trois profils d’usage :

| Profil | Objectif principal |
|---|---|
| Développeur | Retrouver et comprendre les erreurs applicatives. |
| Équipe DevOps | Examiner les performances et suivre le traitement des fichiers. |
| Responsable technique | Consulter les volumes, tendances et indicateurs d’utilisation. |

Ces profils ne constituent pas des rôles d’autorisation distincts dans le socle initial. L’authentification et la gestion de droits ne sont pas incluses dans ce socle.

## 3. Sources, données et collecte

| Source simulée | Exemples | Exploitation |
|---|---|---|
| Accès HTTP | Requête vers une route, méthode, statut et durée | Trafic, erreurs HTTP et latence |
| Événements applicatifs et erreurs | Création de tâche, échec de rapport, erreur technique | Diagnostic et comptage des erreurs |
| Exécutions SQL | Type de requête et durée d’exécution | Identification des requêtes lentes |
| Utilisation des fonctionnalités | Consultation de projet, gestion de tâche, génération de rapport | Adoption des fonctionnalités et utilisateurs actifs |

Toutes les données seront synthétiques. Les identifiants d’utilisateurs et d’organisations seront fictifs. Le générateur produira des scénarios normaux, des erreurs et des lenteurs, ainsi que des jeux de référence permettant de vérifier les résultats.

La collecte initiale repose uniquement sur l’import manuel de fichiers depuis l’interface web. Elle ne comporte ni connexion aux logs privés de plateformes externes, ni agent de collecte installé sur une application réelle.

### Formats acceptés

- **CSV** : en-têtes et colonnes conformes à un contrat d’entrée documenté.
- **JSON** : profil JSON Lines, avec un objet par ligne, pour le socle retenu.
- **TXT** : une ligne par événement, suivant une structure documentée.

L’extension seule ne suffit pas à rendre un fichier compatible. Les structures exactes, types et correspondances ECS seront définis dans SCRUM-10. Les exemples des maquettes sont illustratifs et ne constituent pas le contrat d’import.

Le parcours prévu est : transfert, contrôles initiaux, aperçu de dix événements au maximum, confirmation, ingestion et suivi du bilan. Un aperçu valide ne garantit pas la validité de tout le fichier.

## 4. Conventions de calcul des indicateurs

Les règles suivantes constituent les décisions de cadrage proposées pour l’implémentation et les tests.

- Les horodatages sont stockés en UTC. Le fuseau d’affichage et des indicateurs journaliers est **Africa/Tunis**.
- Une période est un intervalle **[début inclus, fin exclue[**. Un événement est rattaché à la période par sa date d’événement, et non par la date d’import.
- Par défaut, les graphiques d’analyse portent sur les **24 dernières heures**. Les exceptions des cartes de synthèse sont définies ci-dessous.
- Les filtres d’analyse sont la période, le service et, lorsqu’il est renseigné, l’identifiant d’organisation. Ils s’appliquent avant les agrégations.
- Une valeur absente n’est pas remplacée par zéro. Elle est exclue uniquement du calcul qui exige ce champ. Une moyenne ou un taux sans population admissible affiche « N/D ».
- Un événement contenant les champs nécessaires est compté une fois dans chaque calcul auquel il appartient. Le comptage porte sur les documents indexés ; la déduplication métier entre plusieurs imports n’est pas incluse dans le socle.
- Les durées sont affichées en millisecondes. Si le stockage normalisé utilise des nanosecondes, la conversion est : durée en ms = durée en ns / 1 000 000.

### 4.1. Les quatre cartes de synthèse

| Carte | Définition et formule | Périmètre et filtres | Unité |
|---|---|---|---|
| Total des logs indexés | Nombre de documents de logs présents dans Elasticsearch | Toutes les dates ; filtres service et organisation si sélectionnés | Événements |
| Logs du jour | Nombre de documents dont la date d’événement appartient au jour courant dans Africa/Tunis | De 00:00 locale au prochain 00:00 local ; filtres service et organisation | Événements |
| Logs en erreur | Nombre de documents dont le niveau normalisé est ERROR ou CRITICAL | Période sélectionnée ; filtres service et organisation | Événements |
| Fichiers importés | Nombre d’imports confirmés enregistrés dans MongoDB, tous statuts confondus | Toutes les dates ; compteur global, indépendant des filtres sur les logs | Fichiers |

Le niveau CRITICAL est inclus dans la carte « Logs en erreur » et peut être détaillé séparément sans être additionné deux fois. Les transferts annulés ou non confirmés ne comptent pas comme fichiers importés. Le périmètre propre à chaque carte sera indiqué dans son libellé ou son aide pour éviter de laisser croire que toutes suivent le même filtre temporel.

### 4.2. Indicateurs d’analyse SaaS

| Indicateur | Population et formule | Filtres et regroupement | Unité |
|---|---|---|---|
| Temps de réponse HTTP moyen par endpoint | Somme des durées HTTP valides / nombre de requêtes HTTP possédant une durée valide | Période, service, organisation ; regroupement par endpoint | Millisecondes |
| Taux d’erreurs HTTP 5xx | 100 × nombre de réponses de statut 500 à 599 / nombre de réponses HTTP avec un statut valide de 100 à 599 | Période, service, organisation ; endpoint si nécessaire | Pourcentage |
| Évolution des erreurs HTTP 5xx | Nombre de réponses HTTP 5xx dans chaque intervalle de temps | Période, service, organisation ; pas de temps indiqué sur le graphique | Réponses par intervalle |
| Requêtes SQL lentes | Exécutions SQL dont la durée est strictement supérieure à 1 000 ms ; classement décroissant par durée | Période, service, organisation ; dix exécutions les plus lentes | Millisecondes et nombre d’exécutions |
| Utilisateurs actifs | Nombre d’identifiants utilisateur distincts ayant produit au moins un événement HTTP ou métier dans la période | Période, service, organisation ; identifiant présent requis | Utilisateurs distincts |
| Fonctionnalités les plus utilisées | Nombre d’événements métier d’utilisation par fonctionnalité | Période, service, organisation ; fonctionnalité renseignée ; classement décroissant | Utilisations |

Le seuil SQL de 1 000 ms est une convention de démonstration configurable, pas une norme universelle. Les données synthétiques devront permettre de vérifier des valeurs inférieures, égales et supérieures au seuil.

Un événement métier d’utilisation représente une action utilisateur sur une fonctionnalité. Les traces techniques intermédiaires ne sont pas comptées comme autant d’utilisations. Le générateur et le dictionnaire de données préciseront les actions admissibles. Le comptage distinct des utilisateurs devra être vérifié sur un jeu connu ; toute approximation utilisée par l’implémentation sera documentée.

Le nombre de logs ERROR/CRITICAL et le nombre de réponses HTTP 5xx sont deux mesures différentes : le premier repose sur le niveau du log, le second sur le statut HTTP.

### 4.3. Exemples de vérification

- Pour 200 réponses HTTP valides dont 10 réponses 5xx, le taux attendu est de **5 %**.
- Pour trois durées HTTP de 100, 200 et 300 ms sur un même endpoint, la moyenne attendue est de **200 ms**.
- Pour les identifiants utilisateur U1, U1 et U2 dans la population admissible, le nombre attendu est de **2 utilisateurs actifs**.
- Pour des exécutions SQL de 800, 1 000 et 1 200 ms, une seule exécution dépasse le seuil retenu.
- Pour 12 logs ERROR et 3 logs CRITICAL, la carte des erreurs affiche **15**, dont 3 CRITICAL.
- Pour deux imports confirmés et un transfert annulé, la carte des fichiers importés affiche **2**.
- Pour tester les logs du jour, inclure des événements juste avant, exactement à et juste après minuit dans Africa/Tunis.

## 5. Périmètre obligatoire

La liste suivante sert de référence de vérification du socle :

- [ ] Générer des logs synthétiques reproductibles dans les formats retenus.
- [ ] Importer manuellement un fichier CSV, JSON Lines ou TXT conforme au contrat.
- [ ] Contrôler le fichier et prévisualiser les premiers événements avant confirmation.
- [ ] Parser et normaliser les événements selon le modèle ECS retenu.
- [ ] Indexer les logs valides dans Elasticsearch et identifier les rejets.
- [ ] Conserver dans MongoDB les métadonnées et le bilan des imports.
- [ ] Consulter les fichiers importés et suivre leurs états et compteurs.
- [ ] Rechercher les logs, combiner des filtres et consulter les résultats paginés.
- [ ] Consulter le détail d’un log et exporter les résultats en CSV.
- [ ] Enregistrer et consulter l’historique des recherches.
- [ ] Afficher les quatre cartes et les indicateurs SaaS définis dans ce document.
- [ ] Mettre en cache les indicateurs avec Redis.
- [ ] Créer un dashboard Kibana : latence HTTP moyenne par endpoint, évolution des erreurs 5xx et utilisateurs actifs.
- [ ] Proposer une interface utilisable sur ordinateur et mobile.
- [ ] Fournir un environnement Docker Compose, la documentation et les vérifications nécessaires à la démonstration.

Les cases décrivent les fonctionnalités à vérifier pendant le développement ; elles ne déclarent pas leur réalisation actuelle.

## 6. Extensions et exclusions

### Extensions proposées, non engagées dans le socle

- **Temps réel** : alimentation continue et actualisation par WebSocket.
- **CI/CD avancé** : contrôles qualité automatisés, publication des images, déploiement staging et rollback.

Leur réalisation dépendra du périmètre retenu et de la charge disponible. Git, les tests et la documentation restent nécessaires sans le module CI/CD avancé.

### Hors périmètre initial

- Développement du SaaS métier de gestion de projets et de tâches.
- Collecte des données privées de plateformes tierces.
- Prise en charge automatique de tous les formats de logs existants.
- Authentification, rôles d’accès et isolation multi-tenant.
- Détection d’anomalies par machine learning et alerting avancé.
- Haute disponibilité et exploitation distribuée en production.

### Identifiant d’organisation

L’identifiant d’organisation sert uniquement à filtrer et analyser les données synthétiques. Il ne garantit aucune isolation des accès. Sa présence ne constitue ni un contrôle d’autorisation ni une architecture multi-tenant sécurisée.

## 7. Besoins non fonctionnels essentiels

| Besoin | Exigence minimale | Vérification prévue |
|---|---|---|
| Fiabilité | Cohérence entre événements attendus, indexés et rejetés ; bilan vérifié avant clôture d’un import | Jeux de référence avec résultats connus |
| Performance | Pagination des résultats et cache des indicateurs ; objectifs chiffrés à fixer avant les tests | Mesures sur un volume connu, avec et sans cache |
| Protection des entrées | Contrôle des fichiers et paramètres ; affichage des logs comme texte non exécutable | Fichiers invalides et messages contenant du HTML |
| Persistance | Conservation des logs et métadonnées après redémarrage normal | Redémarrage des conteneurs et comparaison des données |
| Facilité d’utilisation | Navigation claire et affichage adapté à l’ordinateur et au mobile | Démonstration des parcours d’import et de recherche |

Ces exigences sont des objectifs de réalisation. D’autres pourront être ajoutées si le développement révèle un besoin concret et justifiable.

## 8. Revue et rattachement au dépôt

Ce document couvre le scénario, les profils, les sources synthétiques, les formats, l’import manuel, les quatre cartes, les indicateurs détaillés, le fuseau horaire et les limites du périmètre.

Avant de clôturer SCRUM-8, relire les conventions proposées : seuil SQL, définition d’utilisateur actif, profil JSON Lines et périmètre propre à chaque carte. Leur approbation valide le cadrage, pas l’implémentation.

Livrable cible : `docs/cadrage.md`. Le document pourra être intégré au dépôt après SCRUM-12. SCRUM-10 détaillera les champs, types et correspondances ECS, sans être une dépendance préalable à la rédaction du cadrage.
