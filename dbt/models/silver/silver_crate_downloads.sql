select
    versions.crate_id,
    version_downloads.download_date,
    sum(version_downloads.downloads) as downloads
from {{ ref('silver_version_downloads') }} as version_downloads
inner join {{ ref('silver_versions') }} as versions
    on version_downloads.version_id = versions.version_id
group by versions.crate_id, version_downloads.download_date
