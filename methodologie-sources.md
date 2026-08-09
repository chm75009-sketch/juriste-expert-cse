# Méthodologie de vérification des décisions

## Objectif

La base ne doit contenir que des décisions **réelles et traçables**. Le risque principal d'une
base de jurisprudence est la référence approximative ou inventée (mauvaise date, numéro de
pourvoi erroné, solution déformée). D'où la méthodologie à **deux niveaux** ci-dessous.

## Les deux niveaux de la base

La base combine deux familles de fiches, distinguées par le champ `statut_verification` :

| Niveau | Statut | Origine | Garantie |
|---|---|---|---|
| **Arrêts commentés** | `verifie` / `a_verifier` | Recherche documentaire multi-sources (doctrine, éditeurs, revues) | Règle des 4 sources (ci-dessous) |
| **Texte officiel** | `source_officielle` | **API Judilibre** (open data des décisions judiciaires, Cour de cassation / ministère de la Justice) | Texte intégral officiel ; identifiant Judilibre + URL de consultation |

Les deux niveaux ne se confondent pas :

- Une fiche **« arrêt commenté »** apporte une **analyse rédigée** (faits, portée pratique) et
  un recoupement doctrinal ; c'est le cœur qualitatif de la base (fiches curées).
- Une fiche **« texte officiel »** apporte l'**exhaustivité** : la décision existe de manière
  certaine (elle provient de la base officielle), avec sa date, sa juridiction, son numéro de
  pourvoi et son texte intégral consultable via l'URL Judilibre. En revanche, la **solution**
  (entrave retenue/écartée) et le **thème** y sont détectés automatiquement sur le dispositif
  et les motifs : quand la détection est ambiguë, la fiche porte la mention
  **« solution à confirmer »** (`solution: "a_confirmer"`), et le résumé est, à défaut de
  sommaire officiel, un **extrait des motifs** en attendant un résumé rédigé.

Une fiche « texte officiel » peut être **promue** en arrêt commenté : on rédige le résumé, on
confirme la solution et le thème, on ajoute les sources doctrinales — elle passe alors en
`verifie` (si ≥ 4 sources) tout en conservant son identifiant Judilibre.

## Niveau 1 — Arrêts commentés : la règle des 4 sources

Une décision est marquée **`verifie`** uniquement si elle est confirmée par **au moins
4 sources sérieuses distinctes et concordantes** sur : la juridiction, la date, la solution
(entrave retenue ou écartée) et, s'il est cité, le numéro de pourvoi.

Sources considérées comme sérieuses (une seule occurrence par famille) :

| Famille | Exemples |
|---|---|
| Bases officielles | Légifrance, site de la Cour de cassation (courdecassation.fr), Judilibre |
| Éditeurs juridiques | Dalloz (dont Dalloz actualité), Éditions Lefebvre / EFL, Lamy / Liaisons sociales, LexisNexis |
| Revues et presse spécialisée | Semaine sociale Lamy, RJS, Droit social, Les Cahiers du DRH |
| Sites institutionnels | service-public.fr, travail-emploi.gouv.fr, ministère du Travail |
| Cabinets et praticiens reconnus | Publications signées de cabinets d'avocats identifiés, Village de la Justice (articles signés) |

Ne comptent **pas** comme sources sérieuses : forums, blogs anonymes, contenus générés
automatiquement, reprises sans référence précise.

### Statut « à vérifier »

Une décision passe (ou reste) en **`a_verifier`** dès que :

- moins de 4 sources sérieuses la confirment ;
- deux sources divergent sur la date, le numéro ou la solution ;
- la décision n'est trouvée que citée « de seconde main » sans lien vers le texte.

Dans ce cas, `note_verification` explique précisément ce qui manque ou diverge, et l'interface
affiche un bandeau « ⚠ À vérifier » sur la carte. **Aucune décision douteuse n'est supprimée
silencieusement ni présentée comme sûre.**

## Niveau 2 — Texte officiel : décisions issues de l'API Judilibre

Fiches produites par `outils/collecte-judilibre.py` à partir de l'API publique
**Judilibre** (`https://api.piste.gouv.fr/cassation/judilibre/v1.0`, portail PISTE).

Règles d'enregistrement de ce niveau :

- `statut_verification: "source_officielle"` — la décision provient de la base officielle.
- `judilibre_id` : identifiant unique de la décision dans Judilibre (obligatoire).
- La première entrée de `sources` est **« Judilibre (texte officiel) »** avec l'URL de
  consultation publique de la décision.
- `juridiction` et `chambre` reprennent les métadonnées officielles (chambre criminelle,
  chambre sociale, cours d'appel…).
- `numero` : numéro de pourvoi (ou RG) tel que fourni par Judilibre.
- **Solution** : détectée automatiquement sur le **dispositif** (rejet, cassation, relaxe,
  condamnation) et croisée avec la qualité du demandeur au pourvoi quand elle est
  identifiable. En cas d'ambiguïté : `solution: "a_confirmer"` + mention explicite dans
  `note_verification` (« solution à confirmer »). Aucune solution n'est affirmée sans appui
  textuel.
- **Thème** : classement automatique par mots-clés dans l'une des quatre catégories
  (mise en place/élections ; consultations & BDESE ; fonctionnement & moyens ;
  statut protecteur) — `sous_theme` indique les indices retenus.
- **Résumé** : le **sommaire officiel** de la Cour de cassation quand il existe
  (`resume_type: "sommaire_officiel"`) ; sinon un **extrait des motifs**
  (`resume_type: "extrait_motifs"`), clairement présenté comme provisoire en attendant un
  résumé rédigé.
- **Dédoublonnage** : une décision Judilibre n'est jamais ajoutée si son numéro de pourvoi
  (normalisé) ou son identifiant correspond à une fiche existante — les 44 fiches curées ne
  sont **jamais écrasées**.

## Règles d'enregistrement communes

- `numero` : renseigné uniquement s'il est confirmé (sources ou métadonnées officielles) ;
  sinon `null`.
- Jurisprudence antérieure à 2018 (comité d'entreprise, délégués du personnel, CHSCT) :
  admise car transposable au CSE, en le signalant dans le résumé ou le sous-thème
  (textes de l'époque : L. 483-1 et s. anciens).
- Chaque enregistrement respecte `schema.json`.

## Cycle de mise à jour

1. **Collecte officielle** : `python3 outils/collecte-judilibre.py` (clé API locale,
   jamais commitée) → nouvelles fiches `source_officielle`, statistiques de collecte.
2. **Recherche multi-sources** pour les décisions importantes : recoupement doctrinal,
   rédaction du résumé → promotion en `verifie`.
3. Revue périodique : fiches « à vérifier » (confirmer ou retirer) et fiches
   « solution à confirmer » (lire le dispositif, trancher).
4. L'UI (`index.html`) se met à jour automatiquement à partir de `jurisprudence.js`.
