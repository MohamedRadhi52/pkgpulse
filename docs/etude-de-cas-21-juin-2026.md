# Étude de cas : le pic du 21 juin 2026

Le fichier d'archive du dimanche 21 juin 2026 pèse 23,6 Mo, six fois plus qu'un jour ordinaire.
Pic de demande ou artefact, et quel effet sur la prévision ?

## Un pic de largeur, pas de volume

| Dimanche | Versions téléchargées | Dont une seule fois | Téléchargements |
|---|---|---|---|
| 31 mai | 346 865 | 26 % | 573 millions |
| 7 juin | 368 152 | 28 % | 539 millions |
| 14 juin | 400 961 | 28 % | 583 millions |
| 21 juin | 2 437 107 | 83 % | 621 millions |
| 28 juin | 389 106 | 26 % | 692 millions |

Le 21 juin, six fois plus de versions sont téléchargées, mais le total ne dépasse les dimanches
précédents que de 8 %, dans la tendance. Deux millions de versions absentes le dimanche précédent
sont téléchargées une ou deux fois, pour 7 millions de téléchargements en tout, soit 1,1 % du
volume du jour. Elles couvrent tout l'historique du registre : la médiane des identifiants de
version téléchargés bouge à peine (1,32 million, contre 1,28 million le 14 juin).

## Origine probable

Presque tout le registre a été téléchargé une fois, avec le user-agent de cargo, puisque ces
téléchargements ont passé le filtre des miroirs mis en place fin octobre 2025. Un miroir construit
avec cargo ou une compilation de tout l'écosystème sont les hypothèses les plus plausibles ; les
données publiques ne permettent pas de trancher.

## Effet sur la prévision et la détection

- **Total** : aucune alerte le 21 juin (score robuste de 0,75, pour un seuil de 4). La série
  autres, qui porte la longue traîne, reste aussi sous le seuil (0,87).
- **Catégories** : automotive (9,4) et finance (5,3) sont signalées le 21 juin. Ce sont de petites
  catégories, où un téléchargement de plus par version pèse lourd.
- **Paquets suivis** : aucun n'est signalé le 21 juin. Avec des centaines de milliers de
  téléchargements par jour, un de plus par version ne se voit pas. Les séries signalées la veille
  (toml_edit, serde_spanned, quelques catégories) relèvent d'un autre événement, que ces données
  ne suffisent pas à expliquer.

## Leçons

- Le choix des séries (agrégats et paquets les plus téléchargés) rend la prévision robuste à ce
  type d'événement.
- Un indicateur de largeur, comme le nombre de versions téléchargées par jour, serait en revanche
  faussé. Un test dbt sur le nombre de lignes quotidiennes repérerait ce jour-là : c'est une piste
  pour le contrôle qualité.
- La leçon principale de la détection d'anomalies est ailleurs : ses plus gros regroupements
  tombent le 25 mai 2026 (Memorial Day, 238 séries) et le 7 septembre (Labor Day, 42 séries), avec
  un écho une semaine plus tard, quand le jour férié sert de référence au modèle J+1. La demande
  suit le calendrier de travail américain, celui de l'intégration continue des entreprises : des
  variables de jours fériés, connues à l'avance, sont la prochaine amélioration du modèle.
