# Ponderation Des Terrains Patients

## Objet

Ce document justifie les ponderations proposees pour les terrains patients qui augmentent
le risque de complications deja simulees dans le projet:

- pneumopathie / IRA post-op
- EP / TVP-EP
- sepsis progressif
- hemorragie post-op
- douleur post-op non controlee
- complication cardiaque post-op

Le principe retenu est le suivant:

- quand un score valide existe, on reprend sa logique de points
- sinon, on traduit la force de l'association clinique en poids de simulateur

## Regle De Traduction Vers Le Simulateur

Pour les facteurs non couverts par un score formel unique:

- `+3`: facteur fort
  - score valide avec poids eleve, ou
  - association repetee et forte, souvent OR >= 3, ou
  - facteur explicitement considere comme majeur dans une recommandation
- `+2`: facteur modere
  - association consistante, souvent OR autour de 1.5 a 3
- `+1`: facteur faible mais credible
  - facteur cite dans des recommandations ou des revues, sans niveau de force comparable aux facteurs majeurs

## Scores Valides A Reprendre Tels Quels

### ARISCAT Pour Le Risque Pulmonaire

Source:

- https://pubmed.ncbi.nlm.nih.gov/21045639/
- https://pmc.ncbi.nlm.nih.gov/articles/PMC7047701/

Composants et points:

- age 51-80 ans: `3`
- age >80 ans: `16`
- SpO2 preop 91-95%: `8`
- SpO2 preop <=90%: `24`
- infection respiratoire dans le mois: `17`
- hemoglobine <10 g/dL: `11`
- incision abdominale haute: `15`
- incision intrathoracique: `24`
- duree operatoire 2-3 h: `16`
- duree >3 h: `23`
- urgence: `8`

### Caprini Pour Le Risque TVP/EP

Sources:

- https://www.ahrq.gov/patient-safety/settings/hospital/vtguide/appb2.html
- https://cancersheadneck.biomedcentral.com/articles/10.1186/s41199-016-0014-9/tables/2
- https://pmc.ncbi.nlm.nih.gov/articles/PMC3747284/

Composants utilises dans le simulateur:

- age 41-60 ans: `1`
- age 61-74 ans: `2`
- age >=75 ans: `3`
- BMI >25: `1`
- BPCO / abnormal pulmonary function: `1`
- cancer present ou passe: `2`
- chirurgie majeure >45 min: `2`
- alitement >72 h: `2`
- antecedent TVP/EP: `3`
- arthroplastie majeure membre inferieur: `5`
- fracture de hanche / bassin / jambe: `5`

### RCRI Pour Le Risque Cardiaque

Sources:

- https://www.acc.org/latest-in-cardiology/ten-points-to-remember/2024/09/23/04/15/2024-aha-acc-perioperative-guideline-gl
- https://www.sciencedirect.com/topics/medicine-and-dentistry/revised-cardiac-risk-index

Predicteurs:

- chirurgie a haut risque: `1`
- cardiopathie ischémique: `1`
- insuffisance cardiaque: `1`
- antecedent cerebrovasculaire: `1`
- diabete sous insuline: `1`
- creatinine >2 mg/dL: `1`

Definition de chirurgie a haut risque retenue:

- chirurgie intrathoracique
- chirurgie intraperitoneale
- chirurgie vasculaire sus-inguinale

## Ponderation De Simulateur Par Terrain

## Respiratoire

### age_65_74

- poids propose: `+1`
- justification:
  - l'age augmente le risque pulmonaire dans ARISCAT, mais la marche de points est plus forte surtout au-dela de 80 ans
- source:
  - https://pmc.ncbi.nlm.nih.gov/articles/PMC7047701/

### age_75_plus

- poids propose: `+2`
- justification:
  - l'age avance augmente aussi bien le risque pulmonaire que septique et thromboembolique
  - Caprini donne deja `3` points a >=75 ans pour VTE
- sources:
  - https://pmc.ncbi.nlm.nih.gov/articles/PMC7047701/
  - https://cancersheadneck.biomedcentral.com/articles/10.1186/s41199-016-0014-9/tables/2

### bpco_asthme

- complication principale:
  - pneumopathie / IRA
- poids propose: `+3`
- justification:
  - BPCO est integree dans Caprini comme facteur de risque VTE faible, mais surtout c'est un terrain respiratoire fragilisant
  - les recommandations de risque pulmonaire et les outils comme NSQIP retiennent aussi la BPCO comme variable importante
