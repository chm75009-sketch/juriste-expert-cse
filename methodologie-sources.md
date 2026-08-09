# Méthodologie de vérification des décisions

## Objectif

La base ne doit contenir que des décisions **réelles et traçables**. Le risque principal d'une
base de jurisprudence est la référence approximative ou inventée (mauvaise date, numéro de
pourvoi erroné, solution déformée). D'où la règle suivante.

## Règle des 4 sources

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

## Statut « à vérifier »

Une décision passe (ou reste) en **`a_verifier`** dès que :

- moins de 4 sources sérieuses la confirment ;
- deux sources divergent sur la date, le numéro ou la solution ;
- la décision n'est trouvée que citée « de seconde main » sans lien vers le texte.

Dans ce cas, `note_verification` explique précisément ce qui manque ou diverge, et l'interface
affiche un bandeau « ⚠ À vérifier » sur la carte. **Aucune décision douteuse n'est supprimée
silencieusement ni présentée comme sûre.**

## Règles d'enregistrement

- `numero` : renseigné uniquement si confirmé par les sources ; sinon `null`.
- Jurisprudence antérieure à 2018 (comité d'entreprise, délégués du personnel, CHSCT) :
  admise car transposable au CSE, en le signalant dans le résumé ou le sous-thème.
- Chaque enregistrement respecte `data/schema.json`.

## Cycle de mise à jour

1. Recherche multi-sources (bases officielles + éditeurs + revues).
2. Recoupement et comptage des sources → statut.
3. Ajout dans `data/jurisprudence.js` (l'UI se met à jour automatiquement).
4. Revue périodique des fiches « à vérifier » pour les confirmer ou les retirer.
