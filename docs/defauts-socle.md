# Registre des défauts et écarts — SCRUM-27

## Règles de classement

- **P0** : bloque un parcours essentiel ou compromet les données.
- **P1** : écart important au socle ou résultat fonctionnel incorrect.
- **P2** : limitation, défaut documentaire ou contrôle complémentaire.
- **P3** : amélioration de confort.

Un point « à vérifier » n’est pas présenté comme un bug confirmé.
Une justification technique explique un écart ; elle ne prouve pas
à elle seule la conformité à l’énoncé.

## Registre initial

| ID | Nature et priorité | Constat | Action et critère de clôture | État |
|---|---|---|---|---|
| E-01 | Conformité — P1 | L’énoncé demande deux configurations Logstash CSV et JSON ; le projet utilise un pipeline de production commun avec parsing par format. | Examiner une séparation conforme, en préservant validation, normalisation et suivi ; valider CSV, JSONL et TXT après modification. Ne pas compter la configuration de test comme second pipeline de production. | Écart confirmé |
| E-02 | Conformité — P1 | Les graphiques de synthèse utilisent du SVG natif, alors que le socle demande Chart.js ou Plotly. | Prévoir l’alignement sur la bibliothèque demandée ; conserver les fonctions de lecture des valeurs et l’accessibilité. | Écart confirmé |
| E-03 | Convention métier — P2 | Le cadrage retient les utilisateurs distincts sur une période ; le scénario évoque aussi les utilisateurs simultanés. | Garder les libellés exacts, documenter la définition et ne pas revendiquer une mesure de simultanéité. | Limitation documentée |
| E-04 | Conformité — P2 | L’export contient timeRestore=false et aucun refreshInterval. Le rafraîchissement automatique des données n’est pas démontré. | Configurer et vérifier le rafraîchissement Kibana, puis actualiser l’export. | Ouvert — preuve insuffisante |
| E-05 | Configuration — P2 | Les variables Kibana ont été ajoutées à .env.example et leur rôle expliqué dans docs/kibana.md. | Vérifier les liens et la cohérence documentaire avant clôture. | Documentation et liens vérifiés |
| E-06 | Documentation — P2 | Le README et le guide décrivent désormais les modules réalisés, six pages, six services et le nouvel emplacement de Swagger. | Relecture finale et vérification des liens. | Corrigé — liens vérifiés |
| E-07 | Interface — P2 | La page Kibana est utilisable à 324 et 720 px. Les six templates possèdent une note latérale, mais aucun footer ; la note est masquée sur mobile. Le contrôle console a identifié des erreurs de profil Kibana ; voir E-15. | Ajouter un pied de page avec les informations du projet et terminer le contrôle console. | Footer absent ; console partiellement conforme |
| E-08 | Rapport — P2 | Les sections des modules complètent maintenant la partie ingestion historique. | Relecture finale ; intégrer ces sources au rapport pédagogique final. | Sections actualisées |
| E-09 | Preuves — P2 | Les bilans d’ingestion récents sont versionnables ; les contrôles HTTP/HTML et les captures récentes de l’intégration iframe restent à joindre. | Ajouter un bilan reproductible et les captures récentes, sans altérer les preuves historiques. | Ouvert |
| E-10 | Limitation — P2 | Sur la période vide, Kibana affiche N/A pour les utilisateurs, alors que le calcul exact donne zéro. | Conserver l’explication dans le guide et le rapport ; distinguer absence de résultat et échec du service. | Documenté |
| E-11 | Limitation — P2 | Le compteur Unique Count de Kibana peut être approximatif. | Maintenir la limite documentée et la comparaison avec le jeu de référence. | Documenté |
| E-12 | Infrastructure — P2 | Elasticsearch est yellow sur le cluster à un seul nœud ; les données primaires restent disponibles. | Conserver le diagnostic déjà retenu et vérifier la disponibilité des index applicatifs. Ne pas présenter le cluster comme hautement disponible. | Limitation connue |
| E-13 | Validation — P2 | Les preuves de persistance, de non-régression et de protection de l’affichage doivent être rattachées à cette revue. | Retrouver les contrôles existants, préciser leur version et rejouer les scénarios nécessaires. | À vérifier |
| E-14 | Validation — P2 | Le validateur historique ignorait l’évolution des champs dérivés de recherche et signalait trois différences sur les fichiers valides. | Contrôle explicite des champs dérivés ajouté ; nouvelle exécution : 12/12 réussis. Bilans initiaux conservés. | Corrigé et vérifié |

| E-15 | Interface Kibana — P2 | Les appels au profil utilisateur renvoient 404 dans l’installation sans authentification et une promesse non gérée apparaît. | Étudier une correction ciblée ; vérifier ensuite la console et les parcours du dashboard. | Limitation ouverte ; diagnostic ci-dessous |
| E-16 | Configuration Kibana — P2 | Streams répondait HTTP 500 faute de clé de chiffrement persistante. | Clé configurée ; réponse HTTP 200 vérifiée après redémarrage. | Corrigé et vérifié |

Aucun défaut P0 n’a été constaté dans les contrôles effectués jusqu’ici.
Cette observation ne vaut pas validation des parcours encore non exécutés.

## Décisions et suivi

Les corrections, résultats et décisions seront ajoutés au fil de la revue.
La clôture SCRUM-27 exigera une matrice à jour, des parcours démontrables,
un registre priorisé et des documents cohérents avec le logiciel.
Elle ne doit pas être confondue avec une déclaration automatique
de conformité intégrale à toutes les formulations de l’énoncé.

## Console Kibana — contrôle du 27 novembre 2026

- **Corrigé et vérifié** : la route `/api/streams/_status` répondait
  HTTP 500 faute de clé de chiffrement. Après configuration persistante
  de `XPACK_ENCRYPTEDSAVEDOBJECTS_ENCRYPTIONKEY`, elle répond HTTP 200
  avec `{"enabled":false}`.
- **P2 — limitation ouverte** : les appels à
  `/internal/security/user_profile` répondent HTTP 404 et provoquent
  une promesse non gérée dans l’interface Kibana 8.19.0.
  Elasticsearch fonctionne avec la sécurité désactivée.
  Le code installé de `get_current.js` renvoie explicitement 404
  en l’absence d’utilisateur authentifié ou de profil.
  Aucun blocage des parcours de dashboard observés ; le critère
  « absence d’erreurs JavaScript » reste partiellement couvert.
  Une résolution doit être étudiée dans une évolution ciblée de Kibana.
- Le blocage inline accompagné du message « expected » correspond au
  contrôle CSP de Kibana. Ne pas assouplir la CSP pour supprimer ce message.
