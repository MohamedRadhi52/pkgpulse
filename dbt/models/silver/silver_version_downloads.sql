-- Jours complets seulement : le jour du dump, compté jusqu'à l'heure du dump, est écarté
-- (docs/DECISIONS.md, décision 6). Vue : la table bronze est déjà typée et volumineuse.
{{ config(materialized='view') }}

select
    date as download_date,
    version_id,
    downloads,
    source
from {{ source('bronze', 'version_downloads') }}
where date < cast(extracted_at as date)
