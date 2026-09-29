# Revue de code : version initiale (générée par Gemini)

> Revue réalisée le 29/09/2026 sur les commits `3beff74` → `2dcf320`, puis corrections dans les commits suivants de la branche.

## En bref

L'**architecture** proposée par Gemini est saine : monolithe modulaire FastAPI, agents séparés, fournisseurs LLM/recherche abstraits, suivi temps réel en SSE, frontend Next.js, et une interface monochrome réussie. Le README et le `PROJECT_STATUS.md` annonçaient cependant un projet « 100 % terminé », alors que **seule la démo sur SQLite fonctionnait**. Il suffisait d'en sortir pour que ça casse :

| Gravité | Exemples |
|---|---|
| Bloquant | CI cassée, crash systématique sous PostgreSQL/Docker, image web impossible à construire, Next.js avec CVE critiques, aucune recherche réelle possible, contenu inventé, protection SSRF contournable |
| Majeur | vérification sans effet sur le rapport, mode « deep » identique au « standard », annulation inopérante, rerun qui lance deux recherches, crash de l'interface, mémoire qui duplique les sources |
| Mineur | documentation inexacte, ports de base de données exposés, scripts de démarrage incomplets, tests qui accèdent au réseau |

Chaque point bloquant ci-dessous a été **reproduit** (et non déduit de la lecture du code), puis corrigé et couvert par un test.

## Méthode

1. Lecture intégrale du code (backend, frontend, Docker, CI, docs).
2. Exécution réelle : tests, API sur SQLite **et** sur un vrai PostgreSQL, build du frontend, `npm audit`, sondes SSRF, construction et lancement des images Docker.
3. Pour chaque bug : reproduction, correction, test de non-régression.

## 1. Problèmes bloquants

### 1.1 CI et démarrage natif cassés
`aiosqlite` manquait dans `requirements.txt` alors que la base par défaut est `sqlite+aiosqlite`. Résultat : `ModuleNotFoundError` dès le chargement des tests (le workflow CI échouait), et `start.sh`/`start.bat` plantaient au démarrage.

### 1.2 Toute recherche plantait sous PostgreSQL (donc avec Docker)
Les modèles utilisaient `datetime.utcnow` (naïf), l'orchestrateur `datetime.now(timezone.utc)` (avec fuseau). asyncpg refuse ce mélange :
```
asyncpg ... invalid input for query argument $6: datetime.datetime(...) (can't subtract offset-naive and offset-aware datetimes)
```
Le gestionnaire d'erreur plantait à son tour (`PendingRollbackError`, pas de rollback), donc la recherche restait bloquée en `planning` **pour toujours**, et le flux SSE bouclait sans fin. Le chemin Docker Compose n'a donc jamais pu fonctionner.

### 1.3 Déploiement impossible
- `apps/web/Dockerfile` copiait un dossier `public/` inexistant : l'image ne se construisait pas.
- Le frontend appelait `http://localhost:8000` en dur (8 occurrences), et `NEXT_PUBLIC_API_URL` défini dans le compose n'était jamais lu. Déployé sur un serveur, le navigateur de l'utilisateur appelait son propre `localhost`.
- Next.js 14.1.4 : `npm audit` signalait **1 vulnérabilité critique et 1 haute** (dont des RCE et des SSRF).

### 1.4 Aucune recherche réelle possible
- `get_search_provider()` renvoyait **toujours** le mock, quelle que soit la configuration. DuckDuckGo, Tavily et SearXNG étaient documentés mais pas implémentés.
- Côté LLM, seul OpenAI existait, avec une clé lue via `os.getenv`, donc **ignorée si elle était mise dans `.env`** (pydantic-settings ne remplit pas `os.environ`). Gemini et Groq étaient annoncés dans `.env.example` sans implémentation.

### 1.5 Contenu inventé, présenté comme des preuves
Pour un outil qui promet des « citations vérifiables », c'est le point le plus grave :
- L'extracteur renvoyait `"Synthetic extracted content representing knowledge base for {url}. Details on curriculum and active learning empirical studies."` pour **toute** page inaccessible, y compris en production. Ce texte partait ensuite au LLM comme contenu de la source.
- Si le LLM renvoyait un JSON invalide, le vérificateur et l'analyseur de lacunes produisaient des **affirmations codées en dur sur l'apprentissage de Python**, quelle que soit la question.
- Le mock répondait sur « comment apprendre Python » à toute question. Reproduit : une question sur la cryptographie post-quantique produisait un plan sur l'apprentissage de Python, 5 sources « Synthetic extracted content », et un rapport intitulé *« Research Report: What are the tradeoffs of post-quantum cryptography?... »* au contenu sans rapport.

