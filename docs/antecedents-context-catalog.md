# Catalogue Du Panneau Antecedents Medicaux Chirurgicaux

## Objet

Ce document sert de reference pour le panneau UI `Antecedents medicaux chirurgicaux`:

- verification des items deja exposes dans `Terrain patient` et `Contexte peri-op`
- ajouts retenus le 9 mars 2026 apres revue `MAPAR` puis `SFAR` / `NICE` / `ASA` / `ACOG` si `MAPAR` ne couvrait pas directement le besoin
- rappel de la surveillance post-operatoire specifique a relire plus tard par le LLM

Perimetre retenu:

- adulte
- post-operatoire
- suivi hospitalier de suites ou domicile surveille
- pas de pediatrie

Note de cadrage:

- `Grossesse en cours` est gardee comme cas rare mais a fort impact organisationnel
- les items tres specialises non exposes a ce stade restent dans `Autre (preciser dans le commentaire)`

## Terrain Patient - Verification Des Items Deja Exposes

| Libelle UI | Statut | Pourquoi le garder | Surveillance post-op utile plus tard | Sources |
| --- | --- | --- | --- | --- |
| `Age > 70 ans` | Deja expose | reserve fonctionnelle plus faible, risque de delirium et de recuperation plus lente | vigilance cognitive, chute, mobilisation, autonomie | [MAPAR geriatrique][mapar-geriatric], [ARISCAT][ariscat] |
| `Diabete` | Deja expose | impact infectieux, glycemique et cardiovasculaire | glycemie, plaie, infection, hydratation | [Terrain weighting interne][terrain-weighting], [NICE periop][nice-periop] |
| `Obesite` | Deja expose | risque respiratoire, thromboembolique et adaptation antalgique | SpO2, FR, analgesie, prophylaxie VTE, mobilisation | [MAPAR obesite postop][mapar-obese-postop], [SFAR VTE][sfar-vte] |
| `BPCO / asthme` | Deja expose | reserve respiratoire reduite et risque de complication pulmonaire | SpO2, FR, dyspnee, tolerance a l'extubation | [MAPAR hypoxemie postop][mapar-hypox], [ARISCAT][ariscat] |
| `Tabagisme actif ou ancien` | Deja expose | facteur respiratoire et infectieux classique | desaturation, toux, expectoration, infection de plaie | [MAPAR hypoxemie postop][mapar-hypox], [NICE periop][nice-periop] |
| `SAOS` | Deja expose | risque de depression respiratoire et d'obstruction post-op | FR, SpO2, somnolence, analgesie opioide | [MAPAR SAOS][mapar-saos], [ASA postanesthesia care][asa-pacu] |
| `Anemie` | Deja expose | diminue la tolerance au saignement et a l'hypoxie | tolerance hemodynamique, fatigue, dyspnee, saignement | [ARISCAT][ariscat], [SFAR hemorrhage][sfar-hemorrhage] |
| `Insuffisance renale` | Deja expose | risque d'IRA post-op et de mauvaise gestion volo-medicamenteuse | diurese, creatinine, balance hydrique, nephrotoxiques | [NICE AKI][nice-aki] |
| `Anticoagulation / antiagregants` | Deja expose, libelle precise | terrain hemorragique direct et reprise therapeutique delicate | saignement, pansement, drains, strategie de reprise | [MAPAR anticoagulants][mapar-anticoag], [SFAR hemorrhage][sfar-hemorrhage] |
| `Antecedent TVP / EP` | Deja expose | facteur thromboembolique majeur | douleur mollet, dyspnee, prophylaxie VTE, mobilisation | [SFAR VTE][sfar-vte] |
| `Coronaropathie / insuffisance cardiaque` | Deja expose | reserve cardiaque reduite et risque d'evenement peri-op | FC, PA, dyspnee, signes de bas debit | [ACC/AHA periop 2024][acc-periop] |
| `Immunodepression / corticoides` | Deja expose | risque infectieux accru et reponse inflammatoire modifiee | temperature, plaie, foyer infectieux, escalade precoce | [NICE sepsis][nice-sepsis], [Terrain weighting interne][terrain-weighting] |
| `Douleur chronique / opioides` | Deja expose | risque d'analgesie insuffisante et de consommation elevee d'opioides | score douleur, sedation, FR, besoin antalgique | [Terrain weighting interne][terrain-weighting] |
| `Anxiete / facteurs psychiques` | Deja expose | influence la douleur, l'adhesion et la lecture des symptomes | douleur, sommeil, reassurance, re-evaluation contextuelle | [Terrain weighting interne][terrain-weighting] |

## Terrain Patient - Ajouts Retenus Le 9 Mars 2026

