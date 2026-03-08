# Clinical References

Ce fichier centralise les references externes utilisees pour:

- calibrer les scenarios cliniques
- relier une complication post-op a des familles de chirurgie plausibles
- documenter les choix de documentation du projet

## Methode documentaire

Bonnes pratiques retenues pour ce projet:

- fichier dedie dans `docs/` pour eviter de disperser les sources
- liens descriptifs et classes par theme
- peu de notes en bas de page; explication courte directement dans la liste
- URLs absolues et stables

References de methode:

- [Google Developer Documentation Style Guide, Cross-references and linking][google-links]
  Recommande des liens selectifs et descriptifs.
- [Google Developer Documentation Style Guide, Footnotes][google-footnotes]
  Recommande d'eviter les notes de bas de page quand une note ou une section dediee suffit.
- [Microsoft Learn Contributor Guide, Use links in documentation][ms-links]
  Recommande les liens descriptifs et les reference-style links quand le Markdown devient long.

## IA medicale, prudence clinique et confidentialite

Ces sources soutiennent les consignes ajoutees dans les prompts LLM du projet:

- [WHO, safe and ethical AI for health][who-safe-ai]
  Utilise pour justifier les garde-fous de securite, les risques d'hallucination et le besoin de supervision humaine.
- [WHO, ethics and governance guidance for large multimodal models][who-lmm]
  Utilise pour soutenir la prudence sur l'usage de modeles generatifs en sante et la necessite de controles documentes.
- [FDA, clinical decision support software][fda-cds]
  Utilise pour cadrer une aide a l'orientation clinique non directive, transparente et non substitutive a la decision du clinicien.
- [CNIL, IA et sante: developper et evaluer des systemes conformes][cnil-ia-sante]
  Utilise pour justifier la minimisation des donnees, la maitrise des risques et la conformite RGPD.
