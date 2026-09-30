{# Schémas silver, gold et snapshots nommés tels quels, sans préfixe de la cible. #}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {{ custom_schema_name or target.schema }}
{%- endmacro %}
