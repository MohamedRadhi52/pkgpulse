-- Paquets suivis : les plus téléchargés sur une fenêtre fixe, antérieure à la période
-- d'évaluation, pour ne pas choisir les séries en connaissant leur avenir (docs/cadrage.md).
with window_downloads as (
    select
        crate_id,
        sum(downloads) as downloads
    from {{ ref('silver_crate_downloads') }}
    where download_date between cast('{{ var("top_crates_start") }}' as date)
        and cast('{{ var("top_crates_end") }}' as date)
    group by crate_id
),

ranked as (
    select
        crate_id,
        downloads,
        row_number() over (order by downloads desc, crate_id) as crate_rank
    from window_downloads
)

select
    ranked.crate_rank,
    ranked.crate_id,
    crates.crate_name,
    ranked.downloads as window_downloads
from ranked
inner join {{ ref('silver_crates') }} as crates on ranked.crate_id = crates.crate_id
where ranked.crate_rank <= {{ var('top_crates_count') }}
