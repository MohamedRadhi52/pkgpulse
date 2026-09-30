with releases as (
    select
        crate_id,
        cast(published_at as date) as release_date,
        count(*) as versions_published
    from {{ ref('silver_versions') }}
    group by crate_id, cast(published_at as date)
)

-- Une ligne par paquet suivi et par jour du calendrier : un jour sans téléchargement vaut zéro.
select
    top_crates.crate_id,
    top_crates.crate_name,
    calendar.download_date,
    coalesce(crate_downloads.downloads, 0) as downloads,
    coalesce(releases.versions_published, 0) as versions_published
from {{ ref('gold_top_crates') }} as top_crates
cross join {{ ref('gold_daily_total') }} as calendar
left join {{ ref('silver_crate_downloads') }} as crate_downloads
    on top_crates.crate_id = crate_downloads.crate_id
    and calendar.download_date = crate_downloads.download_date
left join releases
    on top_crates.crate_id = releases.crate_id
    and calendar.download_date = releases.release_date
