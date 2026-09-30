{#
    Sur BigQuery, la couche bronze est lue par des tables externes sur les fichiers Parquet de
    Cloud Storage. En local, DuckDB lit les mêmes fichiers directement (external_location).
#}
{% macro create_bronze_tables(bucket) %}
    {% set files = {
        "version_downloads": "bronze/version_downloads/*.parquet",
        "crates": "bronze/crates.parquet",
        "versions": "bronze/versions.parquet",
        "categories": "bronze/categories.parquet",
        "crates_categories": "bronze/crates_categories.parquet"
    } %}
    {% for table, path in files.items() %}
        {% do run_query(
            "create or replace external table `" ~ target.project ~ ".bronze." ~ table ~ "` "
            ~ "options (format = 'PARQUET', uris = ['gs://" ~ bucket ~ "/" ~ path ~ "'])"
        ) %}
        {% do log("bronze." ~ table ~ " : gs://" ~ bucket ~ "/" ~ path, info=true) %}
    {% endfor %}
{% endmacro %}