- sources:
  - https://www.mdpi.com/2077-0383/13/17/5083
  - https://riskcalculator.facs.org/RiskCalculator/about.html

### tabagisme

- complications principales:
  - pneumopathie / IRA
  - douleur post-op
  - sepsis/SSI
- poids propose:
  - pulmonaire `+2`
  - douleur `+1`
  - infectieux `+1`
- justification:
  - facteur consistant pour complications pulmonaires et SSI
  - aussi retrouve dans le risque de douleur persistante / usage prolonge d'opioides
- sources:
  - https://pubmed.ncbi.nlm.nih.gov/37337711/
  - https://journals.lww.com/anesthesia-analgesia/fulltext/2023/07000/practice_advisory_for_preoperative_and.2.aspx

### apnee_sommeil

- complication principale:
  - pneumopathie / IRA
- poids propose: `+2`
- justification:
  - terrain respiratoire de mauvaise reserve; facteur de vigilance reconnu par les recos perioperatoires
- source:
  - https://www.mdpi.com/2077-0383/13/17/5083

### obesite

- complications principales:
  - EP
  - sepsis/SSI
  - respiratoire
- poids propose:
  - EP `+1`
  - infectieux `+2`
  - respiratoire `+1`
- justification:
  - Caprini: BMI >25 = `1` point
  - pour SSI, l'effet est repete, surtout en colorectal et dans les revues
- sources:
  - https://cancersheadneck.biomedcentral.com/articles/10.1186/s41199-016-0014-9/tables/2
  - https://www.cdc.gov/surgical-site-infections/index.html
  - https://www.mdpi.com/2075-1729/14/7/850

## Infectieux / Septique

### diabete

- complications principales:
  - sepsis
  - SSI
  - cardiaque a travers les scores perioperatoires
- poids propose:
  - sepsis `+2`
  - cardiaque `+1`
- justification:
  - facteur repetitif dans CDC/NICE pour sepsis
  - meta-analyse post-op sepsis: OR ~1.41
  - facteur recurrent dans SSI
- sources:
  - https://www.cdc.gov/sepsis/risk-factors/index.html
  - https://pubmed.ncbi.nlm.nih.gov/31172283/
  - https://www.mdpi.com/2075-1729/14/7/850

### immunodepression_ou_steroides

- complication principale:
  - sepsis
- poids propose: `+3`
- justification:
  - CDC et NICE retiennent les immunosuppressions comme terrain majeur
- sources:
  - https://www.cdc.gov/sepsis/risk-factors/index.html
  - https://www.nice.org.uk/guidance/ng51/chapter/1-Guidance

### cancer_actif_ou_recent

- complications principales:
  - EP
  - sepsis
- poids propose:
  - EP `+2`
  - sepsis `+2`
- justification:
  - Caprini donne `2` points a la malignite
  - CDC signale le cancer comme facteur de risque de sepsis
- sources:
  - https://cancersheadneck.biomedcentral.com/articles/10.1186/s41199-016-0014-9/tables/2
  - https://www.cdc.gov/sepsis/risk-factors/index.html

### insuffisance_renale

- complications principales:
  - sepsis
  - hemorragie
  - cardiaque
- poids propose:
  - sepsis `+2`
  - hemorragie `+2`
  - cardiaque `+2`
- justification:
  - meta-analyse sepsis: chronic kidney disease OR ~1.26
  - RCRI: creatinine >2 mg/dL = 1 point
  - meta-analyse anticoagulation-related bleeding: renal failure OR ~1.81
- sources:
  - https://pubmed.ncbi.nlm.nih.gov/31172283/
  - https://www.sciencedirect.com/topics/medicine-and-dentistry/revised-cardiac-risk-index
  - https://pubmed.ncbi.nlm.nih.gov/41557588/

### dependance_fonctionnelle_ou_frailty

- complications principales:
  - sepsis
  - cardiaque
  - EP
- poids propose:
  - sepsis `+2`
  - cardiaque `+2`
  - EP `+2`
- justification:
  - les calculateurs NSQIP et les recommandations perioperatoires geriatriques montrent que la dependance fonctionnelle et la frailty aggravent le risque global
