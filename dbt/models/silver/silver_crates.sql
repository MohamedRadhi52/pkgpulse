with latest_versions as (
    select
        crate_id,
        version_number,
        row_number() over (partition by crate_id order by published_at desc) as recency
    from {{ ref('silver_versions') }}
    where not yanked
),

crate_categories as (
    select
        crate_id,
        {{ dbt.listagg('category_slug', "', '", 'order by category_slug') }} as categories
    from {{ ref('silver_crate_categories') }}
    group by crate_id
)

select
    crates.id as crate_id,
    crates.name as crate_name,
    crates.created_at,
    crates.updated_at,
    latest_versions.version_number as latest_version,
    crate_categories.categories
from {{ source('bronze', 'crates') }} as crates
left join latest_versions
    on crates.id = latest_versions.crate_id and latest_versions.recency = 1
left join crate_categories on crates.id = crate_categories.crate_id