### 1.6 Protection SSRF contournable
La vérification se faisait par préfixes de chaînes. Sondes réelles :

| URL | Autorisée ? |
|---|---|
| `http://169.254.169.254/latest/meta-data/` (métadonnées cloud) | **oui** |
| `http://2130706433/` (127.0.0.1 en décimal) | **oui** |
| `http://[::ffff:127.0.0.1]/`, `http://[fd00::1]/`, `http://100.64.0.1/` | **oui** |
| `http://metadata.google.internal/`, tout nom DNS pointant vers une IP privée | **oui** |
| `http://172.217.16.142/` (IP publique Google) | bloquée à tort |

De plus, les **redirections étaient suivies sans vérification** (contournement trivial), et une URL rejetée levait une exception qui faisait échouer **toute** la recherche.

### 1.7 `.gitignore` piégé
Le motif Python `lib/` ignorait **tous** les dossiers `lib`, y compris `apps/web/lib/`, qui aurait silencieusement disparu du dépôt.

## 2. Problèmes majeurs (logique du pipeline et de l'interface)

- **La vérification n'influençait pas le rapport** : le synthétiseur ne recevait ni les affirmations vérifiées ni les contradictions. Le résumé exécutif et les limites étaient des phrases fixes, et le titre toujours suffixé par « ... ».
- **« Deep » = « Standard »** : les deux faisaient exactement un tour d'analyse des lacunes, et les sources ajoutées n'étaient jamais re-vérifiées.
- **Annulation inopérante** : l'endpoint changeait le statut, mais l'orchestrateur l'écrasait ensuite et terminait la recherche. Aucun bouton d'annulation dans l'interface.
- Les limites (`MAX_SOURCES`, `MAX_RUNTIME_SECONDS`…) n'étaient jamais appliquées ; `tokens_used` et `results_count` restaient à 0.
- **Mémoire sémantique** : une même URL était rappelée plusieurs fois, et le préfixe s'accumulait (reproduit : `[Reused Memory] [Reused Memory] Extracted Resource: docs.python.org`). Chaque requête chargeait le contenu complet de toutes les sources. Et l'embedding présenté comme « sémantique » était un sac de mots haché, sans stopwords ni ponctuation retirée.
- **Sources dupliquées** entre la recherche initiale et les recherches complémentaires.
- **Rerun lançait deux recherches** : l'UI appelait `/rerun` (qui démarre déjà une recherche), puis `POST /research`, avec un domaine et une profondeur potentiellement faux (état React pas encore à jour).
- **Écran blanc** : une question de moins de 5 caractères renvoyait une 422, puis l'UI ouvrait `EventSource(/research/undefined/events)` et finissait par `research.claims.length` sur un objet d'erreur.
- L'historique renvoyait le détail complet (contenu intégral des sources) de 50 recherches. Inspecter une ancienne recherche affichait la télémétrie de la dernière exécutée.
- Redis était exigé par le healthcheck (statut « degraded » en natif) mais inutilisé. L'ADR-003 décrivait un pub/sub Redis inexistant, et l'ADR-004 un Alembic absent.
- Les dates étaient renvoyées sans fuseau, et donc interprétées en heure locale par le navigateur.
- Une recherche interrompue par un redémarrage restait « en cours » indéfiniment.

## 3. Problèmes mineurs et documentation

- README : fichier `LICENSE` absent, commande de test PowerShell uniquement, `docker-compose.prod.yml` référencé mais inexistant, image API décrite comme non-root alors qu'elle tournait en root. `PROJECT_STATUS.md` contenait des liens `file:///d:/...` vers le poste de développement.
- docker-compose exposait PostgreSQL (mot de passe `postgres`) et Redis sur l'hôte, avec un healthcheck Postgres qui ignorait les variables, une clé `version` obsolète, et une image de production sur laquelle le code source était monté.
- `start.bat` n'installait pas les dépendances web, et `start.sh` n'était pas exécutable. Les deux scripts créaient la base SQLite dans des dossiers différents.
- Frontend : un fichier unique de 1066 lignes, le rapport Markdown affiché en texte brut (classe `prose` sans le plugin), des dépendances inutilisées (react-query, zustand), une interface non responsive, une classe `dark` sans styles, et des statuts codés en dur (« HYBRID MOCK »).
- Tests : ils faisaient de vraies requêtes HTTP, et il n'y avait aucun test d'API, d'orchestrateur ou de sécurité.

## 4. Ce qui a été corrigé et ajouté

