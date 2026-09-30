with daily as (
    select
        crate_categories.category_slug,
        crate_downloads.download_date,
        sum(crate_downloads.downloads) as downloads
    from {{ ref('silver_crate_downloads') }} as crate_downloads
    inner join {{ ref('silver_crate_categories') }} as crate_categories
        on crate_downloads.crate_id = crate_categories.crate_id
    group by crate_categories.category_slug, crate_downloads.download_date
)

-- Une ligne par catégorie et par jour du calendrier : un jour sans téléchargement vaut zéro.
select
    categories.category_slug,
    categories.category_name,
    calendar.download_date,
    coalesce(daily.downloads, 0) as downloads
from {{ ref('silver_categories') }} as categories
cross join {{ ref('gold_daily_total') }} as calendar
left join daily
    on categories.category_slug = daily.category_slug
    and calendar.download_date = daily.download_date
