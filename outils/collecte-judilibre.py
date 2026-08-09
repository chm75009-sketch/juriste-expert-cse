#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Collecte de masse de la jurisprudence « délit d'entrave » via l'API Judilibre
=============================================================================

Interroge l'API publique Judilibre (portail PISTE) :
    https://api.piste.gouv.fr/cassation/judilibre/v1.0

Requêtes : « entrave » croisé avec une série de termes (CSE, comité
d'entreprise, délégué du personnel, CHSCT, IRP, L. 2317-1, L. 483-1…),
sur les chambres criminelle et sociale de la Cour de cassation et sur
les cours d'appel, avec pagination complète (découpage automatique par
périodes quand une requête dépasse le plafond de 10 000 résultats).

Chaque décision retenue produit une fiche conforme à `schema.json` :
  - statut_verification: "source_officielle"
  - judilibre_id + URL publique de consultation
  - solution détectée sur le dispositif (rejet / cassation / relaxe /
    condamnation) — « a_confirmer » si ambiguë
  - thème détecté par mots-clés (4 catégories de l'application)
  - résumé = sommaire officiel s'il existe, sinon extrait des motifs

La fusion dans `jurisprudence.js` n'écrase JAMAIS les fiches existantes
(dédoublonnage par numéro de pourvoi normalisé et par judilibre_id).

Clé API (jamais commitée — voir .gitignore), par ordre de priorité :
  1. option  --cle XXXX
  2. variable d'environnement JUDILIBRE_KEY_ID
  3. fichier  outils/judilibre-api-key.txt

Usage :
    python3 outils/collecte-judilibre.py                 # collecte complète
    python3 outils/collecte-judilibre.py --dry-run       # sans écrire
    python3 outils/collecte-judilibre.py --date-debut 2015-01-01
    python3 outils/collecte-judilibre.py --max-fiches 200

Aucune dépendance externe (bibliothèque standard uniquement).
"""

import argparse
import json
import os
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BASE_URL_DEFAUT = "https://api.piste.gouv.fr/cassation/judilibre/v1.0"
URL_PUBLIQUE = "https://www.courdecassation.fr/decision/{id}"

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FICHIER_DONNEES = os.path.join(RACINE, "jurisprudence.js")
FICHIER_CLE = os.path.join(RACINE, "outils", "judilibre-api-key.txt")
DOSSIER_CACHE = os.path.join(RACINE, "outils", "cache")

PAGE_SIZE = 50          # maximum autorisé par l'API
PLAFOND_RECHERCHE = 10000  # l'API refuse page*page_size au-delà de 10 000

# Termes croisés avec « entrave » (opérateur AND : tous les mots présents)
TERMES = [
    "comité social et économique",
    "CSE",
    "comité d'entreprise",
    "délégué du personnel",
    "CHSCT",
    "institutions représentatives du personnel",
    "L. 2317-1",
    "L. 483-1",
]

# Périmètres juridictionnels : Cour de cassation (chambres criminelle et
# sociale) + cours d'appel
PERIMETRES = [
    {"jurisdiction": "cc", "chambers": ["cr", "soc"], "libelle": "Cass. (crim. + soc.)"},
    {"jurisdiction": "ca", "chambers": [], "libelle": "Cours d'appel"},
]

# ---------------------------------------------------------------------------
# Utilitaires texte
# ---------------------------------------------------------------------------

MOIS_FR = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet",
           "août", "septembre", "octobre", "novembre", "décembre"]


def sans_accents(s):
    return unicodedata.normalize("NFD", s or "").encode("ascii", "ignore").decode("ascii")


def norm(s):
    """Minuscules sans accents, espaces normalisés — pour la détection."""
    return re.sub(r"\s+", " ", sans_accents(s or "").lower())


def date_fr(iso):
    """'2023-06-06' -> '6 juin 2023'."""
    try:
        d = datetime.strptime(iso[:10], "%Y-%m-%d")
        jour = "1er" if d.day == 1 else str(d.day)
        return f"{jour} {MOIS_FR[d.month - 1]} {d.year}"
    except (ValueError, TypeError):
        return iso or ""


def norm_numero(num):
    """Clé de dédoublonnage : chiffres uniquement ('n° 23-19.821' -> '2319821')."""
    if not num:
        return None
    chiffres = re.sub(r"\D", "", str(num))
    return chiffres or None


# ---------------------------------------------------------------------------
# Client API
# ---------------------------------------------------------------------------

class ClientJudilibre:
    def __init__(self, cle, base_url=BASE_URL_DEFAUT, pause=0.2, cache_dir=None):
        self.cle = cle
        self.base_url = base_url.rstrip("/")
        self.pause = pause
        self.cache_dir = cache_dir
        self.nb_requetes = 0
        if cache_dir:
            os.makedirs(cache_dir, exist_ok=True)

    def _get(self, chemin, params):
        """GET avec réessais (429/5xx) et respect du rythme."""
        # urlencode avec doseq pour les paramètres répétés (chamber=cr&chamber=soc)
        url = f"{self.base_url}{chemin}?{urllib.parse.urlencode(params, doseq=True)}"
        derniere_erreur = None
        for tentative in range(5):
            time.sleep(self.pause)
            req = urllib.request.Request(url, headers={
                "KeyId": self.cle,
                "accept": "application/json",
            })
            try:
                with urllib.request.urlopen(req, timeout=60) as rep:
                    self.nb_requetes += 1
                    return json.loads(rep.read().decode("utf-8"))
            except urllib.error.HTTPError as e:
                derniere_erreur = e
                if e.code in (429, 500, 502, 503, 504):
                    attente = 2 ** tentative
                    print(f"    … HTTP {e.code}, nouvel essai dans {attente}s", file=sys.stderr)
                    time.sleep(attente)
                    continue
                if e.code in (401, 403):
                    raise SystemExit(
                        f"ERREUR : accès refusé par l'API (HTTP {e.code}). "
                        "Vérifiez la clé API (header KeyId) et l'abonnement Judilibre sur PISTE."
                    )
                raise
            except (urllib.error.URLError, TimeoutError) as e:
                derniere_erreur = e
                attente = 2 ** tentative
                print(f"    … erreur réseau ({e}), nouvel essai dans {attente}s", file=sys.stderr)
                time.sleep(attente)
        raise SystemExit(f"ERREUR : l'API ne répond pas après 5 essais ({derniere_erreur})")

    # -- /search ------------------------------------------------------------

    def _page_recherche(self, terme, perimetre, page, date_debut, date_fin):
        params = [
            ("query", f"entrave {terme}"),
            ("operator", "and"),
            ("jurisdiction", perimetre["jurisdiction"]),
            ("page_size", PAGE_SIZE),
            ("page", page),
            ("sort", "date"),
            ("order", "desc"),
            ("date_start", date_debut),
            ("date_end", date_fin),
        ]
        for ch in perimetre["chambers"]:
            params.append(("chamber", ch))
        return self._get("/search", params)

    def rechercher(self, terme, perimetre, date_debut, date_fin, profondeur=0):
        """Pagination complète d'une requête ; découpe la période en deux
        (récursivement) si le total dépasse le plafond de l'API."""
        premiere = self._page_recherche(terme, perimetre, 0, date_debut, date_fin)
        total = premiere.get("total", 0)
        if total == 0:
            return []

        if total > PLAFOND_RECHERCHE and profondeur < 12:
            d1 = datetime.strptime(date_debut, "%Y-%m-%d").date()
            d2 = datetime.strptime(date_fin, "%Y-%m-%d").date()
            if (d2 - d1).days > 1:
                milieu = d1 + (d2 - d1) / 2
                print(f"    {total} résultats > plafond : découpage "
                      f"{date_debut}→{milieu} / {milieu + timedelta(days=1)}→{date_fin}")
                return (self.rechercher(terme, perimetre, date_debut, milieu.isoformat(), profondeur + 1)
                        + self.rechercher(terme, perimetre, (milieu + timedelta(days=1)).isoformat(),
                                          date_fin, profondeur + 1))

        resultats = list(premiere.get("results", []))
        pages = (min(total, PLAFOND_RECHERCHE) + PAGE_SIZE - 1) // PAGE_SIZE
        for page in range(1, pages):
            rep = self._page_recherche(terme, perimetre, page, date_debut, date_fin)
            lot = rep.get("results", [])
            if not lot:
                break
            resultats.extend(lot)
        return resultats

    # -- /decision ----------------------------------------------------------

    def decision(self, id_decision):
        """Texte intégral + zones + sommaire d'une décision (avec cache disque)."""
        if self.cache_dir:
            chemin = os.path.join(self.cache_dir, f"{id_decision}.json")
            if os.path.exists(chemin):
                with open(chemin, encoding="utf-8") as f:
                    return json.load(f)
        rep = self._get("/decision", [("id", id_decision)])
        if self.cache_dir:
            with open(os.path.join(self.cache_dir, f"{id_decision}.json"), "w",
                      encoding="utf-8") as f:
                json.dump(rep, f, ensure_ascii=False)
        return rep


# ---------------------------------------------------------------------------
# Analyse d'une décision : zones, solution, thème, articles, résumé
# ---------------------------------------------------------------------------

def texte_zone(dec, nom):
    """Concatène les segments d'une zone ('dispositif', 'motivations'…)."""
    texte = dec.get("text") or ""
    zones = dec.get("zones") or {}
    segments = zones.get(nom) or []
    morceaux = []
    for seg in segments:
        try:
            morceaux.append(texte[seg["start"]:seg["end"]])
        except (KeyError, TypeError):
            pass
    return "\n".join(morceaux).strip()


RE_COUPABLE = re.compile(r"declare?n?t?\b.{0,120}\bcoupable", re.S)
RE_CONDAMNE = re.compile(r"condamne\b.{0,160}\b(amende|emprisonnement|euros?|francs|dommages)", re.S)


def detecter_solution(dec):
    """Retourne (solution, note, indice) à partir du dispositif et des métadonnées.

    solution ∈ {retenue, ecartee, a_confirmer} ; note = None ou explication
    (obligatoire si a_confirmer) ; indice = mot-clé du dispositif retenu.
    """
    sol_meta = norm(dec.get("solution") or "")
    disp = norm(texte_zone(dec, "dispositif")) or norm((dec.get("text") or "")[-1200:])
    texte = norm(dec.get("text") or "")

    relaxe_disp = "relaxe" in disp or "renvoye des fins de la poursuite" in disp
    coupable_disp = bool(RE_COUPABLE.search(disp)) or bool(RE_CONDAMNE.search(disp))

    # 1. Dispositif explicite (surtout cours d'appel)
    if relaxe_disp and not coupable_disp:
        return "ecartee", None, "relaxe (dispositif)"
    if coupable_disp and not relaxe_disp:
        return "retenue", None, "condamnation (dispositif)"

    # 2. Cour de cassation : rejet → la décision attaquée est confirmée
    if "rejet" in sol_meta or disp.startswith("rejette") or "rejette le pourvoi" in disp:
        relaxe_txt = "relaxe" in texte
        coupable_txt = bool(RE_COUPABLE.search(texte)) or "condamn" in texte
        if coupable_txt and not relaxe_txt:
            return "retenue", None, "rejet du pourvoi contre une condamnation"
        if relaxe_txt and not coupable_txt:
            return "ecartee", None, "rejet du pourvoi contre une relaxe"
        return ("a_confirmer",
                "Solution à confirmer : rejet du pourvoi mais le sens de la décision "
                "attaquée (condamnation ou relaxe) n'a pas pu être déterminé automatiquement.",
                "rejet (sens de la décision attaquée ambigu)")

    # 3. Cassation : le sort dépend du renvoi
    if "cassation" in sol_meta or "casse et annule" in disp:
        return ("a_confirmer",
                "Solution à confirmer : cassation — l'issue définitive dépend de la "
                "juridiction de renvoi ; lire le dispositif pour trancher.",
                "cassation")

    # 4. Solutions procédurales
    for mot in ("irrecevabilite", "non-lieu", "desistement", "decheance", "annulation"):
        if mot in sol_meta:
            return ("a_confirmer",
                    f"Solution à confirmer : issue procédurale ({mot}) sans examen du fond "
                    "détectable automatiquement.",
                    mot)

    return ("a_confirmer",
            "Solution à confirmer : le dispositif ne permet pas de détecter automatiquement "
            "si l'entrave a été retenue ou écartée.",
            "dispositif ambigu")


THEMES_MOTS_CLES = {
    "mise_en_place": [
        "protocole preelectoral", "protocole d'accord preelectoral", "organisation des elections",
        "elections professionnelles", "proces-verbal de carence", "carence", "candidature",
        "college electoral", "electorat", "mise en place du comite", "scrutin",
        "defaut d'organisation des elections",
    ],
    "consultations_bdese": [
        "information-consultation", "consultation du comite", "consulter le comite",
        "defaut de consultation", "bdese", "bdes", "base de donnees economiques",
        "orientations strategiques", "politique sociale", "situation economique et financiere",
        "expert-comptable", "expertise", "avis du comite", "information du comite",
    ],
    "fonctionnement_moyens": [
        "reunion", "convocation", "ordre du jour", "heures de delegation", "credit d'heures",
        "local", "subvention de fonctionnement", "budget", "activites sociales et culturelles",
        "proces-verbal de reunion", "secretaire du comite", "affichage", "liberte de deplacement",
        "entrave au fonctionnement",
    ],
    "statut_protecteur_principes": [
        "salarie protege", "statut protecteur", "autorisation de l'inspecteur du travail",
        "autorisation administrative", "licenciement", "rupture du contrat", "mise a pied",
        "discrimination syndicale", "reintegration", "transfert du contrat", "mandat",
    ],
}


def detecter_theme(dec):
    """Retourne (theme, indices) par score de mots-clés sur le texte intégral."""
    texte = norm(dec.get("text") or "") + " " + norm(dec.get("summary") or "")
    scores, indices = {}, {}
    for theme, mots in THEMES_MOTS_CLES.items():
        trouves = [m for m in mots if m in texte]
        # les expressions longues (plus spécifiques) pèsent double
        scores[theme] = sum(2 if " " in m else 1 for m in trouves)
        indices[theme] = trouves
    meilleur = max(scores, key=lambda t: scores[t])
    if scores[meilleur] == 0:
        return "fonctionnement_moyens", []
    return meilleur, indices[meilleur][:4]


RE_ARTICLE = re.compile(r"\bL\.?\s*(\d{3,4}(?:-\d+){1,2})\b")


def extraire_articles(dec):
    """Articles du code du travail cités (L. XXXX-X), priorité aux textes d'entrave."""
    texte = (dec.get("text") or "")
    vus, articles = set(), []
    for m in RE_ARTICLE.finditer(texte):
        art = f"L. {m.group(1)}"
        if art not in vus:
            vus.add(art)
            articles.append(art)
    prioritaires = [a for a in articles if re.search(r"2317-1|483-|431-|2146-", a)]
    autres = [a for a in articles if a not in prioritaires]
    return (prioritaires + autres)[:6]


def construire_resume(dec):
    """Sommaire officiel si présent, sinon extrait des motifs centré sur « entrave »."""
    sommaire = (dec.get("summary") or "").strip()
    if sommaire:
        return sommaire, "sommaire_officiel"

    motifs = texte_zone(dec, "motivations") or (dec.get("text") or "")
    phrases = re.split(r"(?<=[.;])\s+", motifs)
    pertinentes = [p.strip() for p in phrases if "entrave" in norm(p)]
    if pertinentes:
        extrait = " ".join(pertinentes[:3])
    else:
        extrait = motifs[-800:].strip()
    extrait = re.sub(r"\s+", " ", extrait)
    if len(extrait) > 700:
        extrait = extrait[:700].rsplit(" ", 1)[0] + "…"
    return ("[Extrait des motifs — résumé rédigé à venir] " + extrait,
            "extrait_motifs")


def libelle_juridiction(dec):
    j = (dec.get("jurisdiction") or "").lower()
    chambre = dec.get("chamber") or ""
    if j == "cc":
        ch = norm(chambre)
        if "crim" in ch or ch == "cr":
            return "Cass. crim.", "Chambre criminelle"
        if "soc" in ch:
            return "Cass. soc.", "Chambre sociale"
        return "Cass.", chambre or None
    if j == "ca":
        lieu = dec.get("location") or ""
        lieu = re.sub(r"(?i)^cour d'appel (de |d')", "", lieu).strip()
        return (f"CA {lieu}" if lieu else "CA"), chambre or None
    return (dec.get("jurisdiction") or "Juridiction inconnue"), chambre or None


def fabriquer_fiche(dec):
    """Construit une fiche conforme à schema.json depuis une décision Judilibre."""
    id_jl = dec.get("id")
    juridiction, chambre = libelle_juridiction(dec)
    iso = (dec.get("decision_date") or "")[:10] or None
    numeros = dec.get("numbers") or ([dec["number"]] if dec.get("number") else [])
    numero = f"n° {numeros[0]}" if numeros else None
    solution, note, indice = detecter_solution(dec)
    theme, indices_theme = detecter_theme(dec)
    resume, resume_type = construire_resume(dec)

    sous_theme = "Collecte Judilibre"
    if indices_theme:
        sous_theme += " — indices : " + ", ".join(indices_theme)
    sous_theme += f" — dispositif : {indice}"

    return {
        "theme": theme,
        "sous_theme": sous_theme,
        "juridiction": juridiction,
        "chambre": chambre,
        "date": date_fr(iso) if iso else "date inconnue",
        "date_iso": iso,
        "numero": numero,
        "solution": solution,
        "solution_officielle": dec.get("solution") or None,
        "resume": resume,
        "resume_type": resume_type,
        "articles": extraire_articles(dec),
        "sources": [{
            "nom": "Judilibre (texte officiel)",
            "url": URL_PUBLIQUE.format(id=id_jl),
        }],
        "nb_sources": 1,
        "statut_verification": "source_officielle",
        "note_verification": note,
        "judilibre_id": id_jl,
        "id": f"judilibre-{id_jl}",
        "_numeros_tous": [norm_numero(n) for n in numeros if norm_numero(n)],
    }


# ---------------------------------------------------------------------------
# Lecture / écriture de jurisprudence.js
# ---------------------------------------------------------------------------

ENTETE_JS = """/* =========================================================================
   BASE DE DONNÉES — Jurisprudence du délit d'entrave au CSE
   Contrat de données : voir schema.json
   Méthodologie à deux niveaux (arrêts commentés / texte officiel) :
   voir methodologie-sources.md
   Les fiches statut_verification "source_officielle" sont générées par
   outils/collecte-judilibre.py depuis l'API Judilibre — ne pas les éditer
   à la main sans motif ; les fiches curées ne sont jamais écrasées.
   ========================================================================= */
const JURISPRUDENCE = """


def lire_base(chemin):
    with open(chemin, encoding="utf-8") as f:
        contenu = f.read()
    debut = contenu.find("[")
    fin = contenu.rfind("]")
    if debut == -1 or fin == -1:
        raise SystemExit(f"ERREUR : impossible de trouver le tableau JSON dans {chemin}")
    return json.loads(contenu[debut:fin + 1])


def ecrire_base(chemin, fiches):
    corps = json.dumps(fiches, ensure_ascii=False, indent=2)
    with open(chemin, "w", encoding="utf-8") as f:
        f.write(ENTETE_JS + corps + ";\n")


# ---------------------------------------------------------------------------
# Programme principal
# ---------------------------------------------------------------------------

def lire_cle(args):
    if args.cle:
        return args.cle.strip()
    if os.environ.get("JUDILIBRE_KEY_ID"):
        return os.environ["JUDILIBRE_KEY_ID"].strip()
    if os.path.exists(args.fichier_cle):
        with open(args.fichier_cle, encoding="utf-8") as f:
            cle = f.read().strip()
        if cle:
            return cle
    raise SystemExit(
        "ERREUR : aucune clé API trouvée.\n"
        f"Placez votre clé PISTE dans {args.fichier_cle} (fichier gitignoré),\n"
        "ou exportez JUDILIBRE_KEY_ID, ou passez --cle XXXX."
    )


def main():
    ap = argparse.ArgumentParser(description="Collecte Judilibre — délit d'entrave (CSE/IRP)")
    ap.add_argument("--cle", help="Clé API PISTE (header KeyId)")
    ap.add_argument("--fichier-cle", default=FICHIER_CLE, help="Fichier contenant la clé API")
    ap.add_argument("--base-url", default=BASE_URL_DEFAUT, help="URL de base de l'API")
    ap.add_argument("--donnees", default=FICHIER_DONNEES, help="Chemin de jurisprudence.js")
    ap.add_argument("--date-debut", default="1970-01-01", help="Borne basse (AAAA-MM-JJ)")
    ap.add_argument("--date-fin", default=date.today().isoformat(), help="Borne haute (AAAA-MM-JJ)")
    ap.add_argument("--pause", type=float, default=0.2, help="Pause entre requêtes (s)")
    ap.add_argument("--max-fiches", type=int, default=0,
                    help="Limite de nouvelles fiches à ajouter (0 = sans limite)")
    ap.add_argument("--dry-run", action="store_true", help="Ne pas écrire jurisprudence.js")
    ap.add_argument("--sans-cache", action="store_true", help="Désactiver le cache disque")
    args = ap.parse_args()

    cle = lire_cle(args)
    client = ClientJudilibre(cle, base_url=args.base_url, pause=args.pause,
                             cache_dir=None if args.sans_cache else DOSSIER_CACHE)

    # -- 1. Base existante et clés de dédoublonnage -------------------------
    base = lire_base(args.donnees)
    ids_judilibre = {f.get("judilibre_id") for f in base if f.get("judilibre_id")}
    numeros_connus = {norm_numero(f.get("numero")) for f in base} - {None}
    nb_curees = sum(1 for f in base if f.get("statut_verification") != "source_officielle")
    print(f"Base existante : {len(base)} fiches ({nb_curees} curées, "
          f"{len(base) - nb_curees} source officielle), "
          f"{len(numeros_connus)} numéros de pourvoi connus.")

    # -- 2. Recherche croisée -----------------------------------------------
    trouvailles = {}   # id judilibre -> résultat de recherche
    stats_requetes = []
    for perimetre in PERIMETRES:
        for terme in TERMES:
            libelle = f"« entrave » × « {terme} » [{perimetre['libelle']}]"
            print(f"→ Recherche {libelle}")
            resultats = client.rechercher(terme, perimetre, args.date_debut, args.date_fin)
            nouveaux = 0
            for r in resultats:
                rid = r.get("id")
                if rid and rid not in trouvailles:
                    trouvailles[rid] = r
                    nouveaux += 1
            stats_requetes.append((libelle, len(resultats), nouveaux))
            print(f"   {len(resultats)} résultats, {nouveaux} inédits "
                  f"(total unique : {len(trouvailles)})")

    # -- 3. Détails, analyse, fiches ----------------------------------------
    ids_a_traiter = [rid for rid in trouvailles if rid not in ids_judilibre]
    print(f"\n{len(trouvailles)} décisions uniques trouvées ; "
          f"{len(trouvailles) - len(ids_a_traiter)} déjà en base (judilibre_id) ; "
          f"{len(ids_a_traiter)} à analyser.")

    nouvelles, doublons_numero, erreurs = [], 0, 0
    for i, rid in enumerate(ids_a_traiter, 1):
        if args.max_fiches and len(nouvelles) >= args.max_fiches:
            print(f"   Limite --max-fiches={args.max_fiches} atteinte.")
            break
        if i % 25 == 0 or i == len(ids_a_traiter):
            print(f"   … analyse {i}/{len(ids_a_traiter)} "
                  f"({len(nouvelles)} fiches retenues)")
        try:
            dec = client.decision(rid)
        except SystemExit:
            raise
        except Exception as e:  # décision indisponible : on continue
            erreurs += 1
            print(f"   ! décision {rid} illisible ({e}), ignorée", file=sys.stderr)
            continue
        fiche = fabriquer_fiche(dec)
        nums = set(fiche.pop("_numeros_tous"))
        if nums & numeros_connus:
            doublons_numero += 1
            continue
        numeros_connus |= nums
        ids_judilibre.add(rid)
        nouvelles.append(fiche)

    # -- 4. Fusion sans écrasement ------------------------------------------
    nouvelles.sort(key=lambda f: f.get("date_iso") or "", reverse=True)
    fusion = base + nouvelles
    if args.dry_run:
        print("\n--dry-run : jurisprudence.js NON modifié.")
    else:
        ecrire_base(args.donnees, fusion)
        print(f"\n{args.donnees} mis à jour.")

    # -- 5. Statistiques ------------------------------------------------------
    def compter(fiches, champ):
        c = {}
        for f in fiches:
            c[f.get(champ) or "?"] = c.get(f.get(champ) or "?", 0) + 1
        return dict(sorted(c.items(), key=lambda kv: -kv[1]))

    print("\n===== STATISTIQUES DE COLLECTE =====")
    print(f"Requêtes API                 : {client.nb_requetes}")
    print(f"Décisions uniques trouvées   : {len(trouvailles)}")
    print(f"Déjà en base (judilibre_id)  : {len(trouvailles) - len(ids_a_traiter)}")
    print(f"Doublons par n° de pourvoi   : {doublons_numero}")
    print(f"Décisions illisibles         : {erreurs}")
    print(f"NOUVELLES FICHES AJOUTÉES    : {len(nouvelles)}")
    print(f"Taille de la base            : {len(base)} → {len(fusion)}")
    if nouvelles:
        print("\nNouvelles fiches par thème :")
        for k, v in compter(nouvelles, "theme").items():
            print(f"  {k:<30} {v}")
        print("Nouvelles fiches par solution :")
        for k, v in compter(nouvelles, "solution").items():
            print(f"  {k:<30} {v}")
        print("Nouvelles fiches par juridiction :")
        for k, v in list(compter(nouvelles, "juridiction").items())[:15]:
            print(f"  {k:<30} {v}")
        nb_sommaires = sum(1 for f in nouvelles if f["resume_type"] == "sommaire_officiel")
        print(f"Résumés : {nb_sommaires} sommaires officiels, "
              f"{len(nouvelles) - nb_sommaires} extraits des motifs (à rédiger)")
    print("\nDétail des requêtes :")
    for libelle, n, inedits in stats_requetes:
        print(f"  {n:>5} rés. ({inedits:>5} inédits)  {libelle}")


if __name__ == "__main__":
    main()
