# Validation du socle fonctionnel — SCRUM-27

## Version et portée

Début de revue : 27 novembre 2026.
Version de départ : `89267d324fc37497a738b18920bfb9547bf2530b`.

Références : énoncé Mini-Projet ELK, section V.1, pages 7 à 10 ;
scénario SaaS page 4 ; intégration frontend et Kibana pages 21 à 23 ;
cadrage du projet dans [cadrage.md](cadrage.md).

La revue couvre import, suivi, recherche, détail, export, historique,
KPI, Redis, interface, Kibana et leurs dépendances techniques.

Cette première matrice est un état de revue, pas une déclaration
de conformité complète.

## Signification des statuts

- **Actuel** : contrôle effectué pendant cette revue.
- **Historique** : validation documentée dans un ticket précédent ;
  la preuve doit être relue et la portée de non-régression précisée.
- **À vérifier** : preuve ou contrôle encore insuffisant.
- **Écart** : différence identifiée entre l’énoncé et la réalisation.
- **Convention** : choix du cadrage, à présenter explicitement.

Une capture prouve un état visible ; elle ne prouve pas à elle seule
tous les comportements d’un parcours.

## Matrice exigences, fonctionnalités et preuves

Les chemins de code sont relatifs à la racine du dépôt.

| ID | Exigence | Réalisation et point de contrôle | Preuve ou document | Statut |
|---|---|---|---|---|
| IMP-01 | Import CSV, JSON et TXT | CSV, JSON Lines et TXT selon un contrat précis | [Formats](formats-import.md), [références](../samples/README.md)  [Revalidation SCRUM-27](validation-socle/bilan-20261127T195849Z-ee489653.json) | Actuel — contrôle automatisé |
| IMP-02 | Dépôt par glisser-déposer et sélection | Interface d’import | [Guide](guide-utilisateur.md), [capture](captures/interfaces/import-desktop.png) | Historique |
| IMP-03 | Limite configurable et validation client/serveur | MAX_UPLOAD_BYTES ; contrôle extension, structure et contenu | [Import](import.md), app/import_reader.py et app/validation.py | Historique |
| IMP-04 | Progression du transfert | Progression de l’envoi affichée avant le traitement | app/static/import.js, [guide](guide-utilisateur.md) | Historique |
| IMP-05 | Aperçu des dix premiers événements | Aperçu avant confirmation ; contrôle complet pendant l’ingestion | [Rapport](rapport.md), [validation](validation-ingestion/bilan-20261118T105637Z-a9564dca.json)  [Revalidation SCRUM-27](validation-socle/bilan-20261127T195849Z-ee489653.json) | Actuel — contrôle automatisé |
| IMP-06 | Erreurs compréhensibles | Refus de structure et diagnostics de validation | [Réponses Swagger](validation-ingestion/swagger/)  [Revalidation SCRUM-27](validation-socle/bilan-20261127T195849Z-ee489653.json) | Actuel — contrôle automatisé |
| ING-01 | Ingestion déclenchée après confirmation | Fichier conservé ; tracker puis envoi HTTP à Logstash | [Ingestion](ingestion.md), [rapport](rapport.md) | Convention |
| ING-02 | Configurations CSV et JSON distinctes | Un seul pipeline de production, parsing selon le format | logstash/pipeline/main.conf ; voir E-01 | Écart |
| ING-03 | Parsing, validation, enrichissement et normalisation | Scripts Ruby parse, validate, normalize ; modèle ECS | [Modèle](modele-logs.md), logstash/scripts/  [Revalidation SCRUM-27](validation-socle/bilan-20261127T195849Z-ee489653.json) | Actuel — contrôle automatisé |
| ING-04 | Indexation et gestion des rejets | Sorties Elasticsearch et fichier de rejets | [Bilan des douze scénarios](validation-ingestion/bilan-20261118T105637Z-a9564dca.json)  [Revalidation SCRUM-27](validation-socle/bilan-20261127T195849Z-ee489653.json) | Actuel — contrôle automatisé |
| SUI-01 | Suivi du statut et des compteurs | EN_ATTENTE, EN_COURS, TERMINE, PARTIEL, ECHEC | [Suivi](suivi-imports.md), [import partiel](captures/ingestion/suivi-import-partiel.png)  [Revalidation SCRUM-27](validation-socle/bilan-20261127T195849Z-ee489653.json) | Actuel — contrôle automatisé |
| SUI-02 | Erreur technique distincte des rejets de données | Scénario HTTP 503 contrôlé | [Bilan HTTP 503](validation-ingestion/erreur-traitement-20261118T111950Z-9b797490.json)  [Revalidation SCRUM-27](validation-socle/erreur-traitement-20261127T200034Z-966d463a.json) | Actuel — contrôle automatisé |
| FIL-01 | Liste des fichiers et métadonnées | Nom, confirmation, taille, statut et compteurs ; MongoDB | [Fichiers](fichiers.md), [capture](captures/interfaces/fichiers-desktop.png) | Historique |
| FIL-02 | Tri, pagination et filtres statut/date | 20 fichiers par page ; filtres combinables | [Bilan](validation-fichiers/bilan-tris-filtres.json) | Historique |
| REC-01 | Recherche texte, niveau, service et dates | Recherche générale et filtres avancés | [Recherche](recherche.md), [preuves](validation-recherche/swagger/) | Historique |
| REC-02 | Résultats, total, pagination et tri | 50 logs par page ; date, niveau et service | [Pagination](captures/recherche/recherche-pagination.png), [guide](guide-utilisateur.md) | Historique |
| REC-03 | Filtres invalides et période vide | Réponses d’erreur distinctes des résultats vides | [Preuves](validation-recherche/swagger/) | Historique |
| DET-01 | Détail complet d’un log | Popup avec champs, JSON et copie | [Détail](detail-export.md), [capture](captures/detail-export/detail-log-interface.png) | Historique |
| EXP-01 | Export CSV des résultats filtrés | Toutes pages ; limites 10 000 logs et 20 Mio | [Documentation](detail-export.md), [export filtré](validation-detail-export/export-filtre.csv) | Historique |
| HIS-01 | Historique MongoDB accessible | Critères, tri, date et nombre de résultats | [Historique](historique-recherches.md), [schéma](schema-historique-recherches.md) | Historique |
| HIS-02 | Relance d’une recherche | Réexécution des critères enregistrés ; historique commun | [Guide](guide-utilisateur.md), [preuves](validation-historique/) | Historique |
| KPI-01 | Quatre cartes de synthèse | Total, jour Tunis, ERROR/CRITICAL, imports confirmés | [Formules](formules-kpi.md), [référence](validation-dashboard/kpi-reference.json) | Historique |
| KPI-02 | Moyenne HTTP, taux 5xx, SQL lentes et fonctionnalités | Agrégations métier avec unités et populations définies | [Dashboard](dashboard.md), [preuves](validation-dashboard/) | Historique |
| KPI-03 | Utilisateurs actifs | Utilisateurs distincts HTTP ou métier ; aucune mesure des connexions simultanées | [Cadrage](cadrage.md), [formules](formules-kpi.md) ; voir E-03 | Convention |
| RED-01 | Cache Redis | Cache des indicateurs, expiration et comportement de repli | [Redis](cache-redis.md), [bilan](validation-cache/bilan-cache.json) | Historique |
| UI-01 | Pages accessibles et navigation cohérente | Six pages HTTP accessibles avec lien Kibana | Contrôle HTTP/HTML du 27 novembre, exécuté dans webapp | Actuel |
| UI-02 | Swagger accessible dans un nouvel onglet | Un lien /api/docs avec target=_blank et noopener | Contrôle HTML du 27 novembre | Actuel |
| UI-03 | Responsive ordinateur, tablette et mobile | Vérifications antérieures des interfaces ; nouvelle page Kibana confirmée à 324 et 720 px | [Guide](guide-utilisateur.md) ; confirmation manuelle du porteur du projet le 27 novembre 2026 | Actuel — vérification manuelle déclarée |
| UI-04 | Graphiques avec Chart.js ou Plotly | Technologie de rendu à confronter à l’exigence explicite | app/static/dashboard_ui.js ; voir E-02 | Écart confirmé — SVG natif |
| UI-05 | Footer, états et absence d’erreurs JavaScript | Footer absent dans les six templates ; erreurs de profil utilisateur dans Kibana | Voir E-07, E-15 et le diagnostic console dans [le registre](defauts-socle.md) | Écart confirmé — couverture partielle |
| KIB-01 | Vue de données et trois visualisations SaaS | Latence en ms, erreurs 5xx et utilisateurs distincts | [Kibana](kibana.md), [référence](validation-kibana/reference.json) | Historique |
| KIB-02 | Filtre temporel | Journée avec données et journée vide | [26 novembre](captures/kibana/dashboard-2026-11-26.png), [période vide](captures/kibana/dashboard-periode-vide.png) | Historique |
| KIB-03 | Export versionné et restauration | Cinq objets sans référence manquante ; import dans un espace séparé | [Export](../kibana/exports/loganalyzer-saas-dashboard.ndjson), [procédure](kibana.md) | Historique |
| KIB-04 | Intégration dans l’application | Page /kibana, iframe et ouverture directe ; affichage confirmé par l’utilisateur | app/kibana.py, app/templates/kibana.html ; capture à versionner | Actuel |
| KIB-05 | Rafraîchissement automatique des données | L’export ne contient pas de refreshInterval ; le rafraîchissement automatique des données reste non démontré | Voir E-04 | Non démontré — E-04 ouvert |
| OPS-01 | Disponibilité des dépendances | Six services ; Kibana disponible, Elasticsearch dégradé | Contrôle /api/v1/services/status du 27 novembre | Actuel |
| OPS-02 | Template et mapping Elasticsearch | Types ECS et index loganalyzer-logs-* | [Modèle](modele-logs.md), configuration Elasticsearch à relire | À vérifier |
| OPS-03 | Docker, volumes, réseau et healthchecks | Sept conteneurs redémarrés et healthy le 27 novembre ; ce contrôle ne démontre pas à lui seul la persistance des données | [Docker](docker.md), docker-compose.yml ; sortie Docker communiquée pendant la revue | Actuel — démarrage et santé ; persistance distincte |
| OPS-04 | Configuration reproductible | Variables Kibana documentées ; clé persistante locale et modèle sans secret | .env.example, docker-compose.yml, [Kibana](kibana.md) ; voir E-05 | Configuration actualisée ; procédure de démarrage à relire |
| OPS-05 | Persistance après redémarrage | Validation antérieure annoncée ; preuve et procédure à retrouver | [Docker](docker.md), [installation](installation.md) | À vérifier |
| DOC-01 | Documentation à jour et preuves reliées | README, guide et sections des modules du rapport actualisés ; liens locaux vérifiés | [Guide](guide-utilisateur.md), [rapport](rapport.md), [parcours](parcours-demonstration.md) ; voir E-06 et E-08 | Actuel — documentation des modules ; rapport pédagogique final à assembler |

