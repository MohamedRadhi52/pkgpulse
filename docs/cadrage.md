# Cadrage

## Problème

Prévoir chaque jour le nombre de téléchargements sur crates.io, le registre de paquets Rust, à un
et sept jours. C'est un problème de prévision de la demande comparable au retail : des séries avec
des zéros, une forte saisonnalité hebdomadaire, des effets de nouvelles versions et des pics
exogènes (intégration continue, incidents, annonces).

## Séries cibles

| Niveau | Nombre de séries | Définition |
|---|---|---|
| Total | 1 | Téléchargements de toutes les versions de tous les paquets |
| Catégorie | une par catégorie de premier niveau | Téléchargements des paquets rattachés à la catégorie. Un paquet compte une fois par catégorie de premier niveau et peut appartenir à plusieurs catégories. |
| Paquet | 200 | Les 200 paquets les plus téléchargés du 1er novembre 2025 au 28 février 2026 |

La liste des 200 paquets est figée sur une fenêtre antérieure à la période d'évaluation : choisir
les séries sur toute la période reviendrait à sélectionner des paquets en connaissant leur avenir.

## Moment de prévision et horizons

La prévision est calculée chaque jour juste après la publication du dump quotidien de crates.io.
Le jour du dump n'est compté que jusqu'à l'heure du dump : le dernier jour complet est donc la
veille. En notant T ce dernier jour complet (l'origine de la prévision) :

- J+1 est le jour T+1, c'est-à-dire le jour en cours au moment de la prévision ;
- J+7 est le jour T+7.

## Ce que le modèle a le droit de savoir à l'origine T

- Les téléchargements jusqu'au jour T inclus.
- Le calendrier : jour de la semaine, jours fériés.
- Les versions publiées jusqu'au jour T inclus, avec leur date de publication. Une version publiée
  après T est inconnue, même si elle explique un pic dans la fenêtre prévue.
- Le rattachement des paquets aux catégories.

Rien de postérieur à T n'entre dans les variables : un décalage (lag) utilisé pour prévoir J+h a
au moins h jours. Un test automatisé vérifie qu'aucune donnée postérieure à l'origine n'est lue
pendant le backtest.

Deux approximations sont assumées et mesurées :

- Le backtest utilise les valeurs définitives de l'archive, alors qu'en production la valeur du
  jour T peut encore être corrigée le lendemain (données tardives). L'ingestion journalise chaque
  correction, ce qui permet d'en mesurer l'ampleur.
- Le dump ne donne que les catégories actuelles des paquets. Elles sont appliquées à tout
  l'historique ; elles ne changent qu'à la publication d'une version, et le snapshot dbt garde
  leur évolution à partir du début du projet.

## Métriques

- **MASE** : erreur absolue moyenne de la prévision divisée par l'erreur absolue moyenne du naïf
  saisonnier (même jour de la semaine précédente) sur l'historique d'entraînement. Elle reste
  définie quand une série contient des zéros, contrairement à la MAPE, et se lit directement :
  une MASE inférieure à 1 bat le naïf saisonnier. Elle est calculée par série, puis moyennée par
  niveau et par horizon.
- **Couverture des intervalles à 90 %** : part des valeurs réalisées qui tombent dans l'intervalle
  de prédiction, à comparer à la cible de 90 %, avec la largeur moyenne de l'intervalle.

## Protocole d'évaluation

- Backtest à origine glissante : une origine par semaine à partir du 1er mars 2026, jusqu'au
  dernier jour disponible. À chaque origine, un modèle n'est entraîné que sur les données
  antérieures ou égales à l'origine.
- Références : naïf saisonnier et ETS.
- Deux niveaux de prévision comparés : prévision directe d'un agrégat (total, catégorie) contre
  somme des prévisions par paquet.

## Historique retenu

L'historique commence le 1er novembre 2025. Fin octobre 2025, crates.io a restreint son comptage
aux téléchargements faits par cargo pour écarter les miroirs : le nombre de lignes quotidiennes est
divisé par 2,5 à 4. Le total ne montre pas de rupture nette, mais la longue traîne des petits
paquets, et donc les catégories, change de niveau. Les données antérieures relèvent d'un autre
régime de comptage.

## Hors périmètre

- Réconciliation hiérarchique complète : seuls les niveaux agrégé et paquet sont comparés.
- Enrichissement par d'autres sources (étoiles GitHub, autres registres) : possible plus tard, pas
  nécessaire à la prévision.