- [CNIL, recommandations pour le developpement des systemes d'IA][cnil-ia]
  Utilise pour soutenir la transparence, la gouvernance et la documentation des systemes IA.
- [Commission europeenne, data minimisation under GDPR][ec-data-min]
  Utilise pour soutenir le choix de pseudonymisation, de limitation de finalite et de minimisation des donnees dans le prompt et l'architecture.
- [HAS, IA en contexte de soins: accompagner les usages][has-ia-soins]
  Utilise pour justifier un positionnement d'outil d'aide, prudent, documente et integre au contexte de soins.

## Alerte precoce, escalation et reduction des faux positifs

Ces sources ont servi pour comparer notre approche a ce qui se fait classiquement dans les systemes d'alerte:

- [RCP, NEWS2][rcp-news2]
  Utilise pour soutenir un modele d'alertes graduees, fonde sur les constantes et associe a une reponse proportionnee.
- [RCP, NEWS2 chart 2 thresholds and triggers][rcp-news2-chart2]
  Utilise pour soutenir la notion de seuils progressifs et de reponse differenciee selon la gravite.
- [RCP, NEWS2 additional guidance on escalation and response][rcp-news2-escalation]
  Utilise pour soutenir l'idee de frequence de remesure differenciee selon le niveau de risque.
- [AHRQ PSNet, Alert Fatigue][ahrq-alert-fatigue]
  Utilise pour justifier la reduction des alertes peu specifiques, la hierarchisation par severite et l'ajout d'un contexte d'incertitude.
- [NICE NG51 sepsis][nice-sepsis]
  Utilise pour soutenir une lecture prudente des scores et seuils, toujours interpretes avec le contexte clinique.

### Recommandations retenues pour les alertes simples

Le projet conserve les alertes combinees pour la specificite clinique, mais ajoute aussi des alertes simples
pour deux raisons:

- detecter plus tot une derive isolee mais cliniquement utile
- donner au LLM des signaux d'orientation pour le diagnostic differentiel avant confirmation par combinaison ou tendance

Recommandations implementees:

- `TEMP_INFO`: `T >= 38.0`
- `TEMP_WARNING`: `T >= 38.5`
- `TEMP_LOW_WARNING`: `T < 36.0`
- `RR_INFO`: `FR >= 22`
- `RR_WARNING`: `FR >= 25`
- `SBP_INFO`: `SBP <= 100`
- `SBP_CRITICAL`: `SBP <= 90`
- `FC_INFO`: `FC >= 110`
- `FC_WARNING`: `FC >= 130`
- `SpO2` et `TAM` restent surveillees comme avant

Logique retenue:

- `alertes simples` = signal precoce, aide au tri et au LLM
- `alertes combinees` = signal plus specifique, moins sensible aux faux positifs
- `alertes de tendance` = degradation dans le temps, essentielle pour le postop a domicile

Sites utilises pour justifier cette approche:

- [RCP, NEWS2][rcp-news2]
  Chaque constante vitale est interpretee individuellement avant combinaison dans un score global.
- [RCP, NEWS2 report PDF][rcp-news2-chart2]
  Confirme l'importance de seuils simples par parametre, y compris pour RR, SBP, FC et temperature.
- [NICE sepsis][nice-sepsis]
  Utilise des seuils simples de RR, SBP, temperature et etat clinique en soins primaires/communautaires.
- [ameli - retour domicile apres coelioscopie][ameli-coelioscopie]
  Justifie qu'une fievre, un saignement, une douleur thoracique ou une aggravation clinique isolee sont deja des signaux a domicile.
- [ameli - essoufflement recent][ameli-essoufflement]
  Renforce l'interet de reperer precocement une derive respiratoire meme avant combinaison complete.

Utilisation retenue par le LLM:

- une alerte simple n'est pas consideree comme un diagnostic
- elle sert a orienter les hypotheses et a proposer des questions differentielles pertinentes
- une alerte combinee ou une tendance persistante augmente ensuite la confiance et la priorite

## Comparaison avec des dashboards open source

Ces projets sont utiles comme comparaison technique d'interface, mais ne servent pas de reference clinique:

- [CardinalKit SMART-on-FHIR dashboard][github-cardinalkit]
  Exemple de dashboard clinique React oriente visualisation de donnees patients.
- [HomeICU remote vital signs monitor][github-homeicu]
  Exemple de monitoring de signes vitaux avec seuils et alertes a distance.
- [Smart health monitoring system][github-smart-monitoring]
  Exemple de dashboard temps reel avec constantes et alertes, sans couche explicite d'incertitude clinique.

## Respiratoire: pneumopathie, IRA, hypoxemie post-op

- [MAPAR, Hypoxemie postoperatoire - Cas clinique][mapar-hypox]
  Utilise pour justifier une degradation d'abord respiratoire, avec hypotension secondaire en cas d'aggravation.
- [HUG, Strategie pneumonie 2024][hug-pneumonie]
  Utilise pour les signes de gravite respiratoire comme `SpO2 < 90`, `FR > 30`, `PAS < 90` ou `PAD < 60`.
- [PubMed, postoperative pulmonary complications after upper abdominal surgery][pubmed-upper-abd-risk]
  Utilise pour soutenir le lien fort entre chirurgie abdominale haute et complications pulmonaires post-op.
- [PubMed, diaphragmatic ultrasound and postoperative pulmonary complications after upper abdominal surgery][pubmed-upper-abd-2025]
  Utilise comme source recente sur la frequence des complications pulmonaires apres chirurgie abdominale haute.
- [PubMed, thoracic surgery pulmonary complications meta-analysis][pubmed-thoracic-ppc]
  Utilise pour soutenir le lien fort entre chirurgie thoracique et complications respiratoires post-op.

## Thromboembolique: TVP / embolie pulmonaire

- [SFAR, Prevention de la maladie thromboembolique veineuse peri-operatoire][sfar-vte]
  Utilise comme base francaise pour relier EP/TVP aux chirurgies orthopediques, pelviennes et a certaines chirurgies majeures.
- [PubMed, VTE after hip and knee replacement surgery][pubmed-tha-tka-vte-risk]
  Utilise pour justifier le poids fort des arthroplasties de hanche et de genou dans le mapping EP.
- [PubMed, frailty and VTE after THA/TKA][pubmed-frailty-tha-tka]
  Utilise comme source recente soutenant encore le lien THA/TKA <-> VTE/EP.
- [PubMed, VTE prophylaxis after hip and knee arthroplasty][pubmed-aspirin-arthro]
  Utilise comme source complementaire sur le contexte VTE en arthroplastie.

## Sepsis post-op et chirurgie associee

- [Surviving Sepsis Campaign Guidelines 2021][sccm-sepsis]
  Utilise pour les notions de choc distributif et de cible `MAP >= 65`.
- [PubMed, interventional surveillance lowers postoperative infection rates in elective colorectal surgery][pubmed-colorectal-ssi-2022]
  Utilise pour soutenir le lien fort entre chirurgie colorectale et complications infectieuses post-op.
- [PubMed, colorectal SSI risk factors meta-analysis][pubmed-colorectal-meta-2022]
  Utilise pour soutenir le caractere frequent et structure des infections post-op en chirurgie colorectale.
- [PubMed, colorectal surgery prevention bundles scoping review][pubmed-colorectal-bundle-2024]
  Utilise comme source recente sur la charge infectieuse et les bundles de prevention en chirurgie colorectale.

## Hemorragie et hemodynamique

- [SFAR, Choc hemorragique peri- et/ou post-operatoire][sfar-hemorrhage]
  Utilise comme ancrage francais pour les scenarios d'hemorragie et d'hypotension severe.
- [PMC, managing acute upper gastrointestinal bleeding][pmc-ugib]
  Utilise pour soutenir la sequence clinique `tachycardie -> hypotension -> choc hypovolemique`.
- [PubMed, perioperative hemodynamic and blood pressure variability review][pubmed-bpv]
  Utilise en appui general pour la prudence sur les trajectoires tensionnelles et la coherence hemodynamique.

## Douleur post-op

- [SFAR, Mise au point sur l'utilisation de la ketamine][sfar-ketamine]
  Utilise pour soutenir le choix d'un scenario de douleur post-op importante, notamment dans les chirurgies connues pour etre tres douloureuses.
- [PubMed, pain after thoracotomy randomized trial][pubmed-thoracotomy-rct]
  Utilise pour soutenir le choix de la thoracotomie comme chirurgie fortement associee a la douleur post-op.
- [PubMed, chronic pain after thoracotomy meta-analysis][pubmed-thoracotomy-meta]
  Utilise pour soutenir le poids fort de la chirurgie thoracique dans le mapping douleur.
- [PubMed, audit of postoperative pain after open thoracotomy][pubmed-thoracotomy-audit]
  Utilise pour renforcer le lien entre douleur aiguë importante et suites compliquees apres thoracotomie.

## Complications cardiaques post-op

- [PubMed, perioperative cardiovascular risk assessment and management for noncardiac surgery][pubmed-cv-review]
  Utilise pour relier le risque cardiovasculaire peri-operatoire aux chirurgies non cardiaques majeures.
- [PubMed, perioperative myocardial injury in vascular surgery][pubmed-vascular-pmi-2023]
  Utilise pour justifier le poids fort de la chirurgie vasculaire dans le scenario cardiaque post-op.
- [PubMed, incidence and implications of perioperative myocardial injury in vascular surgery][pubmed-vascular-pmi-2016]
  Utilise comme source complementaire sur la forte incidence des atteintes myocardiques en chirurgie vasculaire.
- [PubMed, risk factors associated with perioperative MI in major open vascular surgery][pubmed-open-vascular-mi]
  Utilise pour justifier que la chirurgie vasculaire ouverte reste une chirurgie de reference pour le scenario cardiaque.
- [ACC, high-risk vascular surgery trial summary][acc-vascular]
  Utilise comme source cardiologique complementaire sur le risque peri-operatoire en chirurgie vasculaire majeure.

## References historiques du JSON source d'alertes

Ces sources viennent du JSON clinique source fourni pour les regles et seuils. Elles restent utiles pour la tracabilite du projet.

- [SFAR, recommandations sur la reanimation du choc hemorragique][sfar-hemo-guideline]
- [SSCM/ESICM, Surviving Sepsis Campaign 2021 PDF][ssc-pdf]
- [SCCM, Surviving Sepsis Guidelines 2021 summary][ssc-web]
- [ESC/ERS, acute pulmonary embolism guidelines 2019][esc-pe]
- [ESC high-risk pulmonary embolism summary][esc-pe-high]
- [MAPAR, Hypoxemie postoperatoire][mapar-hypox]
- [MAPAR, hypoxemie et hypotension sur 72h post-op][mapar-72h]
- [Scientific Reports, Shock Index definition and evaluation][shock-index]
- [PMC, acute upper GI bleeding review][pmc-ugib]
- [NHS, acute upper GI bleed guideline][nhs-augib]
- [SFAR/associated publication, ambulatory discharge SpO2 threshold example][sfar-spo2]

## Regle de maintenance

- Ajouter une source seulement si elle soutient une decision de scenario, de regle ou de mapping chirurgie/complication.
- Preferer les societes savantes, recommandations, hopitaux universitaires et revues indexees.
- Si une source sert a une affirmation precise, ajouter une note de une ligne expliquant ce qu'elle soutient.

## Donnees manquantes utiles au domicile

Dans le cadre du sujet `monitoring post-operatoire a domicile`, il faut privilegier
des informations realistes, observables par le patient, un proche ou un soignant non specialiste.

Le tableau ci-dessous retient des champs compatibles avec un suivi a domicile, sans examen
expert ni biologie.

| Champ | Type de reponse | Complications aidees | Priorite | Sources francaises |
| --- | --- | --- | --- | --- |
| Dyspnee brutale ou progressive | Choix simple | EP, pneumopathie/IRA, cardiaque | Haute | [ameli - essoufflement recent][ameli-essoufflement], [ameli - embolie pulmonaire][ameli-ep] |
| Douleur thoracique | Oui/Non + type libre court | EP, cardiaque, pneumopathie | Haute | [ameli - douleur thoracique urgente][ameli-douleur-thoracique], [ameli - embolie pulmonaire][ameli-ep] |
| Toux | Oui/Non | Pneumopathie/IRA | Haute | [ameli - essoufflement recent][ameli-essoufflement], [nice - pneumonia information][nice-pneumonia-public] |
| Expectoration / crachats | Oui/Non | Pneumopathie/IRA | Haute | [ameli - essoufflement recent][ameli-essoufflement], [IDSA CAP pathway][idsa-cap-pathway] |
| Crachats sanglants / hemoptysie | Oui/Non | EP, complication respiratoire severe | Haute | [ameli - embolie pulmonaire][ameli-ep] |
| Fievre recente / frissons | Oui/Non | Sepsis, pneumopathie, infection de plaie | Haute | [ameli - coelioscopie][ameli-coelioscopie], [nice-sepsis][nice-sepsis] |
| Rougeur de plaie | Oui/Non | Sepsis, infection de site operatoire | Haute | [ameli - soigner une plaie][ameli-plaie], [CDC SSI][cdc-ssi] |
| Ecoulement / suppuration de plaie | Oui/Non | Sepsis, infection de site operatoire | Haute | [ameli - soigner une plaie][ameli-plaie], [CDC SSI][cdc-ssi] |
| Saignement visible / pansement sature | Oui/Non | Hemorragie | Haute | [ameli - coelioscopie][ameli-coelioscopie], [AHRQ postoperative hemorrhage][ahrq-hemorrhage] |
| Douleur ou gonflement d'un mollet | Oui/Non | TVP / EP | Haute | [ameli - phlebite][ameli-phlebite], [ameli - coelioscopie][ameli-coelioscopie] |
| Malaise / perte de connaissance | Oui/Non | EP, cardiaque, hemorragie severe | Haute | [ameli - embolie pulmonaire][ameli-ep], [ameli - infarctus][ameli-infarctus] |
| Douleur a la mobilisation | Echelle simple 0-10 ou Oui/Non | Douleur post-op, hemorragie locale | Moyenne | [ameli - arthroscopie][ameli-arthroscopie], [PubMed postop pain function][pubmed-postop-pain-function] |
| Douleur a la toux ou a l'inspiration profonde | Oui/Non | Douleur post-op, pneumopathie, EP | Moyenne | [PubMed postop pain cough][pubmed-postop-pain-cough], [ameli - douleur thoracique urgente][ameli-douleur-thoracique] |
| Vomissements | Oui/Non | Sepsis, complication abdominale, aggravation generale | Moyenne | [ameli - coelioscopie][ameli-coelioscopie] |
| Brulures urinaires | Oui/Non | Infection / sepsis | Moyenne | [ameli - coelioscopie][ameli-coelioscopie] |
| Douleurs abdominales inhabituelles | Oui/Non | Sepsis abdominal, hemorragie, complication digestive | Moyenne | [ameli - coelioscopie][ameli-coelioscopie] |

Principes de selection retenus:

- rester sur des informations observables a domicile
- ne pas demander d'examen expert ou de biologie
- prioriser les donnees qui aident a departager des hypotheses proches
- conserver un nombre de champs raisonnable pour la demo

## Recalibrage temporel du simulateur

Le recalibrage du 7 mars 2026 suit une logique de priorisation des sources primaires. Nous n'avons pas retenu un scraping massif et heterogene de "100 sites", car cela degrade la qualite methodologique en medical. La calibration repose plutot sur les references deja documentees ci-dessus, avec compression du temps clinique reel vers un temps de demo.

Principe retenu:

- conserver l'ordre physiopathologique des evenements
- conserver une logique `chirurgie + jour post-op + complication plausible`
- compresser l'observation pour la demo sans casser le sens clinique des jours `J0 -> J3`
- garder les scenarios brutaux comme brutaux
- ralentir les scenarios progressifs pour qu'ils ne se stabilisent plus en moins d'une minute

Implementation retenue:

- le `refresh` tire maintenant un `jour post-op` aleatoire `J0 -> J3` pour chaque cas
- ce tirage est pondere par complication dans `cases_catalog.json`
- les scenarios progressifs utilisent des `initial_shift_by_postop_day` pour representer un etat deja plus avance a `J2/J3`
- les scenarios abrupts utilisent un `onset_delay_range_minutes` aleatoire, pour pouvoir survenir a n'importe quel moment pendant la surveillance

Choix retenus par complication:

- `pneumonia_ira`
  - base documentaire: MAPAR hypoxemie post-op, HUG pneumonie, litterature chirurgie thoracique et abdominale haute
  - lecture retenue: la degradation est d'abord respiratoire
  - ordre attendu: `SpO2` puis `FR`, puis `FC`, puis baisse tensionnelle moderee secondaire
  - traduction simulateur: progression `J0 -> J1 -> J2 -> J3` compressee dans la demo, avec aggravation respiratoire de plus en plus marquee

- `pulmonary_embolism`
  - base documentaire: recommandations ESC/ERS et SFAR thromboembolique
  - lecture retenue: evenement souvent brutal, avec desaturation, tachycardie, tachypnee; l'hypotension severe signe la gravite
  - ordre attendu: saut precoce `SpO2/FR/FC`, puis instabilite persistante
  - traduction simulateur: saut initial immediat, puis poursuite sur quelques minutes au lieu d'un plateau quasi instantane

- `sepsis_progressive`
  - base documentaire: Surviving Sepsis Campaign 2021, NICE sepsis
  - lecture retenue: debut souvent progressif, avec `T°C`, `FC`, `FR`, puis vasoplegie; la `DBP` peut baisser avant la `SBP`
  - ordre attendu: inflammation precoce, puis chute `DBP`, puis baisse de `TAM`
  - traduction simulateur: progression `J0 -> J1 -> J2 -> J3` compressee, avec phase inflammatoire lente puis bascule vasoplegique

- `hemorrhage_j2`
  - base documentaire: SFAR choc hemorragique, revue UGIB
  - lecture retenue: phase compensee avec tachycardie et pression encore relativement preservee, puis decompensation plus brutale
  - ordre attendu: `FC` et `FR` montent, `SBP` baisse discretement; ensuite chute hemodynamique plus rapide
  - traduction simulateur: deux variantes
    - `hemorrhage_low_grade`: saignement a bas bruit et compense
    - `hemorrhage_j2`: saignement brutal avec decompensation rapide

- `pain_postop_uncontrolled`
  - base documentaire: SFAR douleur/ketamine, litterature thoracotomie
  - lecture retenue: reponse sympathique precoce, sans syndrome infectieux ni desaturation specifique
  - ordre attendu: `FC`, `SBP`, `DBP`, `FR` augmentent vite; `SpO2` reste stable; `T°C` quasi stable
  - traduction simulateur: cycle compresse de journee avec pics d'activite `matin -> midi -> soir` et accalmie apres prise en charge antalgique

- `cardiac_postop_complication`
  - base documentaire: recommandations/revues de risque cardiovasculaire peri-operatoire, chirurgie vasculaire
  - lecture retenue: debut souvent abrupt avec tachycardie et chute tensionnelle, puis bas debit
  - ordre attendu: baisse `SBP/DBP/TAM` et hausse `FC`, eventuellement `SpO2` un peu plus tard
  - traduction simulateur: deux variantes
    - `cardiac_postop_slow`: deterioration progressive du debit
    - `cardiac_postop_complication`: forme rapide avec instabilite plus precoce

[google-links]: https://developers.google.com/style/cross-references
[google-footnotes]: https://developers.google.com/style/footnotes
[ms-links]: https://learn.microsoft.com/en-us/contribute/content/how-to-write-links
[who-safe-ai]: https://www.who.int/news/item/16-05-2023-who-calls-for-safe-and-ethical-ai-for-health
[who-lmm]: https://www.who.int/news/item/18-01-2024-who-releases-ai-ethics-and-governance-guidance-for-large-multi-modal-models
[fda-cds]: https://www.fda.gov/medical-devices/digital-health-center-excellence/step-6-software-function-intended-provide-clinical-decision-support
[cnil-ia-sante]: https://www.cnil.fr/fr/ia-et-sante-developper-et-evaluer-des-systemes-ia-conformes
[cnil-ia]: https://www.cnil.fr/fr/ia-finalisation-recommandations-developpement-des-systemes-ia
[ec-data-min]: https://commission.europa.eu/law/law-topic/data-protection/rules-business-and-organisations/principles-gdpr/how-much-data-can-be-collected_en
[has-ia-soins]: https://www.has-sante.fr/upload/docs/application/pdf/2025-04/note_de_cadrage_-_ia_en_contexte_de_soins_accompagner_les_usages.pdf
[rcp-news2]: https://www.rcplondon.ac.uk/projects/outputs/national-early-warning-score-news-2
[rcp-news2-chart2]: https://www.rcplondon.ac.uk/media/a4ibkkbf/news2-final-report_0_0.pdf
[rcp-news2-escalation]: https://www.rcplondon.ac.uk/media/umzn4ntq/news2_additional-guidance-002-_0.pdf
[ahrq-alert-fatigue]: https://psnet.ahrq.gov/primer/alert-fatigue
[nice-sepsis]: https://www.nice.org.uk/guidance/ng51/resources/suspected-sepsis-recognition-diagnosis-and-early-management-pdf-1837508256709
[github-cardinalkit]: https://github.com/CardinalKit/CardinalKit-SMART-on-FHIR
[github-homeicu]: https://github.com/hellozed/homeicu
[github-smart-monitoring]: https://github.com/subhashissuara/smart-health-monitoring-system
[mapar-hypox]: https://www.mapar.org/cas-clinique/mvwxhyod/Hypox%C3%A9mie%20postop%C3%A9ratoire
[hug-pneumonie]: https://www.hug.ch/sites/interhug/files/2024-09/strategie_pneumonie.pdf
[pubmed-upper-abd-risk]: https://pubmed.ncbi.nlm.nih.gov/10559850/
[pubmed-upper-abd-2025]: https://pubmed.ncbi.nlm.nih.gov/40824343/
[pubmed-thoracic-ppc]: https://pubmed.ncbi.nlm.nih.gov/38317166/
[sfar-vte]: https://sfar.org/prevention-de-la-maladie-thromboembolique-veineuse-peri-operatoire/
[pubmed-tha-tka-vte-risk]: https://pubmed.ncbi.nlm.nih.gov/12172437/
[pubmed-frailty-tha-tka]: https://pubmed.ncbi.nlm.nih.gov/40540311/
[pubmed-aspirin-arthro]: https://pubmed.ncbi.nlm.nih.gov/31236894/
[sccm-sepsis]: https://www.sccm.org/clinical-resources/guidelines/guidelines/surviving-sepsis-guidelines-2021
[pubmed-colorectal-ssi-2022]: https://pubmed.ncbi.nlm.nih.gov/35427799/
[pubmed-colorectal-meta-2022]: https://pubmed.ncbi.nlm.nih.gov/35571649/
[pubmed-colorectal-bundle-2024]: https://pubmed.ncbi.nlm.nih.gov/39486458/
[sfar-hemorrhage]: https://sfar.org/download/choc-hemorragique-per-et-ou-post-operatoire/
[pmc-ugib]: https://pmc.ncbi.nlm.nih.gov/articles/PMC5922603/
[pubmed-bpv]: https://pubmed.ncbi.nlm.nih.gov/40940247/
[sfar-ketamine]: https://sfar.org/mise-au-point-sur-lutilisation-de-la-ketamine/
[pubmed-thoracotomy-rct]: https://pubmed.ncbi.nlm.nih.gov/30195601/
[pubmed-thoracotomy-meta]: https://pubmed.ncbi.nlm.nih.gov/24968967/
[pubmed-thoracotomy-audit]: https://pubmed.ncbi.nlm.nih.gov/28183561/
[pubmed-cv-review]: https://pubmed.ncbi.nlm.nih.gov/32692391/
[pubmed-vascular-pmi-2023]: https://pubmed.ncbi.nlm.nih.gov/37957761/
[pubmed-vascular-pmi-2016]: https://pubmed.ncbi.nlm.nih.gov/27102874/
[pubmed-open-vascular-mi]: https://pubmed.ncbi.nlm.nih.gov/28893702/
[acc-vascular]: https://www.acc.org/Latest-in-Cardiology/Clinical-Trials/2010/02/23/19/04/Effect-of-Bisoprolol-on-Perioperative-Mortality-and-MI-in-HighRisk-Patients-Undergoing-Vascular-Surgery
[sfar-hemo-guideline]: https://sfar.org/recommandations-sur-la-reanimation-du-choc-hemorragique/
[ssc-pdf]: https://sepsis.ch/wp-content/uploads/2024/09/Surviving-Sepsis-Campaign_International-Guidelines-for-Management-of-Sepsis-and-Septic-Shock-2021.pdf
[ssc-web]: https://www.sccm.org/clinical-resources/guidelines/guidelines/surviving-sepsis-guidelines-2021
[esc-pe]: https://biorecos.fr/wp-content/uploads/2019/11/Guidelines-for-the-diagnosis-and-management-of-acute-pulmonary-embolism_ESC_2019.pdf
[esc-pe-high]: https://pmc.ncbi.nlm.nih.gov/articles/PMC12043284/
[mapar-72h]: https://www.mapar.org/article/2/Commentaire%20de%20bibliographies%20du%20service/d4jg2vav/Incapacit%C3%A9%20%C3%A0%20d%C3%A9tecter%20l%E2%80%99hypox%C3%A9mie%20et%20l%E2%80%99hypotension%20survenant%20en%20salle%20en%20postop%C3%A9ratoire%20%3A%20facteurs%20li%C3%A9s%20%C3%A0%20une%20fr%C3%A9quence%20d%27%C3%A9valuation%20insuffisante%20par%20les%20infirmi%C3%A8res
[shock-index]: https://www.nature.com/articles/s41598-024-62579-x
[nhs-augib]: https://apps.worcsacute.nhs.uk/KeyDocumentPortal/Home/DownloadFile/2994
[sfar-spo2]: https://www.sciencedirect.com/science/article/pii/S127979600583685X/pdf
[ameli-coelioscopie]: https://www.ameli.fr/assure/sante/examen/exploration/deroulement-coelioscopie
[ameli-arthroscopie]: https://www.ameli.fr/assure/sante/examen/exploration/deroulement-arthroscopie
[ameli-plaie]: https://www.ameli.fr/var/assure/sante/bons-gestes/soins/soigner-plaie
[ameli-ep]: https://www.ameli.fr/assure/sante/urgence/pathologies/embolie-pulmonaire
[ameli-phlebite]: https://www.ameli.fr/assure/sante/themes/phlebite/symptomes-diagnostic-evolution
[ameli-essoufflement]: https://www.ameli.fr/assure/sante/themes/essoufflement-recent/je-suis-brutalement-essouffle-et-j-ai-du-mal-respirer-que-faire
[ameli-douleur-thoracique]: https://www.ameli.fr/assure/sante/themes/douleur-thoracique/reconnaitre-agit-urgence
[ameli-infarctus]: https://www.ameli.fr/assure/sante/themes/infarctus-myocarde/reconnaitre-infarctus-agir
[nice-pneumonia-public]: https://www.nice.org.uk/guidance/ng250/informationforpublic
[idsa-cap-pathway]: https://www.idsociety.org/globalassets/idsa/practice-guidelines/community-acquired-pneumonia-in-adults/cap-clinical-pathway-final-online.pdf
[cdc-ssi]: https://www.cdc.gov/surgical-site-infections/index.html
[ahrq-hemorrhage]: https://www.ahrq.gov/sites/default/files/wysiwyg/professionals/systems/hospital/qitoolkit/d4g-postophemorrhage-bestpractices.pdf
[pubmed-postop-pain-cough]: https://pubmed.ncbi.nlm.nih.gov/12434145/
[pubmed-postop-pain-function]: https://pubmed.ncbi.nlm.nih.gov/25899952/
