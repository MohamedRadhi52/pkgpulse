-- Un paquet compte une fois par catégorie de premier niveau, même s'il est rangé dans
-- plusieurs de ses sous-catégories.
select distinct
    crates_categories.crate_id,
    {{ dbt.split_part('categories.slug', "'::'", 1) }} as category_slug
from {{ source('bronze', 'crates_categories') }} as crates_categories
inner join {{ source('bronze', 'categories') }} as categories
    on crates_categories.category_id = categories.id
