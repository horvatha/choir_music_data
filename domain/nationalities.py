"""Predicts composer_nationalities.need_to_check -- which rows were
assigned by trusting a Wikidata citizenship (P27) claim at face value,
with no independent verification -- as opposed to the mechanics of
writing the flag (load_nationalities.py's SQL). Every function here is
pure: plain Python values in, plain Python values out.

Historical context: on 2026-08-11, composers loaded via the "relation
discovery" batch (load_missing_composers.py -- these never go through
composers_*.csv, so had no other nationality source at all) had their
nationality bulk-assigned straight from a single-candidate Wikidata P27
citizenship claim, "no research needed" (see nationality_citizenship_
review.md, gitignored, not committed). That's exactly the need_to_check
case schema.sql documents. The flag was only ever applied as a one-off
psql patch, never baked into load_nationalities.py -- its own TRUNCATE
silently wiped all 461 rows at some point on 2026-08-23, recovered from
a 2026-08-22 21:43 backup (composers_backup_20260822_214317.dump).

CITIZENSHIP_TO_NATIONALITY re-derives most of the 460 affected composers
from their live Wikidata citizenship claim rather than hardcoding the
result directly -- self-updating, in the sense that a *new* relation-
discovery composer with a single citizenship claim matching one of these
QIDs gets predicted too, not just the original batch. Verified against
the actual recovered data: of the 366 id>=9900 composers with exactly
one citizenship claim, this predicts 364 correctly and creates only 2
false positives (Theodor Kullak, Jacob Praetorius the Elder -- both
match the "German" prediction exactly but were *not* flagged in the
recovered backup, meaning someone verified them by hand at some point;
excluded via VERIFIED_NOT_NEEDING_CHECK so the prediction doesn't
re-flag them).

NEED_TO_CHECK_EXCEPTIONS covers everyone the citizenship-QID rule can't
explain: composers with zero or multiple citizenship claims in the
cache (most of them -- a missing/ambiguous claim can't be predicted from
by definition), a handful of composers from the original composers_*.csv
pipeline (ids <9900) this same bulk pass also happened to touch, and
Wipo of Burgundy specifically (his only citizenship claim, Q183/Germany,
is a plainly anachronistic P27 mapping for an 11th-century Burgundian
monk -- his real nationality tag is "Frankish (Arles/Burgundy)", not
"German", so the citizenship rule would give the *wrong* answer for him
even if it fired).
"""

# Wikidata citizenship (P27) QID -> the single nationality name it maps
# to, empirically derived from the composers this rule successfully
# explains (see module docstring for the verification numbers).
CITIZENSHIP_TO_NATIONALITY = {
    "Q1055": "German",
    "Q1206012": "German",
    "Q1235720": "Italian",
    "Q142": "French",
    "Q153015": "German",
    "Q154195": "German",
    "Q155": "Brazilian",
    "Q159": "Russian",
    "Q159631": "German",
    "Q16": "Canadian",
    "Q16957": "German",
    "Q17": "Japanese",
    "Q170072": "Dutch",
    "Q170174": "Italian",
    "Q172579": "Italian",
    "Q173065": "Italian",
    "Q183": "German",
    "Q186320": "German",
    "Q20": "Norwegian",
    "Q207272": "Polish",
    "Q212": "Ukrainian",
    "Q218": "Romanian",
    "Q219": "Bulgarian",
    "Q221457": "Polish",
    "Q241": "Cuban",
    "Q27306": "German",
    "Q28": "Hungarian",
    "Q29": "Spanish",
    "Q29999": "Dutch",
    "Q30": "American",
    "Q31": "Belgian",
    "Q32": "Luxembourgish",
    "Q326029": "German",
    "Q33": "Finnish",
    "Q34": "Swedish",
    "Q36": "Polish",
    "Q38": "Italian",
    "Q39": "Swiss",
    "Q40": "Austrian",
    "Q408": "Australian",
    "Q41": "Greek",
    "Q414": "Argentine",
    "Q43287": "German",
    "Q45": "Portuguese",
    "Q45670": "Portuguese",
    "Q4948": "Italian",
    "Q641": "Italian",
    "Q70972": "French",
    "Q717": "Venezuelan",
    "Q739": "Colombian",
    "Q756617": "Danish",
    "Q822": "Lebanese",
    "Q96": "Mexican",
}

