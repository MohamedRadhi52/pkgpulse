-- Toutes les versions, y compris celles de paquets supprimés depuis et absents des métadonnées.
select
    download_date,
    sum(downloads) as downloads
from {{ ref('silver_version_downloads') }}
group by download_date
