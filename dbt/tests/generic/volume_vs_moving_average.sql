{#
    Signale les jours dont le volume tombe sous min_ratio fois la moyenne du même jour de la
    semaine sur les quatre semaines précédentes. Comparer au même jour neutralise la
    saisonnalité hebdomadaire (un dimanche vaut environ la moitié d'un mardi). Seules les chutes
    sont testées : elles trahissent une perte de données, alors qu'un pic est un événement réel.
#}
{% test volume_vs_moving_average(model, column_name, date_column, min_ratio) %}
with volumes as (
    select
        {{ date_column }} as volume_date,
        {{ column_name }} as volume,
        (
            lag({{ column_name }}, 7) over (order by {{ date_column }})
            + lag({{ column_name }}, 14) over (order by {{ date_column }})
            + lag({{ column_name }}, 21) over (order by {{ date_column }})
            + lag({{ column_name }}, 28) over (order by {{ date_column }})
        ) / 4 as moving_average
    from {{ model }}
)

select *
from volumes
where volume < {{ min_ratio }} * moving_average
{% endtest %}