| Libelle UI | Statut | Pourquoi l'ajouter | Surveillance post-op utile plus tard | Sources |
| --- | --- | --- | --- | --- |
| `Fragilite / perte d'autonomie` | Ajout | meilleur marqueur de vulnerabilite globale que le seul ASA chez le sujet age | delirium, chute, mobilisation, recuperation fonctionnelle | [MAPAR geriatrique][mapar-geriatric] |
| `Trouble cognitif / ATCD de delirium` | Ajout | risque fort de confusion et de mauvaise recuperation | delirium hypoactif, reorientation, sommeil, douleur adaptee | [MAPAR geriatrique][mapar-geriatric], [NICE delirium][nice-delirium] |
| `Hepatopathie chronique / cirrhose` | Ajout | terrain a risque de saignement, IRA, ascite et decompensation | volumes, saignement, encephalopathie, diurese, abdomen | [EASL chirurgie et cirrhose 2025][easl-cirrhosis], [MAPAR hemostase hepatique][mapar-hepatic] |
| `Cancer actif ou recent` | Ajout | augmente surtout le risque VTE et certaines complications infectieuses | VTE, mobilisation, douleur, nutrition, surveillance oncologique | [SFAR VTE][sfar-vte] |
| `Dependance alcool / risque de sevrage` | Ajout | agitation, delirium tremens et complications metaboliques peuvent brouiller le postop | neuro, tremblements, protocole de sevrage, vitamine B1 | [NICE alcool][nice-alcohol], [NICE sevrage alcool][nice-alcohol-withdrawal] |
| `Grossesse en cours` | Ajout | cas rare mais organisationnellement majeur, avec implications mere-foetus | concertation obstetrique, VTE, signes de travail, positionnement | [MAPAR grossesse][mapar-pregnancy], [ACOG chirurgie grossesse][acog-pregnancy] |

## Contexte Peri-op - Verification Des Items Deja Exposes

| Libelle UI | Statut | Pourquoi le garder | Surveillance post-op utile plus tard | Sources |
| --- | --- | --- | --- | --- |
| `ASA >= 3` | Deja expose | resume un niveau de comorbidites important mais non suffisant a lui seul | vigilance rapprochee, frequence de re-evaluation plus courte | [NICE periop][nice-periop], [MAPAR geriatrique][mapar-geriatric] |
| `Chirurgie urgente` | Deja expose | chirurgie non optimisee, risque peri-op plus eleve | hemodynamique, douleur, infection, recontrole precoce | [NICE periop][nice-periop], [ARISCAT][ariscat] |
| `Duree operatoire prolongee` | Deja expose | associee aux complications respiratoires et a la charge globale de stress | respiration, douleur, hypothermie, mobilisation | [ARISCAT][ariscat] |
| `Immobilite prolongee` | Deja expose | facteur VTE et deconditionnement | mobilisation, mollets, dyspnee, prevention thrombotique | [SFAR VTE][sfar-vte] |
| `Infection recente` | Deja expose | reserve inflammatoire deja mobilisee, risque infectieux majorable | temperature, foyer infectieux, re-evaluation precoce | [ARISCAT][ariscat], [NICE sepsis][nice-sepsis] |
| `Ventilation prolongee / extubation a risque` | Deja expose, libelle precise | signale un risque respiratoire plus utile que la simple mention de ventilation | SpO2, FR, fatigue respiratoire, vigilance, desencombrement | [ASA postanesthesia care][asa-pacu], [ASA curarisation][asa-nmba] |
| `Denutrition / hypoalbuminemie` | Deja expose | facteur de mauvaise cicatrisation, infection et recuperation lente | plaie, poids, apports, oedemes, fatigue | [NICE periop][nice-periop] |

## Contexte Peri-op - Ajouts Retenus Le 9 Mars 2026

| Libelle UI | Statut | Pourquoi l'ajouter | Surveillance post-op utile plus tard | Sources |
| --- | --- | --- | --- | --- |
| `Chirurgie majeure / complexe` | Ajout | augmente le besoin de surveillance independamment des constantes initiales | PA, douleur, saignement, reevaluation plus rapprochee | [NICE periop][nice-periop], [ASA postanesthesia care][asa-pacu] |
| `Chirurgie intraperitoneale ou thoracique` | Ajout | contexte fortement relie aux complications respiratoires et hemodynamiques | SpO2, FR, douleur a la toux, abdomen, tolerance respiratoire | [ARISCAT][ariscat], [ACC/AHA periop 2024][acc-periop] |
| `Chirurgie carcinologique` | Ajout | contexte a risque VTE et parfois de surveillance plus prolongee | VTE, douleur, nutrition, cicatrisation | [SFAR VTE][sfar-vte] |
| `Risque hemorragique eleve / transfusion` | Ajout | change clairement le niveau de vigilance postop immediat | saignement, drains, pansement, FC, PA, retentissement | [SFAR hemorrhage][sfar-hemorrhage], [MAPAR anticoagulants][mapar-anticoag] |
| `Hypothermie peri-op` | Ajout | aggrave douleur, saignement et complications de recuperation | temperature, frissons, saignement, rewarming | [NICE hypothermie][nice-hypothermia] |

