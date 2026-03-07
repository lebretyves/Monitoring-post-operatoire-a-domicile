# Generation des cas

Cette fiche explique comment le projet genere les cas cliniques au `refresh`, combien de cas sont possibles, et comment sont combines:

- le cas clinique
- le jour post-op (`J0 -> J3`)
- la chirurgie
- le type d'apparition de la complication
- le temps clinique courant observe

## 1. Ce qu'est un "cas"

Dans [cases_catalog.json](c:\Users\lebre\Desktop\Monitoring\postop-monitoring\config\cases_catalog.json), un cas contient:

- une complication ou un etat sain
- une chirurgie de reference
- une baseline physiologique normale
- une trajectoire clinique qui part de `J0`
- des probabilites de jours `J0 -> J3`
- un pool de chirurgies compatibles

## 2. Nombre de cas actuellement definis

Il y a `9` cas au total:

- `1` cas sain
  - `case_stable_reference`
- `8` cas de complication
  - `case_pneumonia_hip`
  - `case_hemorrhage_colectomy`
  - `case_hemorrhage_low_grade`
  - `case_pe_knee`
  - `case_sepsis_colorectal`
  - `case_pain_postop`
  - `case_cardiac_postop`
  - `case_cardiac_postop_slow`

Donc:

- `9 cas catalogue`
- `8 complications / variantes`

## 3. Nombre de combinaisons "cas + jour post-op"

Chaque cas peut etre tire avec un jour post-op parmi:

- `J0`
- `J1`
- `J2`
- `J3`

Les jours sont ponderes, mais les 4 jours existent dans le modele.

Calcul theorique:

- `9 cas`
- `4 jours`
- `9 x 4 = 36` combinaisons `cas + jour`

## 4. Nombre de combinaisons "cas + jour + chirurgie"

Chaque cas pathologique a un `surgery_pool`.

Nombre de chirurgies possibles par cas:

- `case_stable_reference` = `1`
- `case_pneumonia_hip` = `7`
- `case_hemorrhage_colectomy` = `7`
- `case_hemorrhage_low_grade` = `6`
- `case_pe_knee` = `6`
- `case_sepsis_colorectal` = `6`
- `case_pain_postop` = `6`
- `case_cardiac_postop` = `7`
- `case_cardiac_postop_slow` = `6`

Calcul theorique:

- cas sain: `1 chirurgie x 4 jours = 4`
- autres cas:
  - `7 x 4 = 28`
  - `7 x 4 = 28`
  - `6 x 4 = 24`
  - `6 x 4 = 24`
  - `6 x 4 = 24`
  - `6 x 4 = 24`
  - `7 x 4 = 28`
  - `6 x 4 = 24`

Total:

- `4 + 28 + 28 + 24 + 24 + 24 + 24 + 28 + 24 = 208`

Donc il y a actuellement `208` combinaisons theoriques `cas + jour + chirurgie`.

## 5. Pourquoi ce n'est pas uniforme

Le systeme ne tire pas toutes les combinaisons avec la meme frequence.

### Chirurgie

Les chirurgies sont tirees avec la ponderation:

- `strong = 70`
- `medium = 20`
- `weak = 10`

Donc les chirurgies les plus plausibles sortent plus souvent.

### Jour post-op

Chaque cas a aussi un `postop_day_weights`.

Exemple:

- douleur post-op:
  - `J0 = 40`
  - `J1 = 35`
  - `J2 = 15`
  - `J3 = 10`
- sepsis:
  - `J0 = 5`
  - `J1 = 15`
  - `J2 = 35`
  - `J3 = 45`

Donc:

- douleur sort plus souvent a `J0/J1`
- sepsis sort plus souvent a `J2/J3`

### Temps clinique courant

Le `refresh` ne cree plus un patient "deja malade a J2".

Il tire:

- une chirurgie compatible
- une complication plausible
- un jour post-op observe `J0 -> J3`
- un temps clinique courant aleatoire a l'interieur de ce jour

Ensuite, le simulateur reconstruit l'histoire complete:

- depart sur une baseline normale a `J0`
- apparition de la complication plus tard selon sa cinetique
- trajectoire continue jusqu'au temps courant observe

## 6. Ce que fait reellement le bouton Refresh

Le `refresh` ne montre pas les `208` combinaisons d'un coup.

A chaque refresh:

- `1` slot reste le patient temoin sain
- `4` slots tirent `4` cas pathologiques du catalogue
- chaque cas tire:
  - une chirurgie compatible
  - un jour post-op compatible

Donc l'ecran affiche toujours:

- `5 patients simultanes`
- mais issus d'un espace beaucoup plus large de combinaisons

## 7. Progressif vs brutal

Le moteur distingue deux grandes logiques:

### Complications progressives

Exemples:

- `pneumonia_ira`
- `sepsis_progressive`
- `hemorrhage_low_grade`
- `cardiac_postop_slow`

Principe:

- le patient part normal a `J0`
- la complication apparait puis se construit progressivement
- plus on observe tard dans `J0 -> J3`, plus une partie de la degradation a deja eu le temps de se produire
- le graphe peut donc montrer une derive lente sur plusieurs heures/jours cliniques simules

### Complications brutales

Exemples:

- `pulmonary_embolism`
- `hemorrhage_j2`
- `cardiac_postop_complication`

Principe:

- elles peuvent survenir a n'importe quel moment pendant la surveillance
- le simulateur tire un `onset_delay_range_minutes`
- donc l'evenement ne part pas toujours au meme moment apres `J0`

## 8. Ce que cela veut dire pour la demo

Le projet ne montre pas seulement `un scenario fixe par patient`.

Il montre:

- des patients observes a un temps courant entre `J0` et `J3`
- des complications plausibles selon la chirurgie
- des complications lentes ou brutales
- une trajectoire clinique reconstruite depuis `J0`
- une variabilite controllable mais non completement repetitive

## 9. Resume court

- `9` cas catalogue
- `8` complications / variantes
- `36` combinaisons `cas + jour`
- `208` combinaisons `cas + jour + chirurgie`
- `5` patients visibles en meme temps a chaque refresh
- `1` temoin sain
- `4` cas pathologiques tires aleatoirement avec ponderations
- tous les cas commencent a `J0`, puis sont observes a un temps clinique aleatoire entre `J0` et `J3`
