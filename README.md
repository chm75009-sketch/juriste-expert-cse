# Juriste Expert CSE

Application de référence sur le **délit d'entrave au comité social et économique (CSE)** :
jurisprudence vérifiée (entraves **retenues** ou **écartées**), composition et attributions du CSE,
les **trois consultations récurrentes obligatoires**, la **BDESE** et les sanctions.

## Architecture

Application web statique, sans dépendance externe, installable (même modèle que les autres
applications Clarté) :

```
juriste-expert-cse/
├── index.html                # Application complète (UI + logique de filtrage/rendu)
├── jurisprudence.js          # BASE DE DONNÉES des décisions (const JURISPRUDENCE = [...])
├── schema.json               # Schéma JSON d'un enregistrement (contrat de données)
├── methodologie-sources.md   # Règle des 4 sources et statuts de vérification
└── README.md
```

Choix d'architecture :

- **Données séparées de l'interface.** La base vit dans `jurisprudence.js` (un tableau
  d'objets conforme à `schema.json`). L'interface (`index.html`) ne contient aucune
  décision en dur : on enrichit la base sans toucher à l'UI.
- **Fichier `.js` plutôt que `.json`** pour que l'application fonctionne aussi ouverte en
  local (`file://`), sans serveur ni `fetch`.
- **Aucune bibliothèque externe** : HTML/CSS/JS vanilla, fonctionne hors-ligne une fois chargée.

## Modules de l'application

1. **Délits d'entrave — jurisprudence** (module principal) : décisions filtrables par thème,
   solution (retenue/écartée), statut de vérification, et recherche plein texte.
2. **Composition & attributions** : président, élus (barème R. 2314-1), secrétaire/trésorier,
   représentants syndicaux, CSSCT, réunions ; attributions à 11-49 et à 50+ salariés.
3. **Les 3 consultations obligatoires** : contenu précis et déroulé de chacune
   (orientations stratégiques — L. 2312-24 ; situation économique et financière — L. 2312-25 ;
   politique sociale, conditions de travail et emploi — L. 2312-26), délais d'avis.
4. **BDESE** : rubriques obligatoires, règles d'accès et de mise à jour, risque d'entrave.
5. **Textes & sanctions** : L. 2317-1, personnes morales, cumul, sanctions civiles,
   statut protecteur, prescription.

## Règle de fiabilité de la base de jurisprudence

Chaque décision est recoupée dans plusieurs sources sérieuses (Légifrance, Cour de cassation,
éditeurs et revues juridiques, cabinets reconnus) :

- `statut_verification: "verifie"` — la décision est confirmée par **au moins 4 sources
  sérieuses distinctes et concordantes** (référence, date, solution).
- `statut_verification: "a_verifier"` — moins de 4 sources, ou divergence entre sources
  (date, numéro de pourvoi, portée) : la carte porte un bandeau **« À vérifier »** avec la
  raison précise dans `note_verification`.
- Un numéro de pourvoi n'est renseigné que s'il est confirmé ; sinon `numero: null`.

Voir `methodologie-sources.md`.

## Lancer l'application

Aucune installation : ouvrir `index.html` dans un navigateur, ou servir le dossier
(`python3 -m http.server`) pour un usage en réseau.
