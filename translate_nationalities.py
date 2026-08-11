"""One-time LLM-translated nationality_names for every nationalities.name
currently in the DB, into the 12 planned languages
(hu/es/fr/en/de/cs/uk/it/hr/pl/ru/nl -- see TARGET_LANGUAGES in
fetch_wikidata_relationships.py).

Unlike every other *_names table in this repo (genre_names,
instrument_names, work_names, composer_alt_names), this isn't sourced from
Wikidata -- nationalities has no wikidata_id (see its comment in
schema.sql: it's a lossy best-effort parse of free-text source strings,
not a clean per-entity concept with its own QID). These are plain demonym
adjectives ("German", "Hungarian", "French"), not proper nouns, so
translating them directly is safe and unambiguous the way guessing a
person's name spelling in another language is not (see
feedback_dont_guess_uncertain_translations.md) -- there's exactly one
correct word for "French" in Italian.

"en" is only included for the handful of cases where a distinct English
adjectival form actually differs from nationalities.name (there are none
currently -- nationalities.name already IS the English form -- so "en" is
omitted throughout, same reasoning as composer_alt_names skipping "en").

Deliberately skips 2 rows in `nationalities` that aren't real demonyms to
begin with, so translating them would just manufacture false precision --
"Frankish? (Arles/Burgundy)" and "probably French or German", where the
uncertainty is already part of the English source text itself. (Three
other bad rows -- "Denmark", "Egypt", "Finland", raw country names instead
of "Danish"/"Egyptian"/"Finnish" -- were fixed at the source by merging
their composer_nationalities rows onto the existing correct
Danish/Egyptian/Finnish rows and deleting the bad ones, not worked around
here.) These 2 just fall back to their (already imperfect) English
display, same as any nationality this script hasn't reached yet.

Usage:
    python3 translate_nationalities.py
"""
import psycopg2

