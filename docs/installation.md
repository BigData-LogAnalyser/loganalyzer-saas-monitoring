# Installation et environnement de développement

## État du projet

L'environnement local est préparé.
L'application et les services Docker du projet ne sont pas encore déployés.

## Environnement vérifié le 4 novembre 2026

| Élément | Version ou état |
|---|---|
| Système | Ubuntu 24.04.4 LTS |
| Git | 2.43.0 |
| Python | 3.12.3 |
| pip | 24.0 |
| VS Code | 1.143.1 |
| Docker Engine | 29.4.1 |
| Docker Compose | 5.1.3 |
| RAM totale | Environ 23 Gio |
| RAM disponible au relevé | Environ 6,8 Gio |
| Espace disponible sur / | Environ 169 Go |

Ces ressources décrivent la machine de développement.
Elles ne constituent pas des prérequis minimaux mesurés.
La mémoire et l'espace disponibles varient dans le temps.

## Préparer le dépôt local

Git, Python avec le module venv, Docker Engine et Docker Compose
doivent être disponibles sur la machine.

Pour une première installation :

```bash
mkdir -p ~/projets
cd ~/projets
git clone https://github.com/BigData-LogAnalyser/loganalyzer-saas-monitoring.git
cd loganalyzer-saas-monitoring
python3 -m venv .venv
source .venv/bin/activate
```

Le dépôt et l'environnement virtuel sont déjà créés sur le poste
de développement.

## Reprendre le travail

Dans un nouveau terminal :

```bash
cd ~/projets/loganalyzer-saas-monitoring
source .venv/bin/activate
code .
```

Vérifier que Python et pip proviennent de l'environnement virtuel :

```bash
which python
python --version
python -m pip --version
```

Le chemin de Python doit se terminer par
`loganalyzer-saas-monitoring/.venv/bin/python`.

L'environnement `.venv` est local et exclu du dépôt par `.gitignore`.
Cette exclusion peut être vérifiée avec :

```bash
git check-ignore .venv/pyvenv.cfg
```

Les dépendances applicatives seront définies lors de l'implémentation.

Pour quitter l'environnement virtuel :

```bash
deactivate
```

## Vérifier Docker

```bash
docker --version
docker compose version
docker info --format 'Serveur Docker : {{.ServerVersion}}'
```

L'accès au serveur Docker a été vérifié avec le compte utilisateur.
La configuration des services du projet sera réalisée dans le ticket
consacré à Docker Compose.

## Préserver les installations ELK des TP

Au relevé du 4 novembre 2026 :

- Le service Elasticsearch des TP est actif.
- Les services Kibana et Logstash des TP sont inactifs.
- Les ports 9200 et 9300 sont occupés par Elasticsearch.
- Le port 80 est également occupé.

Le projet utilisera ses propres conteneurs, son réseau Docker
et ses volumes dédiés.

Les configurations, les données et les services des TP doivent
être conservés. Les volumes du projet ne doivent pas utiliser
les répertoires de données des TP.

Ports hôte prévus pour le projet :

| Service | Port hôte prévu |
|---|---|
| Application Flask | 8000 |
| Kibana | 5602 |

Elasticsearch, MongoDB et Redis resteront accessibles sur le réseau
Docker interne, sans publication de leurs ports sur l'hôte dans
la configuration initiale.

Ces choix seront confirmés dans le fichier Docker Compose.

## Vérifier les ressources avant le déploiement

```bash
free -h
df -h /
ss -ltnp
```

Vérifier que les ports prévus sont toujours disponibles et que
la mémoire disponible permet de démarrer les services.

Le budget mémoire des conteneurs sera défini lors de la préparation
de Docker Compose, en tenant compte des autres services actifs.