- sources:
  - https://riskcalculator.facs.org/RiskCalculator/about.html
  - https://pubmed.ncbi.nlm.nih.gov/31672676/

## Hemorragique

### anticoagulation

- complication principale:
  - hemorragie
- poids propose: `+3`
- justification:
  - facteur majeur et direct
  - le risque de saignement est nettement accru par l'anticoagulation et par certains antiagregrants
- sources:
  - https://pubmed.ncbi.nlm.nih.gov/29224638/
  - https://pubmed.ncbi.nlm.nih.gov/41557588/

### anemie

- complications principales:
  - hemorragie / mauvaise tolerance du saignement
  - sepsis / SSI
  - respiratoire via ARISCAT si Hb <10
- poids propose:
  - hemorragie `+2`
  - sepsis `+2`
  - respiratoire `+2`
- justification:
  - ARISCAT donne `11` points si Hb <10
  - meta-analyse SSI gastrique: OR ~4.72
  - meta-analyse anticoagulation-related bleeding: OR ~3.24
- sources:
  - https://pmc.ncbi.nlm.nih.gov/articles/PMC7047701/
  - https://pubmed.ncbi.nlm.nih.gov/37337711/
  - https://pubmed.ncbi.nlm.nih.gov/41557588/

## Cardiovasculaire

### coronaropathie

- complication principale:
  - cardiaque post-op
- poids propose: `+3`
- justification:
  - equivalent pratique du predicteur RCRI "ischemic heart disease"
- source:
  - https://www.sciencedirect.com/topics/medicine-and-dentistry/revised-cardiac-risk-index

### insuffisance_cardiaque

- complications principales:
  - cardiaque
  - sepsis aggravation
  - respiratoire reserve reduite
- poids propose:
  - cardiaque `+3`
  - sepsis `+1`
  - respiratoire `+1`
- justification:
  - RCRI: history of heart failure = 1 point
  - meta-analyse postoperative sepsis: OR ~2.53
- sources:
  - https://www.sciencedirect.com/topics/medicine-and-dentistry/revised-cardiac-risk-index
  - https://pubmed.ncbi.nlm.nih.gov/31172283/

### fibrillation_atriale

- complication principale:
  - cardiaque post-op
- poids propose: `+2`
- justification:
  - non incluse dans le RCRI, mais la guideline ACC/AHA 2024 met clairement la FA perioperatoire au premier plan
- source:
  - https://www.acc.org/latest-in-cardiology/ten-points-to-remember/2024/09/23/04/15/2024-aha-acc-perioperative-guideline-gl

## Thromboembolique

### atcd_vte

- complication principale:
  - EP / TVP-EP
- poids propose: `+3`
- justification:
  - Caprini donne `3` points
  - c'est un des facteurs les plus forts et les plus coherents
- sources:
  - https://cancersheadneck.biomedcentral.com/articles/10.1186/s41199-016-0014-9/tables/2
  - https://pmc.ncbi.nlm.nih.gov/articles/PMC3747284/

## Douleur

### douleur_chronique_ou_opioides

- complication principale:
  - douleur post-op non controlee
- poids propose: `+3`
- justification:
  - facteur tres coherent pour douleur persistante et consommation prolongee d'opioides
- sources:
  - https://pubmed.ncbi.nlm.nih.gov/34001769/
  - https://pubmed.ncbi.nlm.nih.gov/39014357/

### anxiete_ou_facteurs_psychiques

- complication principale:
  - douleur post-op non controlee
- poids propose: `+2`
- justification:
  - vulnerabilite psychologique, anxiete, depression et catastrophisme sont des facteurs repetes de douleur persistante post-chirurgicale
- sources:
  - https://pubmed.ncbi.nlm.nih.gov/34001769/
  - https://www.tandfonline.com/doi/full/10.2147/JPR.S557361

## Ponderation De Base Par Chirurgie

Echelle de simulateur:

- `4`: chirurgie tres fortement liee a la complication
- `3`: lien fort
- `2`: lien plausible et regulier
- `1`: lien possible mais moins prioritaire

### Chirurgie Thoracique / Oesophagectomie / Thoracotomie

- pulmonaire `4`
  - justification: incision intrathoracique = `24` points dans ARISCAT
- douleur `4`
  - justification: thoracotomie tres liee a douleur post-op aigue et persistante
- cardiaque `2`
  - justification: chirurgie thoracique = chirurgie a haut risque dans RCRI/ACC