## Contrôles actuels constatés

Le contrôle exécuté le 27 novembre 2026 a confirmé :

- HTTP réussi et navigation Kibana sur /dashboard, /, /files,
  /logs, /search-history et /kibana.
- Un seul lien Swagger sur le tableau de bord, configuré pour un nouvel onglet.
- Six services retournés : Flask, Elasticsearch, MongoDB, Redis, Logstash, Kibana.
- Flask, MongoDB, Redis, Logstash et Kibana disponibles.
- Elasticsearch dégradé, conformément au contexte du cluster à un seul nœud.
- Contrôle serveur de l’intégration Kibana positif.

Les sorties ont été communiquées pendant la revue.
Une preuve reproductible versionnée reste à ajouter.
Le contrôle HTTP ne démontre pas l’exécution de JavaScript ni le responsive.

## Travaux réalisés et suites

Les contrôles ciblés d’ingestion et d’erreur technique sont terminés.
Les parcours de démonstration, le registre priorisé, le guide et les
sections des modules du rapport ont été actualisés.

Les preuves historiques sont réutilisées avec leur portée indiquée.
Les points encore insuffisamment démontrés restent explicitement ouverts.
Les captures récentes de l’intégration et les preuves complémentaires
doivent être rattachées au registre ; elles ne sont pas déclarées acquises.