# Composer wikidata_id -> [nationality name, ...] -- composers whose
# need_to_check state the citizenship-QID rule can't derive (see module
# docstring for why each falls outside the rule), so it's recorded
# directly. Comment names each composer for review; source citizenship
# claim shape noted where it's not simply "zero or multiple claims".
NEED_TO_CHECK_EXCEPTIONS = {
    "Q101761654": ['German'],  # Martha von Flotow
    "Q104601003": ['Hungarian'],  # Karoly Noszeda
    "Q107920966": ['Italian'],  # Fabrizio II Gesualdo
    "Q109483563": ['Ukrainian'],  # Дяченко Григорій Онуфрійович
    "Q1150470": ['Italian'],  # Fernando Germani
    "Q11588067": ['Japanese'],  # Toshi Isobe
    "Q11935556": ['Italian'],  # Mario Labroca
    "Q12096217": ['Ukrainian'],  # Glushkov Petro Tarasovich
    "Q12121568": ['Hungarian'],  # shtvan Ferentsovich Marton
    "Q12762134": ['Slovak'],  # Ali Brezovský
    "Q1278110": ['Flemish', 'French'],  # Jean Cousin -- also covered by
                # load_nationalities.py's own OR_RE either/or split;
                # kept here too, harmless (ON CONFLICT-safe upsert).
    "Q139859258": ['German'],  # Conrad Berens
    "Q1430182": ['Czech'],  # Florian Zajíc
    "Q1441113": ['Italian'],  # Francesco Maria Cattaneo
    "Q1449619": ['Austrian'],  # Franz Xaver Gruber
    "Q1525889": ['Italian'],  # Giovanni Battista Mancini
    "Q1525931": ['Italian'],  # Giovanni Battista Tibaldi
    "Q15450999": ['German'],  # Georg Jacob Vollweiler
    "Q1579710": ['Czech'],  # Hans Georg Benda
    "Q15810061": ['Italian'],  # Francesco Barbella
    "Q16177398": ['Argentine'],  # Pablo M Berutti
    "Q16669949": ['German'],  # Walther Lampe
    "Q16691491": ['Russian'],  # Ilya Semyonovich Aisberg
    "Q1692331": ['Czech'],  # Johann Aloys Miksch
    "Q17520384": ['Italian'],  # Giovanni Domenico Rognoni Taeggio
    "Q18616078": ['Italian'],  # Alessandro Toeschi
    "Q19544736": ['German'],  # Wilhelm Hanser
    "Q19999271": ['German'],  # Heinrich van Eyken
    "Q20006143": ['Italian'],  # Ottavio Catalani
    "Q20243396": ['German'],  # Joseph Franz Wolf
    "Q20890544": ['Italian'],  # Domenico Tritto
    "Q21402360": ['Spanish'],  # José Ma. Alcácer
    "Q2152778": ['Italian'],  # Floriano Maria Arresti
    "Q21853006": ['Czech'],  # Matous Habermann
    "Q24942922": ['Spanish'],  # Pedro Fernández de Castilleja
    "Q2528697": ['Italian'],  # Vito Frazzi
    "Q25360437": ['Slovak'],  # Ludovit Rajter starsi
    "Q25424133": ['Italian'],  # Giuseppe Pilotti‏
    "Q25743688": ['Finnish'],  # François de Godzinsky
    "Q259379": ['American'],  # Anoushka Shankar
    "Q26196723": ['German'],  # Johann Kusser st.
    "Q27824587": ['German'],  # Emil Kühnel
    "Q27995018": ['German'],  # Charles Louis Maucourt
    "Q27999024": ['Spanish'],  # Bernardino de Ribera
    "Q28357940": ['Tatar'],  # Аллаһияр Вәлиуллин
    "Q2857410": ['Italian'],  # Antonio Puccini
    "Q28678230": ['Portuguese'],  # Lourenço Ribeiro
    "Q3129505": ['Dutch'],  # Heinrich Praeger
    "Q32161192": ['Italian'],  # Gaetano Carpani
    "Q34739941": ['Russian'],  # Petr Petrovich Evstafʹev
    "Q3514176": ['Japanese'],  # Takanobu Saitō
    "Q354813": ['Frankish'],  # Notker the Stammerer (Notker Balbulus) --
                # original composers_Medieval.csv pipeline (id 1), not
                # the relation-discovery batch; this bulk pass touched
                # him anyway.
    "Q3638094": ['Italian'],  # Benedetto Neri
    "Q3646534": ['Czech'],  # Karel Stecker
    "Q38225696": ['German'],  # Franz Seraph Cramer
    "Q3949447": ['Italian'],  # Santino Garsi da Parma
    "Q41527384": ['German'],  # Johann Christoph Walther
    "Q41547791": ['German'],  # Johann Konrad Schlick
    "Q4160549": ['Italian'],  # Michele Giuliani
    "Q4171146": ['Austrian'],  # Matthias Durst
    "Q4395043": ['French'],  # Félix Rault
    "Q440809": ['German'],  # Friedrich Wieck
    "Q4426737": ['Italian'],  # Cesare Sodero
    "Q458981": ['German'],  # Berno of Reichenau -- original CSV
                # pipeline (id 17), same as Notker above.
    "Q537218": ['Frankish (Arles/Burgundy)'],  # Wipo of Burgundy (id 13,
                # original CSV pipeline) -- his only citizenship claim,
                # Q183, maps to "German" per CITIZENSHIP_TO_NATIONALITY
                # above (correctly, for the many other composers who
                # share it), but that's the wrong answer for an
                # 11th-century Burgundian monk; Wikidata's P27 here is
                # simply anachronistic. wikidata_id backfilled onto this
                # composer's row 2026-08-23 (was previously blank in the
                # DB despite the cache having claims for it).
    "Q546592": ['Japanese'],  # Isao Tomita
    "Q5476105": ['Austrian'],  # Mathias Haydn
    "Q54859811": ['Russian'],  # Eduard Zaritsky
    "Q55078214": ['German'],  # Esaias Reusner der Ältere
    "Q55133198": ['Austrian'],  # Sophonias Päminger
    "Q552124": ['Italian'],  # Girolamo Crescentini
    "Q55838259": ['French'],  # Edmond Diet
    "Q55875077": ['Austrian'],  # Sigismund Päminger
    "Q56401848": ['Catalan'],  # Emili Valdés Perlasia
    "Q56401855": ['Catalan'],  # Julià Vilaseca
    "Q57306105": ['German'],  # Heinrich Romberg
    "Q588565": ['Italian'],  # Domenico da Piacenza
    "Q59327572": ['German'],  # Moritz Schön
    "Q6048751": ['Italian'],  # Luigi Piccinni
    "Q61997412": ['Italian'],  # Agostino Bendinelli
    "Q63565427": ['German'],  # Vincent Lübeck
    "Q63745": ['German'],  # Julius Rietz
    "Q65648": ['German'],  # Charles Hallé
    "Q67963": ['French'],  # Edward Dannreuther
    "Q695725": ['Austrian'],  # Georg Hellmesberger
    "Q74653933": ['German'],  # Otto Reinsdorf
    "Q8002219": ['Czech'],  # Wilhelm Kuhe
    "Q85072": ['German'],  # Wilhelm Joseph von Wasielewski
    "Q875506": ['Italian'],  # Giovanni Andrea Bontempi
    "Q927177": ['Italian'],  # Giacomo Insanguine
    "Q928954": ['Italian'],  # Vincenzo Manfredini
    "Q94574227": ['German'],  # Albert Noelte
    "Q94822351": ['Czech'],  # Theodor Blumer
    "Q94914102": ['Austrian'],  # Wilhelm Müller
    "Q95071503": ['Czech'],  # Maxmilian Koblížek
    "Q95151577": ['Czech'],  # Jaroslav Ušák
}