- EP `1`
  - justification: possible mais moins caracteristique que l'orthopedie membre inferieur

Sources:

- https://pmc.ncbi.nlm.nih.gov/articles/PMC7047701/
- https://pubmed.ncbi.nlm.nih.gov/34001769/
- https://www.acc.org/latest-in-cardiology/ten-points-to-remember/2024/09/23/04/15/2024-aha-acc-perioperative-guideline-gl

### Chirurgie Abdominale Haute Ouverte / Gastrectomie

- pulmonaire `3`
  - justification: incision abdominale haute = `15` points ARISCAT
- douleur `3`
  - justification: laparotomie abdominale haute douloureuse
- sepsis `2`
- hemorragie `2`

Sources:

- https://pmc.ncbi.nlm.nih.gov/articles/PMC7047701/
- https://pubmed.ncbi.nlm.nih.gov/37337711/

### Colectomie / Chirurgie Colorectale / Resection Anterieure Basse

- sepsis `4`
  - justification: chirurgie colorectale tres representee dans les complications infectieuses/septiques
- hemorragie `3`
- pulmonaire `2`
- EP `2`

Sources:

- https://pubmed.ncbi.nlm.nih.gov/35371356/
- https://www.mdpi.com/2075-1729/14/7/850
- https://pmc.ncbi.nlm.nih.gov/articles/PMC3747284/

### Pancreatectomie

- sepsis `4`
- hemorragie `4`
- pulmonaire `2`
- cardiaque `2`

Justification:

- la pancreatectomie est une chirurgie majeure avec risque important de fistule, sepsis secondaire et hemorrage retardee

Sources:

- https://pubmed.ncbi.nlm.nih.gov/26929287/
- https://pubmed.ncbi.nlm.nih.gov/24448997/

### Hepatectomie

- hemorragie `4`
- sepsis `3`
- pulmonaire `2`
- cardiaque `2`

Justification:

- chirurgie majeure avec risque hemorragique intrinseque et complications infectieuses associees

Sources:

- https://pubmed.ncbi.nlm.nih.gov/24722780/
- https://pubmed.ncbi.nlm.nih.gov/22762398/

### Arthroplastie Genou / Hanche / Fracture De Hanche

- EP `4`
  - justification: Caprini attribue `5` points a arthroplastie majeure membre inferieur et fracture hanche/bassin/jambe
- douleur `2`
- hemorragie `2`
- cardiaque `2`

Sources:

- https://cancersheadneck.biomedcentral.com/articles/10.1186/s41199-016-0014-9/tables/2
- https://sfar.org/prevention-de-la-maladie-thromboembolique-veineuse-peri-operatoire/

### Chirurgie Pelvienne Oncologique

- EP `3`
- sepsis `2`
- hemorragie `2`
- douleur `2`

Justification:

- chirurgie pelvienne et cancer augmentent le risque thromboembolique et infectieux

Sources:

- https://cancersheadneck.biomedcentral.com/articles/10.1186/s41199-016-0014-9/tables/2
- https://www.cdc.gov/sepsis/risk-factors/index.html

### Chirurgie Vasculaire Majeure

- cardiaque `4`
  - justification: haut risque dans RCRI / ACC-AHA
- hemorragie `3`
- EP `2`
- pulmonaire `2`

Sources:

- https://www.sciencedirect.com/topics/medicine-and-dentistry/revised-cardiac-risk-index
- https://www.acc.org/latest-in-cardiology/ten-points-to-remember/2024/09/23/04/15/2024-aha-acc-perioperative-guideline-gl

### Bypass Bariatrique

- EP `3`
- pulmonaire `2`
- sepsis `2`

Justification:

- l'obesite et la chirurgie abdominale majeure renforcent le risque thromboembolique et respiratoire

Sources:

- https://riskcalculator.facs.org/RiskCalculator/about.html
- https://cancersheadneck.biomedcentral.com/articles/10.1186/s41199-016-0014-9/tables/2

## A Retenir

- `ARISCAT`, `Caprini` et `RCRI` peuvent etre repris quasiment tels quels
- `sepsis`, `hemorragie` et `douleur` demandent des poids de simulateur derives des recommandations et meta-analyses
- les poids proposes ici sont faits pour la plausibilite clinique et la simulation, pas pour remplacer un score medical certifie