# {nationalities.name: {language: translation}}
TRANSLATIONS = {
    "Albanian": {"hu": "albán", "es": "albanés", "fr": "albanais", "de": "albanisch", "cs": "albánský", "uk": "албанський", "it": "albanese", "hr": "albanski", "pl": "albański", "ru": "албанский", "nl": "Albanees"},
    "Algerian": {"hu": "algériai", "es": "argelino", "fr": "algérien", "de": "algerisch", "cs": "alžírský", "uk": "алжирський", "it": "algerino", "hr": "alžirski", "pl": "algierski", "ru": "алжирский", "nl": "Algerijns"},
    "American": {"hu": "amerikai", "es": "estadounidense", "fr": "américain", "de": "amerikanisch", "cs": "americký", "uk": "американський", "it": "americano", "hr": "američki", "pl": "amerykański", "ru": "американский", "nl": "Amerikaans"},
    "Argentine": {"hu": "argentin", "es": "argentino", "fr": "argentin", "de": "argentinisch", "cs": "argentinský", "uk": "аргентинський", "it": "argentino", "hr": "argentinski", "pl": "argentyński", "ru": "аргентинский", "nl": "Argentijns"},
    "Armenian": {"hu": "örmény", "es": "armenio", "fr": "arménien", "de": "armenisch", "cs": "arménský", "uk": "вірменський", "it": "armeno", "hr": "armenski", "pl": "ormiański", "ru": "армянский", "nl": "Armeens"},
    "Australian": {"hu": "ausztrál", "es": "australiano", "fr": "australien", "de": "australisch", "cs": "australský", "uk": "австралійський", "it": "australiano", "hr": "australski", "pl": "australijski", "ru": "австралийский", "nl": "Australisch"},
    "Austrian": {"hu": "osztrák", "es": "austríaco", "fr": "autrichien", "de": "österreichisch", "cs": "rakouský", "uk": "австрійський", "it": "austriaco", "hr": "austrijski", "pl": "austriacki", "ru": "австрийский", "nl": "Oostenrijks"},
    "Azerbaijani": {"hu": "azerbajdzsáni", "es": "azerbaiyano", "fr": "azerbaïdjanais", "de": "aserbaidschanisch", "cs": "ázerbájdžánský", "uk": "азербайджанський", "it": "azero", "hr": "azerbajdžanski", "pl": "azerski", "ru": "азербайджанский", "nl": "Azerbeidzjaans"},
    "Bahamian": {"hu": "bahamai", "es": "bahameño", "fr": "bahaméen", "de": "bahamaisch", "cs": "bahamský", "uk": "багамський", "it": "bahamense", "hr": "bahamski", "pl": "bahamski", "ru": "багамский", "nl": "Bahamaans"},
    "Bahraini": {"hu": "bahreini", "es": "bareiní", "fr": "bahreïnien", "de": "bahrainisch", "cs": "bahrajnský", "uk": "бахрейнський", "it": "bahreinita", "hr": "bahreinski", "pl": "bahrajński", "ru": "бахрейнский", "nl": "Bahreins"},
    "Bangladeshi": {"hu": "bangladesi", "es": "bangladesí", "fr": "bangladais", "de": "bangladeschisch", "cs": "bangladéšský", "uk": "бангладеський", "it": "bangladese", "hr": "bangladeški", "pl": "bangladeski", "ru": "бангладешский", "nl": "Bengalees"},
    "Belarusian": {"hu": "belarusz", "es": "bielorruso", "fr": "biélorusse", "de": "belarussisch", "cs": "běloruský", "uk": "білоруський", "it": "bielorusso", "hr": "bjeloruski", "pl": "białoruski", "ru": "белорусский", "nl": "Wit-Russisch"},
    "Belgian": {"hu": "belga", "es": "belga", "fr": "belge", "de": "belgisch", "cs": "belgický", "uk": "бельгійський", "it": "belga", "hr": "belgijski", "pl": "belgijski", "ru": "бельгийский", "nl": "Belgisch"},
    "Belizean": {"hu": "belize-i", "es": "beliceño", "fr": "bélizien", "de": "belizisch", "cs": "belizský", "uk": "белізький", "it": "beliziano", "hr": "belizeanski", "pl": "belizeński", "ru": "белизский", "nl": "Belizaans"},
    "Bohemian": {"hu": "cseh (bohémiai)", "es": "bohemio", "fr": "bohémien", "de": "böhmisch", "cs": "český (Čechy)", "uk": "богемський", "it": "boemo", "hr": "češki (Bohemija)", "pl": "czeski (Czechy)", "ru": "богемский", "nl": "Boheems"},
    "Bolivian": {"hu": "bolíviai", "es": "boliviano", "fr": "bolivien", "de": "bolivianisch", "cs": "bolivijský", "uk": "болівійський", "it": "boliviano", "hr": "bolivijski", "pl": "boliwijski", "ru": "боливийский", "nl": "Boliviaans"},
    "Bosnia and Herzegovina": {"hu": "bosznia-hercegovinai", "es": "bosnioherzegovino", "fr": "bosnien", "de": "bosnisch-herzegowinisch", "cs": "bosensko-hercegovinský", "uk": "боснійсько-герцеговинський", "it": "bosniaco-erzegovese", "hr": "bosanskohercegovački", "pl": "bośniacko-hercegowiński", "ru": "боснийско-герцеговинский", "nl": "Bosnisch-Herzegovijns"},
    "Bosnian": {"hu": "boszniai", "es": "bosnio", "fr": "bosniaque", "de": "bosnisch", "cs": "bosenský", "uk": "боснійський", "it": "bosniaco", "hr": "bosanski", "pl": "bośniacki", "ru": "боснийский", "nl": "Bosnisch"},
    "Brazilian": {"hu": "brazil", "es": "brasileño", "fr": "brésilien", "de": "brasilianisch", "cs": "brazilský", "uk": "бразильський", "it": "brasiliano", "hr": "brazilski", "pl": "brazylijski", "ru": "бразильский", "nl": "Braziliaans"},
    "British": {"hu": "brit", "es": "británico", "fr": "britannique", "de": "britisch", "cs": "britský", "uk": "британський", "it": "britannico", "hr": "britanski", "pl": "brytyjski", "ru": "британский", "nl": "Brits"},
    "Bulgarian": {"hu": "bolgár", "es": "búlgaro", "fr": "bulgare", "de": "bulgarisch", "cs": "bulharský", "uk": "болгарський", "it": "bulgaro", "hr": "bugarski", "pl": "bułgarski", "ru": "болгарский", "nl": "Bulgaars"},
    "Burgundian": {"hu": "burgundiai", "es": "borgoñón", "fr": "bourguignon", "de": "burgundisch", "cs": "burgundský", "uk": "бургундський", "it": "borgognone", "hr": "burgundski", "pl": "burgundzki", "ru": "бургундский", "nl": "Bourgondisch"},
    "Buryat": {"hu": "burját", "es": "buriato", "fr": "bouriate", "de": "burjatisch", "cs": "burjatský", "uk": "бурятський", "it": "buriato", "hr": "burjatski", "pl": "buriacki", "ru": "бурятский", "nl": "Boerjatisch"},
    "Cambodian": {"hu": "kambodzsai", "es": "camboyano", "fr": "cambodgien", "de": "kambodschanisch", "cs": "kambodžský", "uk": "камбоджійський", "it": "cambogiano", "hr": "kambodžanski", "pl": "kambodżański", "ru": "камбоджийский", "nl": "Cambodjaans"},
    "Canadian": {"hu": "kanadai", "es": "canadiense", "fr": "canadien", "de": "kanadisch", "cs": "kanadský", "uk": "канадський", "it": "canadese", "hr": "kanadski", "pl": "kanadyjski", "ru": "канадский", "nl": "Canadees"},
    "Catalan": {"hu": "katalán", "es": "catalán", "fr": "catalan", "de": "katalanisch", "cs": "katalánský", "uk": "каталонський", "it": "catalano", "hr": "katalonski", "pl": "kataloński", "ru": "каталонский", "nl": "Catalaans"},
    "Chilean": {"hu": "chilei", "es": "chileno", "fr": "chilien", "de": "chilenisch", "cs": "chilský", "uk": "чилійський", "it": "cileno", "hr": "čileanski", "pl": "chilijski", "ru": "чилийский", "nl": "Chileens"},
    "Chinese": {"hu": "kínai", "es": "chino", "fr": "chinois", "de": "chinesisch", "cs": "čínský", "uk": "китайський", "it": "cinese", "hr": "kineski", "pl": "chiński", "ru": "китайский", "nl": "Chinees"},
    "Colombian": {"hu": "kolumbiai", "es": "colombiano", "fr": "colombien", "de": "kolumbianisch", "cs": "kolumbijský", "uk": "колумбійський", "it": "colombiano", "hr": "kolumbijski", "pl": "kolumbijski", "ru": "колумбийский", "nl": "Colombiaans"},
    "Costa Rican": {"hu": "costa rica-i", "es": "costarricense", "fr": "costaricien", "de": "costa-ricanisch", "cs": "kostarický", "uk": "костариканський", "it": "costaricano", "hr": "kostarikanski", "pl": "kostarykański", "ru": "костариканский", "nl": "Costa Ricaans"},
    "Croatian": {"hu": "horvát", "es": "croata", "fr": "croate", "de": "kroatisch", "cs": "chorvatský", "uk": "хорватський", "it": "croato", "hr": "hrvatski", "pl": "chorwacki", "ru": "хорватский", "nl": "Kroatisch"},
    "Cuban": {"hu": "kubai", "es": "cubano", "fr": "cubain", "de": "kubanisch", "cs": "kubánský", "uk": "кубинський", "it": "cubano", "hr": "kubanski", "pl": "kubański", "ru": "кубинский", "nl": "Cubaans"},
    "Curaçaoan": {"hu": "curaçaói", "es": "curazoleño", "fr": "curaçaoan", "de": "curaçaoisch", "cs": "curaçaoský", "uk": "кюрасаоський", "it": "curacense", "hr": "curaçaoski", "pl": "curaçaoski", "ru": "кюрасаоский", "nl": "Curaçaos"},
    "Cypriot": {"hu": "ciprusi", "es": "chipriota", "fr": "chypriote", "de": "zyprisch", "cs": "kyperský", "uk": "кіпрський", "it": "cipriota", "hr": "ciparski", "pl": "cypryjski", "ru": "кипрский", "nl": "Cypriotisch"},
    "Czech": {"hu": "cseh", "es": "checo", "fr": "tchèque", "de": "tschechisch", "cs": "český", "uk": "чеський", "it": "ceco", "hr": "češki", "pl": "czeski", "ru": "чешский", "nl": "Tsjechisch"},
    "Danish": {"hu": "dán", "es": "danés", "fr": "danois", "de": "dänisch", "cs": "dánský", "uk": "данський", "it": "danese", "hr": "danski", "pl": "duński", "ru": "датский", "nl": "Deens"},
    "Dutch": {"hu": "holland", "es": "neerlandés", "fr": "néerlandais", "de": "niederländisch", "cs": "nizozemský", "uk": "нідерландський", "it": "olandese", "hr": "nizozemski", "pl": "niderlandzki", "ru": "нидерландский", "nl": "Nederlands"},
    "Ecuadorian": {"hu": "ecuadori", "es": "ecuatoriano", "fr": "équatorien", "de": "ecuadorianisch", "cs": "ekvádorský", "uk": "еквадорський", "it": "ecuadoriano", "hr": "ekvadorski", "pl": "ekwadorski", "ru": "эквадорский", "nl": "Ecuadoraans"},
    "Egyptian": {"hu": "egyiptomi", "es": "egipcio", "fr": "égyptien", "de": "ägyptisch", "cs": "egyptský", "uk": "єгипетський", "it": "egiziano", "hr": "egipatski", "pl": "egipski", "ru": "египетский", "nl": "Egyptisch"},
    "English": {"hu": "angol", "es": "inglés", "fr": "anglais", "de": "englisch", "cs": "anglický", "uk": "англійський", "it": "inglese", "hr": "engleski", "pl": "angielski", "ru": "английский", "nl": "Engels"},
    "Estonian": {"hu": "észt", "es": "estonio", "fr": "estonien", "de": "estnisch", "cs": "estonský", "uk": "естонський", "it": "estone", "hr": "estonski", "pl": "estoński", "ru": "эстонский", "nl": "Estisch"},
    "Ethiopian": {"hu": "etióp", "es": "etíope", "fr": "éthiopien", "de": "äthiopisch", "cs": "etiopský", "uk": "ефіопський", "it": "etiope", "hr": "etiopski", "pl": "etiopski", "ru": "эфиопский", "nl": "Ethiopisch"},
    "European": {"hu": "európai", "es": "europeo", "fr": "européen", "de": "europäisch", "cs": "evropský", "uk": "європейський", "it": "europeo", "hr": "europski", "pl": "europejski", "ru": "европейский", "nl": "Europees"},
    "Faroese": {"hu": "feröeri", "es": "feroés", "fr": "féroïen", "de": "färöisch", "cs": "faerský", "uk": "фарерський", "it": "faroese", "hr": "farski", "pl": "farerski", "ru": "фарерский", "nl": "Faeröers"},
    "Filipino": {"hu": "fülöp-szigeteki", "es": "filipino", "fr": "philippin", "de": "philippinisch", "cs": "filipínský", "uk": "філіппінський", "it": "filippino", "hr": "filipinski", "pl": "filipiński", "ru": "филиппинский", "nl": "Filipijns"},
    "Finnish": {"hu": "finn", "es": "finlandés", "fr": "finlandais", "de": "finnisch", "cs": "finský", "uk": "фінський", "it": "finlandese", "hr": "finski", "pl": "fiński", "ru": "финский", "nl": "Fins"},
    "Flemish": {"hu": "flamand", "es": "flamenco", "fr": "flamand", "de": "flämisch", "cs": "vlámský", "uk": "фламандський", "it": "fiammingo", "hr": "flamanski", "pl": "flamandzki", "ru": "фламандский", "nl": "Vlaams"},
    "Franco-Flemish": {"hu": "francia-flamand", "es": "francoflamenco", "fr": "franco-flamand", "de": "französisch-flämisch", "cs": "francouzsko-vlámský", "uk": "французько-фламандський", "it": "franco-fiammingo", "hr": "francusko-flamanski", "pl": "francusko-flamandzki", "ru": "франко-фламандский", "nl": "Frans-Vlaams"},
    "Frankish": {"hu": "frank", "es": "franco", "fr": "franc", "de": "fränkisch", "cs": "francký", "uk": "франкський", "it": "franco", "hr": "franački", "pl": "frankijski", "ru": "франкский", "nl": "Frankisch"},
    "French": {"hu": "francia", "es": "francés", "fr": "français", "de": "französisch", "cs": "francouzský", "uk": "французький", "it": "francese", "hr": "francuski", "pl": "francuski", "ru": "французский", "nl": "Frans"},
    "Galician": {"hu": "galiciai", "es": "gallego", "fr": "galicien", "de": "galicisch", "cs": "galicijský", "uk": "галісійський", "it": "galiziano", "hr": "galicijski", "pl": "galicyjski", "ru": "галисийский", "nl": "Galicisch"},
    "Georgian": {"hu": "grúz", "es": "georgiano", "fr": "géorgien", "de": "georgisch", "cs": "gruzínský", "uk": "грузинський", "it": "georgiano", "hr": "gruzijski", "pl": "gruziński", "ru": "грузинский", "nl": "Georgisch"},
    "German": {"hu": "német", "es": "alemán", "fr": "allemand", "de": "deutsch", "cs": "německý", "uk": "німецький", "it": "tedesco", "hr": "njemački", "pl": "niemiecki", "ru": "немецкий", "nl": "Duits"},
    "Ghanaian": {"hu": "ghánai", "es": "ghanés", "fr": "ghanéen", "de": "ghanaisch", "cs": "ghanský", "uk": "ганський", "it": "ghanese", "hr": "ganski", "pl": "ghański", "ru": "ганский", "nl": "Ghanees"},
    "Greek": {"hu": "görög", "es": "griego", "fr": "grec", "de": "griechisch", "cs": "řecký", "uk": "грецький", "it": "greco", "hr": "grčki", "pl": "grecki", "ru": "греческий", "nl": "Grieks"},
    "Guatemalan": {"hu": "guatemalai", "es": "guatemalteco", "fr": "guatémaltèque", "de": "guatemaltekisch", "cs": "guatemalský", "uk": "гватемальський", "it": "guatemalteco", "hr": "gvatemalski", "pl": "gwatemalski", "ru": "гватемальский", "nl": "Guatemalteeks"},
    "Haitian": {"hu": "haiti", "es": "haitiano", "fr": "haïtien", "de": "haitianisch", "cs": "haitský", "uk": "гаїтянський", "it": "haitiano", "hr": "haićanski", "pl": "haitański", "ru": "гаитянский", "nl": "Haïtiaans"},
    "Hong Kong": {"hu": "hongkongi", "es": "hongkonés", "fr": "hongkongais", "de": "hongkongerisch", "cs": "hongkongský", "uk": "гонконгський", "it": "hongkonghese", "hr": "hongkonški", "pl": "hongkoński", "ru": "гонконгский", "nl": "Hongkongs"},
    "Hungarian": {"hu": "magyar", "es": "húngaro", "fr": "hongrois", "de": "ungarisch", "cs": "maďarský", "uk": "угорський", "it": "ungherese", "hr": "mađarski", "pl": "węgierski", "ru": "венгерский", "nl": "Hongaars"},
    "Icelandic": {"hu": "izlandi", "es": "islandés", "fr": "islandais", "de": "isländisch", "cs": "islandský", "uk": "ісландський", "it": "islandese", "hr": "islandski", "pl": "islandzki", "ru": "исландский", "nl": "IJslands"},
    "Indian": {"hu": "indiai", "es": "indio", "fr": "indien", "de": "indisch", "cs": "indický", "uk": "індійський", "it": "indiano", "hr": "indijski", "pl": "indyjski", "ru": "индийский", "nl": "Indiaas"},
    "Indonesian": {"hu": "indonéz", "es": "indonesio", "fr": "indonésien", "de": "indonesisch", "cs": "indonéský", "uk": "індонезійський", "it": "indonesiano", "hr": "indonezijski", "pl": "indonezyjski", "ru": "индонезийский", "nl": "Indonesisch"},
    "Iranian": {"hu": "iráni", "es": "iraní", "fr": "iranien", "de": "iranisch", "cs": "íránský", "uk": "іранський", "it": "iraniano", "hr": "iranski", "pl": "irański", "ru": "иранский", "nl": "Iraans"},
    "Iraqi": {"hu": "iraki", "es": "iraquí", "fr": "irakien", "de": "irakisch", "cs": "irácký", "uk": "іракський", "it": "iracheno", "hr": "irački", "pl": "iracki", "ru": "иракский", "nl": "Iraaks"},
    "Irish": {"hu": "ír", "es": "irlandés", "fr": "irlandais", "de": "irisch", "cs": "irský", "uk": "ірландський", "it": "irlandese", "hr": "irski", "pl": "irlandzki", "ru": "ирландский", "nl": "Iers"},
    "Israeli": {"hu": "izraeli", "es": "israelí", "fr": "israélien", "de": "israelisch", "cs": "izraelský", "uk": "ізраїльський", "it": "israeliano", "hr": "izraelski", "pl": "izraelski", "ru": "израильский", "nl": "Israëlisch"},
    "Italian": {"hu": "olasz", "es": "italiano", "fr": "italien", "de": "italienisch", "cs": "italský", "uk": "італійський", "it": "italiano", "hr": "talijanski", "pl": "włoski", "ru": "итальянский", "nl": "Italiaans"},
    "Jamaican": {"hu": "jamaicai", "es": "jamaicano", "fr": "jamaïcain", "de": "jamaikanisch", "cs": "jamajský", "uk": "ямайський", "it": "giamaicano", "hr": "jamajčanski", "pl": "jamajski", "ru": "ямайский", "nl": "Jamaicaans"},
    "Japanese": {"hu": "japán", "es": "japonés", "fr": "japonais", "de": "japanisch", "cs": "japonský", "uk": "японський", "it": "giapponese", "hr": "japanski", "pl": "japoński", "ru": "японский", "nl": "Japans"},
    "Kazakhstani": {"hu": "kazah", "es": "kazajo", "fr": "kazakh", "de": "kasachisch", "cs": "kazašský", "uk": "казахський", "it": "kazako", "hr": "kazahstanski", "pl": "kazachski", "ru": "казахский", "nl": "Kazachs"},
    "Korean": {"hu": "koreai", "es": "coreano", "fr": "coréen", "de": "koreanisch", "cs": "korejský", "uk": "корейський", "it": "coreano", "hr": "korejski", "pl": "koreański", "ru": "корейский", "nl": "Koreaans"},
    "Kosovar": {"hu": "koszovói", "es": "kosovar", "fr": "kosovar", "de": "kosovarisch", "cs": "kosovský", "uk": "косовський", "it": "kosovaro", "hr": "kosovski", "pl": "kosowski", "ru": "косовский", "nl": "Kosovaars"},
    "Kyrgyzstani": {"hu": "kirgiz", "es": "kirguís", "fr": "kirghize", "de": "kirgisisch", "cs": "kyrgyzský", "uk": "киргизький", "it": "kirghiso", "hr": "kirgiski", "pl": "kirgiski", "ru": "киргизский", "nl": "Kirgizisch"},
    "Latvian": {"hu": "lett", "es": "letón", "fr": "letton", "de": "lettisch", "cs": "lotyšský", "uk": "латвійський", "it": "lettone", "hr": "latvijski", "pl": "łotewski", "ru": "латвийский", "nl": "Lets"},
    "Lebanese": {"hu": "libanoni", "es": "libanés", "fr": "libanais", "de": "libanesisch", "cs": "libanonský", "uk": "ліванський", "it": "libanese", "hr": "libanonski", "pl": "libański", "ru": "ливанский", "nl": "Libanees"},
    "Lithuanian": {"hu": "litván", "es": "lituano", "fr": "lituanien", "de": "litauisch", "cs": "litevský", "uk": "литовський", "it": "lituano", "hr": "litavski", "pl": "litewski", "ru": "литовский", "nl": "Litouws"},
    "Luxembourgish": {"hu": "luxemburgi", "es": "luxemburgués", "fr": "luxembourgeois", "de": "luxemburgisch", "cs": "lucemburský", "uk": "люксембурзький", "it": "lussemburghese", "hr": "luksemburški", "pl": "luksemburski", "ru": "люксембургский", "nl": "Luxemburgs"},
    "Macedonian": {"hu": "macedón", "es": "macedonio", "fr": "macédonien", "de": "mazedonisch", "cs": "makedonský", "uk": "македонський", "it": "macedone", "hr": "makedonski", "pl": "macedoński", "ru": "македонский", "nl": "Macedonisch"},
    "Maltese": {"hu": "máltai", "es": "maltés", "fr": "maltais", "de": "maltesisch", "cs": "maltský", "uk": "мальтійський", "it": "maltese", "hr": "malteški", "pl": "maltański", "ru": "мальтийский", "nl": "Maltees"},
    "Mexican": {"hu": "mexikói", "es": "mexicano", "fr": "mexicain", "de": "mexikanisch", "cs": "mexický", "uk": "мексиканський", "it": "messicano", "hr": "meksički", "pl": "meksykański", "ru": "мексиканский", "nl": "Mexicaans"},
    "Moldovan": {"hu": "moldovai", "es": "moldavo", "fr": "moldave", "de": "moldauisch", "cs": "moldavský", "uk": "молдовський", "it": "moldavo", "hr": "moldavski", "pl": "mołdawski", "ru": "молдавский", "nl": "Moldavisch"},
    "Mongolian": {"hu": "mongol", "es": "mongol", "fr": "mongol", "de": "mongolisch", "cs": "mongolský", "uk": "монгольський", "it": "mongolo", "hr": "mongolski", "pl": "mongolski", "ru": "монгольский", "nl": "Mongools"},
    "Netherlandish": {"hu": "németalföldi", "es": "neerlandés (histórico)", "fr": "néerlandais (historique)", "de": "niederländisch (historisch)", "cs": "nizozemský (historický)", "uk": "нідерландський (історичний)", "it": "neerlandese (storico)", "hr": "nizozemski (povijesni)", "pl": "niderlandzki (historyczny)", "ru": "нидерландский (исторический)", "nl": "Nederlands (historisch)"},
    "New Zealander": {"hu": "új-zélandi", "es": "neozelandés", "fr": "néo-zélandais", "de": "neuseeländisch", "cs": "novozélandský", "uk": "новозеландський", "it": "neozelandese", "hr": "novozelandski", "pl": "nowozelandzki", "ru": "новозеландский", "nl": "Nieuw-Zeelands"},
    "Nicaraguan": {"hu": "nicaraguai", "es": "nicaragüense", "fr": "nicaraguayen", "de": "nicaraguanisch", "cs": "nikaragujský", "uk": "нікарагуанський", "it": "nicaraguense", "hr": "nikaragvanski", "pl": "nikaraguański", "ru": "никарагуанский", "nl": "Nicaraguaans"},
    "Nigerian": {"hu": "nigériai", "es": "nigeriano", "fr": "nigérian", "de": "nigerianisch", "cs": "nigerijský", "uk": "нігерійський", "it": "nigeriano", "hr": "nigerijski", "pl": "nigeryjski", "ru": "нигерийский", "nl": "Nigeriaans"},
    "Northern Irish": {"hu": "észak-ír", "es": "norirlandés", "fr": "nord-irlandais", "de": "nordirisch", "cs": "severoirský", "uk": "північноірландський", "it": "nordirlandese", "hr": "sjevernoirski", "pl": "północnoirlandzki", "ru": "североирландский", "nl": "Noord-Iers"},
    "Norwegian": {"hu": "norvég", "es": "noruego", "fr": "norvégien", "de": "norwegisch", "cs": "norský", "uk": "норвезький", "it": "norvegese", "hr": "norveški", "pl": "norweski", "ru": "норвежский", "nl": "Noors"},
    "Occitan": {"hu": "occitán", "es": "occitano", "fr": "occitan", "de": "okzitanisch", "cs": "okcitánský", "uk": "окситанський", "it": "occitano", "hr": "okcitanski", "pl": "oksytański", "ru": "окситанский", "nl": "Occitaans"},
    "Palestinian": {"hu": "palesztin", "es": "palestino", "fr": "palestinien", "de": "palästinensisch", "cs": "palestinský", "uk": "палестинський", "it": "palestinese", "hr": "palestinski", "pl": "palestyński", "ru": "палестинский", "nl": "Palestijns"},
    "Panamanian": {"hu": "panamai", "es": "panameño", "fr": "panaméen", "de": "panamaisch", "cs": "panamský", "uk": "панамський", "it": "panamense", "hr": "panamski", "pl": "panamski", "ru": "панамский", "nl": "Panamees"},
    "Paraguayan": {"hu": "paraguayi", "es": "paraguayo", "fr": "paraguayen", "de": "paraguayisch", "cs": "paraguayský", "uk": "парагвайський", "it": "paraguaiano", "hr": "paragvajski", "pl": "paragwajski", "ru": "парагвайский", "nl": "Paraguayaans"},
    "Peruvian": {"hu": "perui", "es": "peruano", "fr": "péruvien", "de": "peruanisch", "cs": "peruánský", "uk": "перуанський", "it": "peruviano", "hr": "peruanski", "pl": "peruwiański", "ru": "перуанский", "nl": "Peruaans"},
    "Polish": {"hu": "lengyel", "es": "polaco", "fr": "polonais", "de": "polnisch", "cs": "polský", "uk": "польський", "it": "polacco", "hr": "poljski", "pl": "polski", "ru": "польский", "nl": "Pools"},
    "Portuguese": {"hu": "portugál", "es": "portugués", "fr": "portugais", "de": "portugiesisch", "cs": "portugalský", "uk": "португальський", "it": "portoghese", "hr": "portugalski", "pl": "portugalski", "ru": "португальский", "nl": "Portugees"},
    "Puerto Rican": {"hu": "puerto ricó-i", "es": "puertorriqueño", "fr": "portoricain", "de": "puerto-ricanisch", "cs": "portorický", "uk": "пуерториканський", "it": "portoricano", "hr": "portoriканski", "pl": "portorykański", "ru": "пуэрториканский", "nl": "Puerto Ricaans"},
    "Québécois": {"hu": "québeci", "es": "quebequense", "fr": "québécois", "de": "québecisch", "cs": "québecký", "uk": "квебекський", "it": "quebecchese", "hr": "kvebečki", "pl": "quebecki", "ru": "квебекский", "nl": "Québecs"},
    "Romanian": {"hu": "román", "es": "rumano", "fr": "roumain", "de": "rumänisch", "cs": "rumunský", "uk": "румунський", "it": "rumeno", "hr": "rumunjski", "pl": "rumuński", "ru": "румынский", "nl": "Roemeens"},
    "Russian": {"hu": "orosz", "es": "ruso", "fr": "russe", "de": "russisch", "cs": "ruský", "uk": "російський", "it": "russo", "hr": "ruski", "pl": "rosyjski", "ru": "русский", "nl": "Russisch"},
    "Salvadoran": {"hu": "salvadori", "es": "salvadoreño", "fr": "salvadorien", "de": "salvadorianisch", "cs": "salvadorský", "uk": "сальвадорський", "it": "salvadoregno", "hr": "salvadorski", "pl": "salwadorski", "ru": "сальвадорский", "nl": "Salvadoraans"},
    "Scottish": {"hu": "skót", "es": "escocés", "fr": "écossais", "de": "schottisch", "cs": "skotský", "uk": "шотландський", "it": "scozzese", "hr": "škotski", "pl": "szkocki", "ru": "шотландский", "nl": "Schots"},
    "Serbian": {"hu": "szerb", "es": "serbio", "fr": "serbe", "de": "serbisch", "cs": "srbský", "uk": "сербський", "it": "serbo", "hr": "srpski", "pl": "serbski", "ru": "сербский", "nl": "Servisch"},
    "Slovak": {"hu": "szlovák", "es": "eslovaco", "fr": "slovaque", "de": "slowakisch", "cs": "slovenský", "uk": "словацький", "it": "slovacco", "hr": "slovački", "pl": "słowacki", "ru": "словацкий", "nl": "Slowaaks"},
    "Slovenian": {"hu": "szlovén", "es": "esloveno", "fr": "slovène", "de": "slowenisch", "cs": "slovinský", "uk": "словенський", "it": "sloveno", "hr": "slovenski", "pl": "słoweński", "ru": "словенский", "nl": "Sloveens"},
    "South African": {"hu": "dél-afrikai", "es": "sudafricano", "fr": "sud-africain", "de": "südafrikanisch", "cs": "jihoafrický", "uk": "південноафриканський", "it": "sudafricano", "hr": "južnoafrički", "pl": "południowoafrykański", "ru": "южноафриканский", "nl": "Zuid-Afrikaans"},
    "South Korean": {"hu": "dél-koreai", "es": "surcoreano", "fr": "sud-coréen", "de": "südkoreanisch", "cs": "jihokorejský", "uk": "південнокорейський", "it": "sudcoreano", "hr": "južnokorejski", "pl": "południowokoreański", "ru": "южнокорейский", "nl": "Zuid-Koreaans"},
    "Soviet": {"hu": "szovjet", "es": "soviético", "fr": "soviétique", "de": "sowjetisch", "cs": "sovětský", "uk": "радянський", "it": "sovietico", "hr": "sovjetski", "pl": "radziecki", "ru": "советский", "nl": "Sovjet"},
    "Spanish": {"hu": "spanyol", "es": "español", "fr": "espagnol", "de": "spanisch", "cs": "španělský", "uk": "іспанський", "it": "spagnolo", "hr": "španjolski", "pl": "hiszpański", "ru": "испанский", "nl": "Spaans"},
    "Sri Lankan": {"hu": "srí lanka-i", "es": "esrilanqués", "fr": "srilankais", "de": "sri-lankisch", "cs": "srílanský", "uk": "шрі-ланкійський", "it": "singalese", "hr": "šrilanski", "pl": "lankijski", "ru": "шри-ланкийский", "nl": "Sri Lankaans"},
    "Swedish": {"hu": "svéd", "es": "sueco", "fr": "suédois", "de": "schwedisch", "cs": "švédský", "uk": "шведський", "it": "svedese", "hr": "švedski", "pl": "szwedzki", "ru": "шведский", "nl": "Zweeds"},
    "Swiss": {"hu": "svájci", "es": "suizo", "fr": "suisse", "de": "schweizerisch", "cs": "švýcarský", "uk": "швейцарський", "it": "svizzero", "hr": "švicarski", "pl": "szwajcarski", "ru": "швейцарский", "nl": "Zwitsers"},
    "Syrian": {"hu": "szíriai", "es": "sirio", "fr": "syrien", "de": "syrisch", "cs": "syrský", "uk": "сирійський", "it": "siriano", "hr": "sirijski", "pl": "syryjski", "ru": "сирийский", "nl": "Syrisch"},
    "Taiwanese": {"hu": "tajvani", "es": "taiwanés", "fr": "taïwanais", "de": "taiwanisch", "cs": "tchajwanský", "uk": "тайванський", "it": "taiwanese", "hr": "tajvanski", "pl": "tajwański", "ru": "тайваньский", "nl": "Taiwanees"},
    "Tajik": {"hu": "tádzsik", "es": "tayiko", "fr": "tadjik", "de": "tadschikisch", "cs": "tádžický", "uk": "таджицький", "it": "tagiko", "hr": "tadžički", "pl": "tadżycki", "ru": "таджикский", "nl": "Tadzjieks"},
    "Thai": {"hu": "thaiföldi", "es": "tailandés", "fr": "thaïlandais", "de": "thailändisch", "cs": "thajský", "uk": "тайський", "it": "thailandese", "hr": "tajlandski", "pl": "tajski", "ru": "тайский", "nl": "Thais"},
    "Tunisian": {"hu": "tunéziai", "es": "tunecino", "fr": "tunisien", "de": "tunesisch", "cs": "tuniský", "uk": "туніський", "it": "tunisino", "hr": "tuniski", "pl": "tunezyjski", "ru": "тунисский", "nl": "Tunesisch"},
    "Turkish": {"hu": "török", "es": "turco", "fr": "turc", "de": "türkisch", "cs": "turecký", "uk": "турецький", "it": "turco", "hr": "turski", "pl": "turecki", "ru": "турецкий", "nl": "Turks"},
    "Turkmenistani": {"hu": "türkmén", "es": "turcomano", "fr": "turkmène", "de": "turkmenisch", "cs": "turkmenský", "uk": "туркменський", "it": "turkmeno", "hr": "turkmenistanski", "pl": "turkmeński", "ru": "туркменский", "nl": "Turkmeens"},
    "Ugandan": {"hu": "ugandai", "es": "ugandés", "fr": "ougandais", "de": "ugandisch", "cs": "ugandský", "uk": "угандійський", "it": "ugandese", "hr": "ugandski", "pl": "ugandyjski", "ru": "угандийский", "nl": "Oegandees"},
    "Ukrainian": {"hu": "ukrán", "es": "ucraniano", "fr": "ukrainien", "de": "ukrainisch", "cs": "ukrajinský", "uk": "український", "it": "ucraino", "hr": "ukrajinski", "pl": "ukraiński", "ru": "украинский", "nl": "Oekraïens"},
    "Uruguayan": {"hu": "uruguayi", "es": "uruguayo", "fr": "uruguayen", "de": "uruguayisch", "cs": "uruguayský", "uk": "уругвайський", "it": "uruguaiano", "hr": "urugvajski", "pl": "urugwajski", "ru": "уругвайский", "nl": "Uruguayaans"},
    "Uzbekistani": {"hu": "üzbég", "es": "uzbeko", "fr": "ouzbek", "de": "usbekisch", "cs": "uzbecký", "uk": "узбецький", "it": "uzbeko", "hr": "uzbekistanski", "pl": "uzbecki", "ru": "узбекский", "nl": "Oezbeeks"},
    "Venezuelan": {"hu": "venezuelai", "es": "venezolano", "fr": "vénézuélien", "de": "venezolanisch", "cs": "venezuelský", "uk": "венесуельський", "it": "venezuelano", "hr": "venezuelanski", "pl": "wenezuelski", "ru": "венесуэльский", "nl": "Venezolaans"},
    "Vietnamese": {"hu": "vietnami", "es": "vietnamita", "fr": "vietnamien", "de": "vietnamesisch", "cs": "vietnamský", "uk": "в'єтнамський", "it": "vietnamita", "hr": "vijetnamski", "pl": "wietnamski", "ru": "вьетнамский", "nl": "Vietnamees"},
    "Welsh": {"hu": "walesi", "es": "galés", "fr": "gallois", "de": "walisisch", "cs": "velšský", "uk": "валлійський", "it": "gallese", "hr": "velški", "pl": "walijski", "ru": "валлийский", "nl": "Welsh"},
    "Western European": {"hu": "nyugat-európai", "es": "europeo occidental", "fr": "ouest-européen", "de": "westeuropäisch", "cs": "západoevropský", "uk": "західноєвропейський", "it": "europeo occidentale", "hr": "zapadnoeuropski", "pl": "zachodnioeuropejski", "ru": "западноевропейский", "nl": "West-Europees"},
}

UPSERT_SQL = """
    INSERT INTO nationality_names (nationality_id, language, name)
    VALUES (%s, %s, %s)
    ON CONFLICT (nationality_id, language) DO UPDATE SET name = EXCLUDED.name
"""


def main():
    conn = psycopg2.connect()
    loaded = 0
    skipped = []
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id, name FROM nationalities")
                for nationality_id, name in cur.fetchall():
                    translations = TRANSLATIONS.get(name)
                    if translations is None:
                        skipped.append(name)
                        continue
                    for language, translated in translations.items():
                        cur.execute(UPSERT_SQL, (nationality_id, language, translated))
                        loaded += 1
    finally:
        conn.close()
    print(f"Loaded {loaded} nationality translations.")
    if skipped:
        print(f"{len(skipped)} nationalities with no translation entry: {skipped}")


if __name__ == "__main__":
    main()
