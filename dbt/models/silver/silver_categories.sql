-- Catégories de premier niveau ; les sous-catégories (slug parent::enfant) sont rattachées à
-- leur parent dans silver_crate_categories.
select
    slug as category_slug,
    category as category_name
from {{ source('bronze', 'categories') }}
where slug not like '%::%'
