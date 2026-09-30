# Décisions

Journal des choix techniques, dans l'ordre où ils ont été pris. Chaque entrée donne le constat, la
décision et sa raison.

## 1. Deux sources qui se complètent : l'archive et le dump

Constats relevés en septembre 2026 :

- `https://static.crates.io/archive/version-downloads/index.json` liste 4 248 fichiers
  quotidiens, du 2014-11-11 au 2026-06-29, avec un seul trou (2014-11-15). Chaque entrée donne
  `name` (`AAAA-MM-JJ.csv`) et `size` en octets.
- Un fichier d'archive contient une ligne par version téléchargée ce jour-là. Il pèse de 2 à 5 Mo
  en 2026, jusqu'à 23,6 Mo le 2026-06-21.
- Le fichier du jour J est publié vers 23 h 30 UTC le jour J+91 : l'archive a trois mois de
  retard. Son ETag est le MD5 du fichier, ce qui permet de vérifier chaque téléchargement.
- Le dump `https://static.crates.io/db-dump.tar.gz` est régénéré toutes les 24 heures. Il contient
  `metadata.json` (horodatage UTC du début du dump), un README, les scripts SQL d'import, et un CSV
  par table dans `data/`, dont `version_downloads.csv` pour les 90 derniers jours. Il est servi
  par CloudFront après une redirection ; sa taille est relevée à chaque exécution du pipeline.

Décision : l'archive fournit l'historique définitif ; le dump fournit les 90 derniers jours et les
métadonnées (paquets, versions, catégories). Un jour quitte la base de crates.io au moment où il
entre dans l'archive, donc les deux sources se rejoignent sans trou.

## 2. Historique à partir du 1er novembre 2025

