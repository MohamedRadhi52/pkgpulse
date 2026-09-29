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
