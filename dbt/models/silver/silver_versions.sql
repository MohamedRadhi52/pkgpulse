select
    id as version_id,
    crate_id,
    num as version_number,
    created_at as published_at,
    yanked
from {{ source('bronze', 'versions') }}
