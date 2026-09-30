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
