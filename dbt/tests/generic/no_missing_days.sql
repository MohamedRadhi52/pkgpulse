{# Chaque série couvre tous les jours entre son premier et son dernier jour. #}
{% test no_missing_days(model, column_name, partition_by=none) %}
select
    {% if partition_by %}{{ partition_by }},{% endif %}
    min({{ column_name }}) as first_day,
    max({{ column_name }}) as last_day,
    count(distinct {{ column_name }}) as days
from {{ model }}
{% if partition_by %}group by {{ partition_by }}{% endif %}
having {{ dbt.datediff('min(' ~ column_name ~ ')', 'max(' ~ column_name ~ ')', 'day') }} + 1
    != count(distinct {{ column_name }})
{% endtest %}
