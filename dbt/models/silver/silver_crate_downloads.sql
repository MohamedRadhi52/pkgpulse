select
    versions.crate_id,
    downloads.download_date,
    sum(downloads.downloads) as downloads
from {{ ref('silver_version_downloads') }} as downloads
inner join {{ ref('silver_versions') }} as versions
    on downloads.version_id = versions.version_id
group by versions.crate_id, downloads.download_date
