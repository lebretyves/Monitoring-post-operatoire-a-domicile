# Questionnaire Differentiel Post-op a Domicile

## Objet

Ce document decrit un arbre de questions simple pour completer les constantes vitales
et aider a departager les complications post-operatoires deja exploitees dans le simulateur.

Il ne modifie pas le simulateur.
Il sert de base de raisonnement pour:

- le LLM
- un futur formulaire patient / IDE
- la soutenance du projet

Complications couvertes:

- pneumopathie / IRA post-op
- embolie pulmonaire / TVP-EP
- sepsis / complication infectieuse
- hemorragie post-op
- douleur post-op non controlee
- complication cardiaque post-op

## Principe general

Le raisonnement se fait en 3 niveaux:

1. donnees objectives
2. questionnaire tronc commun
3. modules differenciels si plusieurs hypotheses restent proches

## Niveau 1 - Donnees objectives

Avant tout questionnaire, on utilise:

- FC
- SpO2
- TA / TAM
- FR
- T C
- historique depuis J0
- alertes
- chirurgie
- jour post-op

Ces donnees servent a produire une premiere orientation:

- respiratoire
- thromboembolique
- infectieuse
- hemorragique
- douleur
- cardiaque

## Niveau 2 - Questionnaire tronc commun

Ces questions sont les plus utiles, quel que soit le scenario.

### Q1. Dyspnee

- non
- oui, brutale
- oui, progressive

Utile pour:

- EP
- pneumopathie / IRA
- cardiaque

### Q2. Douleur thoracique

- non
- oui, oppressive
- oui, pleurale / a l'inspiration
- oui, surtout a la toux

Utile pour:

- cardiaque
- EP
- pneumopathie

### Q3. Fievre ou frissons

- non
- oui

Utile pour:

- sepsis
- pneumopathie
- infection de plaie

### Q4. Malaise / perte de connaissance

- non
- oui

Utile pour:

- EP
- hemorragie
- cardiaque

### Q5. Douleur a la mobilisation

- non
- oui, faible
- oui, moderee
- oui, importante

Utile pour:

- douleur post-op
- complication locale

### Q6. Rougeur de plaie

- non
- oui

Utile pour:

- infection de site operatoire
- sepsis

### Q7. Ecoulement / suppuration de plaie

- non
- oui

Utile pour:

- infection de site operatoire
- sepsis

### Q8. Saignement visible / pansement sature

- non
- oui

Utile pour:

- hemorragie

## Niveau 3 - Modules differenciels

Ces questions ne sont posees que si l'analyse initiale hesite entre plusieurs hypotheses.

## Module A - EP vs Pneumopathie / IRA

Questions:

- debut brutal ou progressif ?
- douleur thoracique a l'inspiration ?
- toux ?
- expectoration ?
- hemoptysie ?
- douleur ou gonflement d'un mollet ?

Oriente plutot vers EP:

- debut brutal
- douleur pleurale
- hemoptysie
- mollet douloureux ou gonfle

Oriente plutot vers pneumopathie / IRA:

- debut progressif
- toux
- expectoration
- fievre ou frissons

## Module B - Sepsis vs Douleur post-op

Questions:

- frissons ?
- fievre repetee ?
- rougeur de plaie ?
- ecoulement de plaie ?
- brulures urinaires ?
- douleurs abdominales inhabituelles ?
- aggravation surtout a la mobilisation ?

Oriente plutot vers sepsis:

- fievre ou frissons
- foyer infectieux visible
- signes urinaires
- douleurs abdominales inhabituelles

Oriente plutot vers douleur post-op:

- douleur surtout mecanique
- aggravation a la mobilisation, a la toux ou a l'inspiration
- pas de syndrome infectieux net

## Module C - Hemorragie vs Cardiaque

Questions:

- saignement visible ?
- pansement sature ?
- douleurs abdominales inhabituelles ?
- malaise / syncope ?
- douleur thoracique oppressive ?
- palpitations / rythme irregulier ?

Oriente plutot vers hemorragie:

- saignement visible
- pansement sature
- douleurs abdominales
- malaise avec signes de perte sanguine

Oriente plutot vers cardiaque:

- douleur thoracique oppressive
- palpitations
- dyspnee sans argument infectieux ou hemorragique fort

## Module D - Respiratoire infectieux vs Sepsis

Questions:

- toux ?
- expectoration ?
- frissons ?
- rougeur ou ecoulement de plaie ?
- brulures urinaires ?
- douleurs abdominales ?

Oriente plutot vers pneumopathie / IRA:

- toux
- expectoration
- dyspnee progressive
- douleur thoracique a la respiration ou a la toux

Oriente plutot vers sepsis:

- foyer infectieux de plaie
- signes urinaires
- douleurs abdominales
- syndrome infectieux plus general

## Module E - Douleur post-op vs complication organique

Questions:

- douleur au repos ?
- douleur a la toux ?
- douleur a l'inspiration profonde ?
- douleur a la mobilisation ?
- amelioration apres repos / antalgie ?

Oriente plutot vers douleur post-op:

- douleur liee au mouvement
- douleur a la toux
- douleur a l'inspiration profonde
- amelioration avec repos / antalgie

Oriente plutot contre douleur seule:

- hypoxemie importante
- fievre franche
- hypotension
- saignement visible

## Arbre global simplifie

```text
Constantes + historique + alertes
        |
        v
Questionnaire tronc commun
        |
        +--> hypothese assez claire -> synthese + surveillance
        |
        `--> hypotheses proches -> module differentiel cible
                                   |
                                   +--> EP vs pneumopathie
                                   +--> sepsis vs douleur
                                   +--> hemorragie vs cardiaque
                                   +--> respiratoire infectieux vs sepsis
                                   `--> douleur vs complication organique
```

## Recommandation d'usage

Pour une premiere version UI:

- afficher seulement le tronc commun en permanence
- declencher les modules differenciels seulement si:
  - le LLM hesite
  - ou les alertes et constantes orientent vers plusieurs hypotheses

Ainsi:

- le formulaire reste court
- l'analyse reste plus differenciante
- la demo reste lisible