# Composer wikidata_id -> matches CITIZENSHIP_TO_NATIONALITY exactly
# (single claim, correct-looking mapping) but is confirmed *not* flagged
# in the recovered 2026-08-22 backup -- someone verified these by hand
# at some point. Without this, the citizenship rule would incorrectly
# re-flag them the next time it runs.
VERIFIED_NOT_NEEDING_CHECK = {
    "Q706082",  # Theodor Kullak
    "Q71963",   # Jacob Praetorius the Elder
}


# The citizenship-QID rule only means "unverified" within the relation-
# discovery batch (composer_id >= this) -- an *ordinary* composers_*.csv
# composer having a citizenship claim that matches their nationality is
# completely normal (that's just correct data, not evidence of an
# unverified bulk assignment), so applying the rule without this gate
# produces thousands of false positives across the whole DB (verified:
# 3742 when tested ungated vs. 2 when gated to id>=9900, both against
# the real live DB on 2026-08-23). Composers below this id always came
# through composers_*.csv (or an equivalent hand-curated source) and
# have their own independently-sourced nationality; the exceptions this
# batch *did* touch below the boundary (Notker the Stammerer/id 1, Berno
# of Reichenau/id 17, Wipo of Burgundy/id 13) are handled individually
# via NEED_TO_CHECK_EXCEPTIONS instead.
MIN_RELATION_DISCOVERY_COMPOSER_ID = 9900


def predict_need_to_check(composer_id, wikidata_id, nationality_name, citizenship_qids):
    """True if this composer/nationality pair looks like an unverified,
    citizenship-only assignment. citizenship_qids is the composer's raw
    Wikidata P27 claim list (from attributes.citizenship in
    wikidata_relationships.json) -- pure function, caller does its own
    cache-shape reading."""
    exception_names = NEED_TO_CHECK_EXCEPTIONS.get(wikidata_id)
    if exception_names is not None and nationality_name in exception_names:
        return True
    if wikidata_id in VERIFIED_NOT_NEEDING_CHECK:
        return False
    if composer_id >= MIN_RELATION_DISCOVERY_COMPOSER_ID and len(citizenship_qids) == 1:
        return CITIZENSHIP_TO_NATIONALITY.get(citizenship_qids[0]) == nationality_name
    return False
