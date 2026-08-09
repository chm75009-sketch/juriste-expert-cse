# Juriste Expert CSE

Application de référence sur le **délit d'entrave au comité social et économique (CSE)** :
jurisprudence vérifiée (entraves **retenues** ou **écartées**), composition et attributions du CSE,
les **trois consultations récurrentes obligatoires**, la **BDESE** et les sanctions.

La base combine des **arrêts commentés** (fiches curées, recoupées dans la doctrine) et une
**collecte de masse depuis l'API officielle Judilibre** (open data des décisions judiciaires).

## Architecture

Application web statique, sans dépendance externe, installable (même modèle que les autres
applications Clarté) :

```
juriste-expert-cse/
├── index.html                # Application complète (UI + logique de filtrage/rendu)
├── jurisprudence.js          # BASE DE DONNÉES des décisions (const JURISPRUDENCE = [...])
├── schema.json               # Schéma JSON d'un enregistrement (contrat de données)
├── methodologie-sources.md   # Méthodologie à deux niveaux (4 sources / texte officiel)
├── outils/
│   ├── collecte-judilibre.py     # Collecte de masse via l'API Judilibre (PISTE)
│   └── judilibre-api-key.txt     # Clé API locale — GITIGNORÉ, jamais commité
└── README.md
```

Choix d'architecture :

- **Données séparées de l'interface.** La base vit dans `jurisprudence.js` (un tableau
  d'objets conforme à `schema.json`). L'interface (`index.html`) ne contient aucune
  décision en dur : on enrichit la base sans toucher à l'UI.
- **Fichier `.js` plutôt que `.json`** pour que l'application fonctionne aussi ouverte en
  local (`file://`), sans serveur ni `fetch`.
- **Aucune bibliothèque externe** : HTML/CSS/JS vanilla, fonctionne hors-ligne une fois chargée.
- **Chargement progressif** : l'UI affiche 30 décisions puis un bouton « Afficher plus » —
  elle reste fluide avec des centaines ou des milliers de fiches.

## Modules de l'application

1. **Délits d'entrave — jurisprudence** (module principal) : décisions filtrables par thème,
   solution (retenue / écartée / à confirmer), statut de vérification, **juridiction**,
   **période**, tri par date, compteurs par thème et recherche plein texte.
2. **Composition & attributions** : président, élus (barème R. 2314-1), secrétaire/trésorier,
   représentants syndicaux, CSSCT, réunions ; attributions à 11-49 et à 50+ salariés.
3. **Les 3 consultations obligatoires** : contenu précis et déroulé de chacune
   (orientations stratégiques — L. 2312-24 ; situation économique et financière — L. 2312-25 ;
   politique sociale, conditions de travail et emploi — L. 2312-26), délais d'avis.
4. **BDESE** : rubriques obligatoires, règles d'accès et de mise à jour, risque d'entrave.
5. **Textes & sanctions** : L. 2317-1, personnes morales, cumul, sanctions civiles,
   statut protecteur, prescription.

## Fiabilité : méthodologie à deux niveaux

Chaque fiche porte un `statut_verification` (détail dans `methodologie-sources.md`) :

- **Arrêts commentés** — recherche documentaire multi-sources :
  - `verifie` : décision confirmée par **au moins 4 sources sérieuses distinctes et
    concordantes** (Légifrance, Cour de cassation, éditeurs, revues, cabinets identifiés) ;
  - `a_verifier` : moins de 4 sources ou divergence — bandeau **« À vérifier »** avec la
    raison précise dans `note_verification`.
- **Texte officiel** — `source_officielle` : décision issue de l'**API Judilibre**
  (badge **« 🏛 Source officielle »**), avec identifiant Judilibre et URL du texte
  intégral. La solution (retenue/écartée) est **détectée automatiquement sur le
  dispositif** ; en cas d'ambiguïté la fiche porte `solution: "a_confirmer"` et le
  résumé est le sommaire officiel ou, à défaut, un extrait des motifs.
- Un numéro de pourvoi n'est renseigné que s'il est confirmé ; sinon `numero: null`.

## Collecte de masse via l'API Judilibre

Le script `outils/collecte-judilibre.py` (Python 3, bibliothèque standard uniquement)
interroge l'API publique Judilibre du portail PISTE
(`https://api.piste.gouv.fr/cassation/judilibre/v1.0`).

### 1. Clé API (jamais commitée)

Créer un compte sur [piste.gouv.fr](https://piste.gouv.fr), souscrire à l'API Judilibre,
puis placer la clé (« KeyId ») dans un fichier local **gitignoré** :

```bash
echo 'VOTRE-CLE-API' > outils/judilibre-api-key.txt
```

(ou `export JUDILIBRE_KEY_ID=...`, ou `--cle ...`).

### 2. Lancer la collecte

```bash
python3 outils/collecte-judilibre.py               # collecte complète
python3 outils/collecte-judilibre.py --dry-run     # essai sans écrire
python3 outils/collecte-judilibre.py --date-debut 2015-01-01
python3 outils/collecte-judilibre.py --max-fiches 200
```

Ce que fait le script :

- croise **« entrave »** avec : comité social et économique, CSE, comité d'entreprise,
  délégué du personnel, CHSCT, institutions représentatives du personnel, L. 2317-1,
  L. 483-1 ;
- interroge les **chambres criminelle et sociale** de la Cour de cassation et les
  **cours d'appel**, avec **pagination complète** (découpage automatique par périodes
  au-delà du plafond de 10 000 résultats de l'API) ;
- pour chaque décision : identifiant Judilibre, juridiction, chambre, date, numéro de
  pourvoi, **solution détectée sur le dispositif** (rejet / cassation / relaxe /
  condamnation — « solution à confirmer » si ambigu), **thème** parmi les 4 catégories,
  **résumé** (sommaire officiel s'il existe, sinon extrait des motifs) ;
- **fusionne dans `jurisprudence.js` sans jamais écraser les fiches curées**
  (dédoublonnage par numéro de pourvoi normalisé et par identifiant Judilibre —
  relance idempotente) ;
- affiche des **statistiques de fin de collecte** (par thème, solution, juridiction,
  type de résumé, détail par requête).

Un cache disque (`outils/cache/`, gitignoré) évite de retélécharger les décisions déjà
récupérées lors des relances.

## Lancer l'application

Aucune installation : ouvrir `index.html` dans un navigateur, ou servir le dossier
(`python3 -m http.server`) pour un usage en réseau.