[Registre des écarts et défauts](defauts-socle.md)

## Bilan de la revalidation d’ingestion

- Douze scénarios réussis, zéro échec :
  [bilan](validation-socle/bilan-20261127T195849Z-ee489653.json).
- Scénario HTTP 503 réussi :
  [bilan](validation-socle/erreur-traitement-20261127T200034Z-966d463a.json).
- Base MongoDB et fichiers temporaires du test HTTP 503 supprimés.
- Les imports des scénarios d’ingestion restent dans les données du projet.

Le validateur historique comparait les documents aux cibles avant
l’ajout des champs dérivés search_text et search_values.
Les premiers essais de cette revue ont donc signalé trois différences.
Le validateur a été actualisé pour contrôler le contenu des deux champs,
puis comparer les autres champs aux cibles métier.
Les bilans initiaux sont conservés ; ils ne sont pas présentés comme réussis.

Cette validation automatisée couvre l’API et la chaîne de traitement.
Les interactions de l’interface restent appuyées par leurs preuves
et observations distinctes.

[Parcours de démonstration](parcours-demonstration.md)

## Vérification documentaire et responsive

Le 27 novembre 2026, le contrôle des liens locaux des sept documents
a réussi. Les deux bilans récents sont lisibles et indiquent OK.
L’export Kibana contient cinq objets et aucune référence interne manquante.

Le porteur du projet confirme l’utilisation du menu, du sélecteur de période
et du bouton d’ouverture directe de la page Kibana à 720 et 324 px.
Cette confirmation est une observation manuelle déclarée.

L’export indique timeRestore=false et ne contient pas de refreshInterval.
Le rafraîchissement automatique des données n’est donc pas établi
par cette preuve. Le contrôle périodique de disponibilité reste distinct.

Les écarts Logstash et graphiques SVG restent ouverts.