**Backend**
- Dates stockées en UTC via un `TypeDecorator`, compatible avec les bases existantes. Synchronisation de schéma additive au démarrage, avec reprise des anciennes données (numérotation des événements, nettoyage des préfixes `[Reused Memory]`).
- Récupération web sûre : vérification DNS de chaque adresse, contrôle **au moment de la connexion** (anti DNS-rebinding), redirections re-vérifiées une à une, taille et types de contenu plafonnés, prise en charge des proxys d'entreprise.
- Plus aucun contenu inventé : une page inaccessible passe par l'extrait du moteur de recherche (signalé « snippet only »), sinon la source est ignorée. Une réponse LLM inutilisable déclenche une relance de réparation, puis un avertissement visible, sans jamais fabriquer d'affirmation.
- Fournisseurs réels :
  - LLM : OpenAI-compatible (OpenAI, Groq, OpenRouter, Ollama, LM Studio…, avec adaptation automatique aux paramètres refusés), Gemini, et Anthropic via le SDK officiel (`claude-sonnet-5-5` par défaut, effort réglable, repli côté serveur si le modèle décline une requête) ;
  - recherche : Tavily, SearXNG, DuckDuckGo, Wikipédia, arXiv, combinables ;
  - cache Redis optionnel, avec repli en mémoire.
- Pipeline :
  - vraie boucle « deep » (lacunes → recherches complémentaires → re-vérification, jusqu'à 3 tours) ;
  - synthèse fondée sur les affirmations et les contradictions, citations `[n]` validées, titre, résumé et limites extraits du rapport, rapport rédigé dans la langue de la question ;
  - score de pertinence réellement calculé (autorité, correspondance, rang, profondeur, fraîcheur).
- Exécution :
  - annulation réelle (poignée sur la tâche, mise à jour conditionnelle du statut) ;
  - limite de temps et compteurs de tokens ;
  - reprise propre après un redémarrage ;
  - régénération du rapport après exclusion de sources.
- API : liste allégée avec compteurs, recherche et filtres ; SSE avec reprise (`Last-Event-ID`) et keep-alive ; exports Markdown et JSON ; validation des entrées ; healthcheck qui ne divulgue plus les erreurs internes.
- Mode démo hors ligne qui s'adapte à la question (FR/EN), avec une latence simulée pour voir le pipeline travailler.

**Frontend** (Next.js 16, React 19, 0 vulnérabilité)
- Proxy de même origine vers l'API : un seul port public, pas de CORS, flux SSE transmis en direct.
- Rapport mis en forme avec citations cliquables, affirmations, contradictions, sources (détail du score, texte intégral, exclusion), plan et chronologie en direct.
- Historique avec recherche serveur, filtres et pagination ; recherche dans la mémoire ; annulation, rerun, export, impression.
- URL partageables (`?r=<id>`), thème sombre, mise en page mobile, accessibilité (onglets, dialogues, focus).

**Infra**
- Images Docker non-root et fonctionnelles, construites et testées ici : la stack Compose passe « healthy » et une recherche aboutit de bout en bout sur PostgreSQL et Redis.
- Compose de production (bases non exposées) plus une surcouche de développement avec rechargement à chaud.
- CI : lint, tests sur SQLite **et** PostgreSQL, build du frontend, construction et test des images Docker.
- Scripts de démarrage complets (Windows et Unix), `.env.example` exact, licence MIT.

**Tests** : 103 tests backend sans aucun accès réseau (SSRF, extraction, fournisseurs via transports simulés, agents, API de bout en bout, annulation, SSE, reprise après crash), exécutés sur SQLite et PostgreSQL.

## 5. Ce qui reste, et idées pour la suite

1. **Authentification** et limitation de débit. Aujourd'hui, toute personne qui atteint l'application peut consommer vos crédits d'API : déployez-la derrière un proxy authentifiant (voir [COOLIFY_DEPLOYMENT.md](COOLIFY_DEPLOYMENT.md)).
2. **Vrais embeddings** (fournisseur d'embeddings), avec pgvector pour une mémoire à grande échelle.
3. **File de tâches** (Arq, Celery…) pour plusieurs workers : les recherches tournent pour l'instant dans le processus de l'API.
4. **Alembic** quand le schéma sera stabilisé (la synchronisation actuelle ne sait qu'ajouter des colonnes).
5. Lecture des **PDF** et rendu des sites JavaScript.
6. **Jeu d'évaluation** (questions de référence) pour comparer modèles, prompts et profondeurs de façon mesurable.
7. Rapport diffusé **token par token** pendant la synthèse.