Le 29 octobre 2025, crates.io a restreint le comptage aux requêtes dont le user-agent est cargo,
pour écarter les miroirs (rust-lang/crates.io#12210). Sur une semaine complète avant et après le
changement, le nombre de lignes quotidiennes passe de 1,26 million à 304 000, alors que le total
continue de croître (+10 %, dans la tendance). Les miroirs téléchargeaient surtout des versions
peu demandées : la longue traîne change de niveau, pas l'agrégat.

Décision : l'historique commence le 2025-11-01, premier jour complet après le changement, pour que
toutes les séries relèvent du même régime de comptage.

## 3. Contrats de schéma

crates.io ne garantit pas la stabilité du schéma du dump. Chaque source a donc un contrat
(`src/pkgpulse/ingest/contracts.py`) : des colonnes requises avec leur type, et une clé qui doit
être non nulle et unique.

| Source | Colonnes requises | Clé |
|---|---|---|
| archive `AAAA-MM-JJ.csv` | `version_id` BIGINT, `downloads` BIGINT | `version_id` |
| dump `version_downloads.csv` | `version_id` BIGINT, `downloads` BIGINT, `date` DATE | `version_id`, `date` |
| dump `crates.csv` | `id` BIGINT, `name` VARCHAR, `created_at` TIMESTAMP, `updated_at` TIMESTAMP | `id` |
| dump `versions.csv` | `id` BIGINT, `crate_id` BIGINT, `num` VARCHAR, `created_at` TIMESTAMP, `yanked` BOOLEAN | `id` |
| dump `categories.csv` | `id` BIGINT, `category` VARCHAR, `slug` VARCHAR | `id` |
| dump `crates_categories.csv` | `crate_id` BIGINT, `category_id` BIGINT | `crate_id`, `category_id` |

Règles :

- Les colonnes supplémentaires sont ignorées : crates.io en ajoute régulièrement, et seules les
  colonnes utiles sont extraites.
- Une colonne manquante, un fichier vide, une valeur non convertible ou une clé nulle ou en
  double arrête l'ingestion avant toute écriture : rien de faux n'atteint la couche bronze.
- Format des CSV du dump, produits par `COPY ... WITH CSV HEADER` de PostgreSQL : booléens `t` et
  `f`, horodatages UTC sans fuseau (`AAAA-MM-JJ HH:MM:SS.ffffff`, parfois suffixés `+00`), champs
  multilignes entre guillemets. Certains README de paquets dépassent 2 Mo sur une seule ligne : la
  taille de ligne maximale du lecteur CSV est portée à 64 Mo.
- `index.json` : liste d'objets `name` et `size`. `metadata.json` : `timestamp` et
  `crates_io_commit`.

Ces contrats sont testés dans `tests/test_contracts.py`, sur des extraits au format réel et sur
chaque cas d'échec.

## 4. Conditions d'usage des données

- La politique d'accès de crates.io demande d'utiliser le dump plutôt que l'API pour les volumes
  importants ; static.crates.io n'impose pas de limite de débit.
- Le README du dump précise que les champs saisis par les utilisateurs (description, README) sont
  bruts et peuvent contenir des formules de tableur.
- Choix : chaque fichier d'archive est téléchargé une seule fois et le dump une fois par jour,
  avec un user-agent qui identifie le projet. Les tables d'utilisateurs et de propriétaires ne
  sont pas extraites. Seuls des agrégats (total, catégories, paquets) sont publiés ; les données
  brutes ne sont jamais versionnées dans le dépôt.

## 5. Couche bronze : un fichier Parquet par jour, remplacé en bloc

- Les téléchargements vont dans `data/bronze/version_downloads/AAAA-MM-JJ.parquet`, avec les
  colonnes `date`, `version_id`, `downloads`, `source` (`archive` ou `dump`), `checksum` et
  `extracted_at` (Last-Modified du fichier d'archive, ou horodatage du dump). Les tables de
  métadonnées du dump sont remplacées à chaque dump (`data/bronze/crates.parquet`, etc.) ; leur
  historique est conservé par le snapshot dbt.
- L'unité d'écriture est le jour : une écriture remplace toute la partition, par un fichier
  temporaire puis un renommage atomique. Relancer n'ajoute jamais de lignes, donc ne crée jamais
  de doublon. Un arrêt brutal laisse au pire un `.tmp` orphelin, ignoré par les lecteurs, et la
  relance reprend au premier jour manquant. Ce cas s'est produit pendant le premier backfill :
  processus tué après 48 jours, relance qui n'a téléchargé que les 193 jours restants.
- L'empreinte `checksum` est le MD5 des lignes du jour triées par version. Elle sert à ne pas
  réécrire un jour inchangé, à détecter les corrections tardives et à comparer l'archive et le dump
  sur un même jour, quelle que soit la source.
- L'intégrité des téléchargements est vérifiée à la source : MD5 contre ETag pour l'archive, CRC du
  gzip en fin de flux pour le dump.
- Pas de logique de nouvelle tentative : une exécution en échec est simplement relancée, et
  l'idempotence rend la relance sûre.

Volumes réels : du 2025-11-01 au 2026-06-29, 241 fichiers d'archive, 385 000 lignes par jour en
moyenne, 196 Mo de Parquet (0,8 Mo par jour contre 3,7 Mo en CSV).

## 6. Jonction de l'archive et du dump, données tardives

La règle, dans `src/pkgpulse/ingest/junction.py`, décide si une partition candidate remplace la
partition existante du même jour :

| Partition existante | Candidate | Écriture |
|---|---|---|
| aucune | archive ou dump | oui |
| dump | archive | oui : l'archive est définitive |
| archive | dump | non : le dump ne remplace jamais l'archive |
| dump | dump au contenu différent | oui : données tardives |
| même source, même contenu | | non |

Conséquence testée : exécuter l'archive puis le dump, ou le dump puis l'archive, donne le même état.

Le jour du dump n'est compté que jusqu'à l'heure du dump. Il est gardé en bronze, qui conserve le
brut, et écarté en aval : un jour est complet si sa date est antérieure à la date de
`extracted_at`. Le lendemain, le nouveau dump réécrit les jours dont le compte a changé, et
l'ingestion journalise chaque correction (nombre de téléchargements avant et après).

## 7. dbt : architecture médaillon, tests et snapshot

- **Bronze** : les fichiers Parquet de l'ingestion, déclarés comme sources dbt et lus directement
  par DuckDB. **Silver** : typage, renommage, jointures versions, paquets et catégories. **Gold** :
  séries quotidiennes prêtes pour la prévision (total, catégories, paquets suivis).
- `silver_version_downloads` est une vue : la donnée est déjà typée en bronze et une copie
  doublerait le stockage. Les autres modèles sont des tables.
- Les séries gold par catégorie et par paquet couvrent tout le calendrier, avec des zéros les
  jours sans téléchargement. Le calendrier est l'ensemble des jours complets du total, dont la
  continuité est testée.
- Catégories : seul le premier niveau du slug est gardé (`development-tools::testing` compte pour
  `development-tools`). Un paquet compte une fois par catégorie de premier niveau.

Tests, et ce qu'ils protègent :

| Test | Pourquoi |
|---|---|
| unicité et non-nullité des clés, unicité des couples (version, jour), (paquet, jour) | un doublon gonfle les séries sans erreur visible |
| relations versions et paquets | une jointure perdrait des lignes en silence |
| relation téléchargements et versions, en avertissement | mesure les téléchargements des paquets supprimés depuis, absents des métadonnées |
| fraîcheur de la source (alerte à 2 jours, erreur à 4) | le dump doit arriver chaque jour |
| aucun jour manquant | un trou fausserait les décalages et la saisonnalité |
| volume comparé à la moyenne du même jour sur quatre semaines | une chute trahit une perte de données ; seuil de 0,3, sous le creux réel le plus bas (0,36 à Noël 2025) |

Le snapshot `crates_snapshot` (stratégie timestamp sur `updated_at`, qui change à chaque
publication) garde l'historique de la dernière version et des catégories de chaque paquet, que le
dump écrase chaque jour.

En CI, dbt tourne sur un échantillon synthétique au format bronze (`python -m pkgpulse.sample`),
du 2025-11-01 à aujourd'hui, pour que la fraîcheur et la fenêtre des paquets suivis s'appliquent :
aucune donnée brute n'est versionnée. Les données réelles ne passent que par le workflow du
pipeline. Le SQL reste standard et passe par les macros inter-bases de dbt (`split_part`,
`listagg`, `datediff`), pour préparer le profil BigQuery du lot 3.

## 8. Publication des agrégats gold

Les quatre tables gold (total, catégories, paquets suivis et leur classement) sont exportées en
CSV triés et publiées dans la release `gold` du dépôt, remplacées à chaque exécution du pipeline.

- Une release plutôt qu'un commit : les fichiers changent chaque jour et alourdiraient
  l'historique git.
- Seuls ces agrégats sont publiés, conformément à la politique d'accès de crates.io ; la couche
  bronze reste dans le cache privé d'Actions.
- Ces fichiers servent de source aux étapes de prévision, au tableau de bord et à l'API.

## 9. Orchestration : Airflow pour la logique, GitHub Actions pour la production

- Le DAG `airflow/dags/pkgpulse_daily.py` décrit l'enchaînement (ingestion, dbt, export), les
  relances et la date logique. Il est testé en local par `make airflow-test` : sur l'échantillon
  synthétique, il est rejoué sur sept jours consécutifs, et chaque exécution passe les 44 contrôles
  dbt. Rejouer un jour passé ne crée aucun doublon, grâce à l'idempotence de l'ingestion.
- En production, un seul traitement par jour ne justifie pas un serveur Airflow : le même
  enchaînement tourne dans GitHub Actions, gratuit pour un dépôt public, chaque jour à 5 h 17 UTC,
  après le dump de crates.io (pris vers 2 h UTC).
- Relances : le premier backfill réel a échoué sur une erreur HTTP 500 passagère de
  static.crates.io, au 48e des 242 fichiers d'archive. La relance manuelle n'a téléchargé que les
  195 jours restants. Depuis, la relance est automatique : deux tentatives de plus dans Airflow,
  une relance après cinq minutes dans Actions.
- Alertes : un échec du pipeline déclenche l'e-mail de GitHub ; un workflow de surveillance
  quotidien échoue, et alerte à son tour, si le pipeline n'a pas réussi depuis 30 heures, ce qui
  couvre aussi une exécution qui n'a jamais démarré.

## 10. Backtest à origine glissante et MASE

- Une origine tous les 8 jours, du 2026-03-01 au dernier jour où J+7 est observable (26 origines
  au 29 septembre 2026). Avec un pas de 7 jours, toutes les origines tomberaient un dimanche : J+1
  serait toujours un lundi et J+7 toujours un dimanche, deux jours de niveaux très différents, ce
  qui fausserait la comparaison entre horizons.
- À chaque origine, un modèle ne reçoit que les données antérieures ou égales à l'origine. Deux
  tests le vérifient : un modèle espion qui note la dernière date reçue, et des valeurs futures
  empoisonnées qui ne doivent rien changer aux prévisions.
- MASE : erreur absolue divisée par l'erreur moyenne du naïf saisonnier sur l'historique
  d'entraînement, moyennée par série puis par niveau. Elle reste définie avec des zéros, compare
  des séries d'échelles différentes et se lit directement : sous 1, on bat le naïf saisonnier.
- Références : naïf saisonnier (même jour de la semaine précédente) et AutoETS (saisonnalité de 7
  jours) de statsforecast. statsforecast impose pandas < 3 : pandas est épinglé en 2.3.3.

## 11. Modèle global LightGBM et suivi MLflow

- Un modèle LightGBM par horizon, appris sur les 260 séries à la fois (total, 58 catégories, 200
  paquets et la série autres). Les volumes sont divisés par le niveau des 28 derniers jours : un
  seul modèle apprend ainsi sur des séries allant de 10^5 à 10^9 téléchargements par jour. Perte
  L1, cohérente avec la MASE.
- La forme du modèle a été choisie sur les six premières origines du backtest (mars à mi-avril
  2026) ; les résultats annoncés portent sur les origines suivantes.

| Variante (MASE du total, origines de conception) | J+1 | J+7 |
|---|---|---|
| Naïf saisonnier | 0,740 | 0,855 |
| Cible rapportée au niveau des 28 derniers jours | 1,081 | 0,753 |
| Cible rapportée au même jour de la semaine précédente, avec la dynamique récente | 0,489 | 1,169 |

  À J+1, le modèle apprend la correction à apporter au naïf saisonnier, avec l'évolution du
  dernier jour et de la dernière semaine. À J+7, la cible reste rapportée au niveau des 28 jours,
  plus stable qu'un seul jour, sans ces variables de court terme : les ajouter dégrade le total
  à 1,055. Les réglages diffèrent aussi par horizon (modèle plus régularisé à J+1).
- MLflow : une exécution par backtest (paramètres, MASE par niveau, horizon et modèle, tableaux),
  dans une base SQLite conservée avec les données. Les modèles réentraînés sur tout l'historique
  entrent au registre à chaque backtest, et reçoivent l'alias champion s'ils battent les deux
  références en moyenne à chaque horizon. La prévision charge le champion, ou à défaut la
  dernière version : elle ne s'arrête jamais faute de modèle.
- Une prévision datée (backfill du DAG) réentraîne les modèles sur les seules données connues à
  l'origine, pour ne pas utiliser un modèle qui a vu la suite.

## 12. Intervalles de prédiction conformels

- Erreur normalisée : écart absolu divisé par le niveau des 28 derniers jours. Pour chaque niveau
  et horizon, le quantile conformel des erreurs du backtest, avec la correction d'échantillon fini,
  donne la demi-largeur : intervalle = prévision plus ou moins quantile fois niveau, borné à zéro.
- La garantie de couverture (au moins 90 % en moyenne) suppose des erreurs échangeables ; jours
  fériés et forte croissance la mettent à l'épreuve. La couverture est donc mesurée sans fuite : à
  chaque origine, le quantile ne vient que des origines précédentes, après quatre origines de
  chauffe.

## 13. Deux niveaux de prévision : direct contre ascendant

- La série autres (total moins les 200 paquets suivis) rend la hiérarchie exactement additive :
  total = somme des paquets suivis + autres. On compare la MASE du total prévu directement et celle
  de la somme des prévisions de ses parties, pour chaque modèle et chaque horizon.
- Les catégories ne sont pas additives (un paquet peut en avoir plusieurs) : elles restent hors de
  cette comparaison. La réconciliation complète (MinT et variantes) est hors périmètre.

## 14. Détection d'anomalies

- Résidus à J+1 du modèle LightGBM, réentraîné tous les 8 jours et appliqué chaque jour. Chaque
  résidu est comparé aux 56 jours précédents de la même série par un score robuste : écart à la
  médiane divisé par 1,4826 fois la MAD. Au-delà de 4, le jour est un pic ou un creux.
- Sur les données réelles, de mars à septembre 2026 : 447 jours signalés sur 55 120 résidus
  (0,8 %), presque tous sur des paquets et des catégories ; le total ne l'est qu'une fois. Le 25 mai
  2026 (Memorial Day) concentre 238 séries et le 7 septembre (Labor Day) 42, avec un écho une
  semaine plus tard.
- Étude de cas : [docs/etude-de-cas-21-juin-2026.md](etude-de-cas-21-juin-2026.md).

## 15. Cloud : amorçage à la main, le reste dans Terraform

- Fait une fois à la main (amorçage) : le projet GCP, la facturation, une alerte de budget à 5 €,
  l'activation des API et le compte de service de la CI, avec sept rôles précis plutôt que le rôle
  propriétaire. Sa clé est dans les secrets du dépôt ; Workload Identity Federation éviterait une
  clé de longue durée, c'est l'amélioration suivante.
- Dans Terraform (`infra/`) : le bucket des données, les quatre datasets BigQuery (bronze, silver,
  gold, snapshots), le dépôt Artifact Registry avec une règle qui ne garde que les deux dernières
  images (offre gratuite de 0,5 Go), et le compte de service de l'API, en lecture seule sur le
  bucket. L'état est dans un bucket créé par le workflow s'il n'existe pas.
- Le workflow Terraform tourne à chaque push sur main : sans changement, il vérifie l'absence de
  dérive. `gh workflow run terraform.yml -f destroy=true` supprime tout après les candidatures ;
  `gcloud projects delete` reste l'option radicale.
- Tout est en us-central1 : l'offre gratuite de Cloud Storage n'existe que dans trois régions des
  États-Unis, et BigQuery doit être dans la même région que le bucket qu'il lit.
- Le même projet dbt tourne sur DuckDB (local, CI, pipeline) et sur BigQuery (cible `bigquery`).
  Le pipeline copie la couche bronze et les exports dans Cloud Storage ; une macro dbt y crée les
  tables externes du bronze, puis `dbt build` construit silver, gold et le snapshot dans BigQuery.
  Volume estimé : quelques Go lus par jour pour 1 To gratuit par mois, moins de 1 Go stocké.
- Les résultats détaillés du backtest (une ligne par série, origine, horizon et modèle) sont
  désormais exportés avec les autres fichiers, pour recalculer les tableaux du README.

## 16. API sur Cloud Run et déploiement continu

- L'API FastAPI lit les fichiers publiés par le pipeline dans Cloud Storage (prévisions et
  anomalies) et les relit au plus une fois par heure : pas de base de données à maintenir pour des
  données qui changent une fois par jour. Tant que rien n'est publié, elle répond 503.
- L'image ne contient que l'API (FastAPI, uvicorn, client Cloud Storage, sans pandas) : image
  légère, démarrage rapide, utilisateur non root.
- Enchaînement : push sur main, workflow Terraform puis, s'il réussit, workflow de déploiement :
  image étiquetée par le commit, poussée dans Artifact Registry, nouvelle révision Cloud Run et
  vérification de l'URL publique. Le service Cloud Run n'est pas dans Terraform, car son image
  change à chaque déploiement.
- Cloud Run descend à zéro instance et n'en dépasse pas une : l'offre gratuite couvre 2 millions de
  requêtes par mois.