## Items Non Ajoutes Pour L'Instant

- `HTP / hypertension arterielle pulmonaire`: cliniquement legitime et documentee par `MAPAR`, mais trop specialisee pour la premiere version du panneau. A garder dans `Autre` tant qu'on n'a pas un bloc cardio-pulmonaire plus fin. Source: [MAPAR HTP][mapar-htp]
- `Pediatrie`: hors sujet du projet actuel.

## Sources

[terrain-weighting]: ./terrain-risk-weighting.md
[mapar-geriatric]: https://www.mapar.org/article/1/Communication%20MAPAR/s7hmfgbp/Evaluation%20g%C3%A9riatrique%20simplifi%C3%A9e%20pr%C3%A9op%C3%A9ratoire%20par%20l%E2%80%99anesth%C3%A9siste.pdf
[mapar-saos]: https://www.mapar.org/article/1/Communication%20MAPAR/y9gzz3o2/Syndrome%20d%E2%80%99apn%C3%A9e%20du%20sommeil%20%3A%20phase%20pr%C3%A9op%C3%A9ratoire%20%3A%20d%C3%A9tection%2C%20scores%2C%20optimisation.pdf
[mapar-obese-postop]: https://www.mapar.org/article/1/Communication%20MAPAR/g16u511h/Le%20patient%20ob%C3%A8se%20%3A%20la%20p%C3%A9riode%20postop%C3%A9ratoire.pdf
[mapar-hypox]: https://www.mapar.org/cas-clinique/mvwxhyod/Hypox%C3%A9mie%20postop%C3%A9ratoire
[mapar-anticoag]: https://www.mapar.org/presentation/2/Staff%20senior/34/Gestion%20p%C3%A9ri-op%C3%A9ratoire%20des%20anticoagulants%20directs
[mapar-pregnancy]: https://www.mapar.org/presentation/1/Staff%20junior/82/Chirurgie%20non%20obst%C3%A9tricale%20chez%20la%20femme%20enceinte
[mapar-hepatic]: https://www.mapar.org/presentation/1/Staff%20junior/11/H%C3%A9mostase%20et%20transplantation%20h%C3%A9patique
[mapar-htp]: https://www.mapar.org/presentation/1/Staff%20junior/13/Gestion%20p%C3%A9ri-op%C3%A9ratoire%20de%20l%E2%80%99HTP
[nice-delirium]: https://www.nice.org.uk/guidance/cg103
[nice-aki]: https://www.nice.org.uk/guidance/ng148
[nice-periop]: https://www.nice.org.uk/guidance/ng180
[nice-sepsis]: https://www.nice.org.uk/guidance/ng51/resources/suspected-sepsis-recognition-diagnosis-and-early-management-pdf-1837508256709
[nice-alcohol]: https://www.nice.org.uk/guidance/qs11
[nice-alcohol-withdrawal]: https://www.nice.org.uk/guidance/qs11/chapter/Quality-statement-4-Acute-alcohol-withdrawal
[nice-hypothermia]: https://www.nice.org.uk/guidance/cg65
[acog-pregnancy]: https://www.acog.org/clinical/clinical-guidance/committee-opinion/articles/2019/04/nonobstetric-surgery-during-pregnancy
[sfar-vte]: https://sfar.org/prevention-de-la-maladie-thromboembolique-veineuse-peri-operatoire/
[sfar-hemorrhage]: https://sfar.org/download/choc-hemorragique-per-et-ou-post-operatoire/
[asa-pacu]: https://www.asahq.org/standards-and-practice-parameters/standards-for-postanesthesia-care
[asa-nmba]: https://www.asahq.org/standards-and-practice-parameters/practice-guideline-monitoring-and-antagonism-of-neuromuscular-blockade
[acc-periop]: https://www.acc.org/latest-in-cardiology/ten-points-to-remember/2024/09/23/04/15/2024-aha-acc-perioperative-guideline-gl
[ariscat]: https://pmc.ncbi.nlm.nih.gov/articles/PMC7047701/
[easl-cirrhosis]: https://pubmed.ncbi.nlm.nih.gov/40348682/
