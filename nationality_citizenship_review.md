# Nationality mapping review — composers loaded 2026-08-11 (relation-discovery batch)

Each composer's Wikidata citizenship (P27), grouped by country/political entity, cross-referenced
against composers.id so a nationality tag can be assigned by hand. Several of these are the same
kind of defunct-state-vs-actual-origin judgment call already resolved elsewhere this session
(e.g. Kingdom of Prussia -> German for Nicodé, Austro-Hungarian -> Italian for Smareglia,
Soviet Union -> Russian/Georgian/Armenian by actual origin) — same treatment likely applies here.
Composers with multiple citizenships appear in more than one section below.

## STATUS (2026-08-12)

Three categories of groups in this file, at different stages:

1. **Genuinely multi-nation historical entities** (Russian Empire, Soviet Union, Czechoslovakia,
   Kingdom of Bohemia, Austrian Empire, Austria-Hungary, Cisleithania, Yugoslavia/Slovenia) --
   RESOLVED, one composer at a time, via P19 birthplace + P27 citizenships cross-checked against
   each composer's own Wikipedia article (WP prose wins when it disagrees with a bare birthplace
   inference -- see the Fritz Zweig/Tedesco precedents inline below). Sources saved to
   data/wikipedia_pages/. Two composers turned out not to be composers at all and were deleted
   (Leó Popper, Celina Szymanowska -- see their notes below).

2. **UK-related groups** (United Kingdom, United Kingdom of Great Britain and Ireland, Kingdom of
   Great Britain, Kingdom of England, British Raj) -- deliberately left unassigned, not resolved.
   See the note under "United Kingdom" below for why.

3. **Single-nation groups** (France, United States, Spain, Germany, and 60+ others that each map
   1:1 to one modern/historical nation, e.g. "Kingdom of Bavaria" -> German) -- RESOLVED via bulk
   assignment: 423 composers across these groups, 400 with only one candidate nationality
   (assigned directly, no research needed), 23 appearing in *more than one* single-nation group
   (a real multi-citizenship conflict) -- each of those 23 individually researched to keep only
   the better-supported nationality, not a compound. See the "MULTI-CITIZENSHIP RESOLUTIONS"
   list below for all 23, with reasoning.

Still open: **Principality of Transylvania, County of Flanders, New Spain, Free City of Danzig**
(genuinely contested small groups, same treatment as category 1 above still needed) and **"No
citizenship on Wikidata at all" (86 composers)** (no P27 to disambiguate from at all -- needs a
different approach entirely).

### MULTI-CITIZENSHIP RESOLUTIONS (the 23 conflicts from category 3)

- [9996] Camille-Marie Stamaty -- French (explicitly "French pianist" per multiple sources;
  born Rome to a Greek father/French mother, but Rome was incidental -- his father was posted
  there as French consul)
- [10088] José Antonio Santesteban -- Spanish (Basque composer, born/died San Sebastián; no
  French connection found in any source despite a French P27 claim on Wikidata)
- [10181] Sergio Ortega -- Chilean (composer of Chile's Unidad Popular-era political anthems
  "Venceremos"/"El pueblo unido jamás será vencido"; died in Paris exile after the 1973 coup,
  but Chilean identity is foundational and explicit)
- [10205] Chris McGregor -- South African (born in the Transkei to Scottish missionary parents,
  founded the Blue Notes in South Africa in 1963; left for France/UK only in 1964 due to
  apartheid-era harassment of his mixed-race band)
- [10213] György Kurtág Jr. -- Hungarian (explicitly "Hungarian composer... based in Bordeaux,
  France"; son of composer György Kurtág, left Hungary for France only in the early 1980s)
- [10452] Walter Gieseking -- German (born Lyon, France to German parents, but universally
  identified as a German pianist by career and reputation)
- [10523] Walter Morse Rummel -- French (of German-English descent, born Berlin; explicitly
  "active mainly in France", associated with Debussy -- no single source privileges German or
  American over his French professional identity)
- [10103] Theodor W. Adorno -- German (also had US and Swiss residency during/after Nazi exile,
  but German is his foundational and primary identity throughout)
- [10127] María Grever -- Mexican ("the first female Mexican composer to achieve international
  acclaim"; her whole songwriting identity centered on sharing Mexican musical heritage)
- [10184] Moriz Rosenthal -- Polish (explicitly "Polish pianist and composer" despite being born
  in Lemberg, Austrian Empire, and later residing/dying in the US)
- [10231] Enrique Jordá -- Spanish ("Spanish-American conductor", born San Sebastián; his most
  historically notable recordings were of Spanish repertoire)
- [10294] Alejandro Planchart -- American ("Venezuelan-American musicologist", born Caracas but
  his entire scholarly career (Yale, Harvard PhD, UC Santa Barbara professorship) was US-based;
  multiple sources (prabook) call him simply "American")
- [10435] Curt Sachs -- German (predominantly described as "German musicologist" across sources
  despite fleeing Nazi Germany for the US in 1937, where he spent his last 22 years)
- [10479] Margaret Hamerik -- Danish (born Margaret Williams in Tennessee, USA, but consistently
  identified as a "Danish composer" -- married composer Asger Hamerik and emigrated to
  Copenhagen in 1898, where her documented career/identity is centered)
- [10519] Erich Leinsdorf -- American (born Vienna as Erich Landauer; sources describe him evenly
  as "Austrian-born American" without privileging either, but his defining, decades-long career
  (Cleveland, Rochester, the Met, Boston Symphony) was entirely in the US)
- [10554] Eduardo Mata -- Mexican (born Mexico City, internationally active but identity
  foundationally Mexican)
- [10087] Miguel Pontaza -- Guatemalan (maestro de capilla at Guatemala City Cathedral,
  documented as part of Guatemala's colonial musical tradition; no personal Spain-specific claim
  found -- the Wikidata "Spain" P27 likely just reflects colonial-subject-of-the-crown status,
  not personal identity)
- [10290] Julio Estrada -- Mexican (born and raised in Mexico City; family exiled from Spain in
  1941, so the Spain connection is ancestral, not personal)
- [10428] Adolfo Salazar -- Spanish (explicitly "eminent Spanish musicologist"; his formative and
  most historically significant career -- founding the Sociedad Nacional de Música, music
  criticism for Madrid's El Sol -- was in Spain before his 1939 exile to Mexico at the end of
  his career)
- [10130] Sergiu Celibidache -- Romanian (multiple sources identify Romanian nationality as his
  primary identity despite his career being centered on the Munich Philharmonic in Germany)
- [10420] Csaba Deák -- Swedish (explicitly "Hungarian-born Swedish composer" -- same
  origin-vs-adopted-identity "X-born Y" pattern as Raff/Franck/Gilmore elsewhere in this DB,
  where Y is the primary nationality)
- [10518] Erich Kleiber -- Austrian (born Vienna; later became an Argentine citizen after
  emigrating in protest of the Nazis in 1933, but his foundational identity and most
  historically significant work -- championing the premiere of Berg's Wozzeck in Berlin --
  is Austrian)
- [10454] Victor Smolski -- Belarusian (explicitly "Belarusian... not Russian" per source, born
  Minsk; long-time member of the German metal band Rage doesn't change his origin-nationality)

## France (72)
- [9996] Camille-Marie Stamaty (1811–1870)
- [10015] Gabriel Verdalle (1847–1918)
- [10016] Blanche Lucas (1874–1956)
- [10028] Jean Dattas (1919–1975)
- [10033] Jean Boyer (1948–2004)
- [10037] Samuel Liégeon (1984–)
- [10044] Hippolyte François Rabaud (1839–1900)
- [10054] Phédora Pierret (1808–1869)
- [10062] Elliott Armen (?–)
- [10066] E. Robert Schmitz (1889–1949)
- [10077] Pierre-Joseph-Guillaume Zimmermann (1785–1853)
- [10079] Hyacinthe Klosé (1808–1880)
- [10088] José Antonio Santesteban (1835–1906)
- [10091] Joseph Meifred (1791–1867)
- [10092] Jean-Claude Casadesus (1935–)
- [10097] François Benoist (1794–1878)
- [10099] Frédéric Blanc (?–)
- [10100] François Couperin the elder (?–)
- [10107] Clément Ducol (1981–)
- [10123] Camille Pleyel (1788–1855)
- [10131] Lucien Garban (1877–1959)
- [10137] Jean Hubeau (1917–1992)
- [10155] Louis Thiry (1935–2019)
- [10181] Sergio Ortega (1938–2003)
- [10192] Louis Fleury (1878–1926)
- [10194] Nicolas Couperin (1680–1748)
- [10197] Charles Couperin (1638–1678)
- [10203] Marie-Claire Alain (1926–2013)
- [10205] Chris McGregor (1936–1990)
- [10213] György Kurtág Jr. (1954–)
- [10239] Pantaléon Battu (1799–1870)
- [10241] Richard Hammer (1828–1907)
- [10243] Annie Challan (1940–)
- [10247] Marguerite-Antoinette Couperin (1705–)
- [10248] Auguste Durand (1830–1909)
- [10249] Jean-Pierre Duport (1741–1818)
- [10250] Annette-Julie Nicolò-Isouard (1814–1876)
- [10266] Jeanne Joulain (1920–2010)
- [10269] Joseph Reveyron (1917–2005)
- [10276] Louis Robilliard (1939–)
- [10282] Michel Ciry (1919–2018)
- [10283] Nicolas Séjan (1745–1819)
- [10284] Olivier Bernard (1925–2019)
- [10285] Paul Berthier (1884–1953)
- [10286] Paul Viardot (1857–1941)
- [10287] Romain Didier (1949–)
- [10305] Pierre-Joseph Candeille (1744–1827)
- [10306] Agnelle Bundervoët (1922–2015)
- [10314] Jean Doyen (1907–1982)
- [10321] Pierre Sancan (1916–2008)
- [10324] Louise Aglaé Massart (1827–1887)
- [10327] Louis Fourestier (1892–1976)
- [10350] Anna de La Grange (1825–1905)
- [10362] Alphonse Leduc (1804–1868)
- [10371] Pierre Baillot (1771–1842)
- [10372] Eugène-Philippe Bellenot (1860–1928)
- [10374] Auguste Franchomme (1808–1884)
- [10440] Antoine-François Marmontel (1816–1898)
- [10452] Walter Gieseking (1895–1956)
- [10463] Jean-Delphin Alard (1815–1888)
- [10464] Adolphe Nourrit (1802–1839)
- [10478] Odile Pierre (1932–2020)
- [10482] Edward Dannreuther (1844–1905)
- [10492] Olivier Latry (1962–)
- [10501] Jean Rousseau (1644–1699)
- [10520] Jules Danbé (1840–1905)
- [10523] Walter Morse Rummel (1887–1953)
- [10525] Émile Desportes (?–)
- [10548] Lazare Lévy (1882–1964)
- [10556] François Habeneck (1781–1849)
- [10557] Marina Scriabine (1911–1998)
- [10570] Francis Chapelet (1934–)

## United States (46)
- [9994] Byron Janis (1928–2024)
- [10004] Charles Seeger (1886–1979)
- [10061] Dorian Rudnytsky (1944–)
- [10068] James Reese Europe (1880–1919)
- [10084] Fred Hersch (1955–)
- [10101] Geoffrey Keezer (1970–)
- [10103] Theodor W. Adorno (1903–1969)
- [10116] Allan Arthur Willman (1909–1987)
- [10127] María Grever (1885–1951)
- [10140] John Hill Hewitt (1801–1890)
- [10148] Willie "The Lion" Smith (1897–1973)
- [10171] Alexander Schreiner (1901–1987)
- [10182] Luke Winslow-King (1983–)
- [10184] Moriz Rosenthal (1862–1946)
- [10187] Eduard Steuermann (1892–1964)
- [10202] Edward Kilenyi (1884–1968)
- [10224] Anoushka Shankar (1981–)
- [10230] Gyan Riley (1977–)
- [10231] Enrique Jordá (1911–1996)
- [10272] William Arms Fisher (1861–1948)
- [10278] Whitney Eugene Thayer (1838–1889)
- [10280] Clara M. Brinkerhoff (1828–)
- [10294] Alejandro Planchart (1935–2019)
- [10296] Donald Byrd (1932–2013)
- [10310] Heinrich Gebhard (1878–1963)
- [10357] Mercer Ellington (1919–1996)
- [10369] Chris Brubeck (1952–)
- [10378] Deborah Holland (1954–)
- [10381] Edward Shippen Barnes (1887–1958)
- [10392] Norah Jones (1979–)
- [10429] Heniot Levy (1879–1945)
- [10435] Curt Sachs (1881–1959)
- [10462] John Woods Duke (1899–1984)
- [10479] Margaret Hamerik (1867–1942)
- [10505] Robert Kapilow (1952–)
- [10508] Russell Sherman (1930–2023)
- [10509] Wesley LaViolette (1894–1978)
- [10510] Sammy Timberg (1903–1992)
- [10511] Saul Goodman (1907–1996)
- [10512] Sebastian Bach Mills (1839–1898)
- [10519] Erich Leinsdorf (1912–1993)
- [10527] Benjamin Johnson Lang (1837–1909)
- [10554] Eduardo Mata (1942–1995)
- [10562] Jennifer Goldsmith (?–)
- [10563] Ellen Goldsmith Edson (?–)

## Spain (43)
- [9999] Carles Santos (1940–2017)
- [10006] Luis Bernardo Jalón (?–1659)
- [10029] José María Echeverría y Urruzola (1855–)
- [10030] Marcelo Settimio (?–1655)
- [10045] Josefina Robledo Gallego (1897–1972)
- [10078] Ramón Carnicer (1789–1855)
- [10080] Manuel Ansola Unzueta (1883–)
- [10085] Iris Azquinezer (?–)
- [10086] Francisco Escudero (1912–2002)
- [10087] Miguel Pontaza (?–1807)
- [10088] José Antonio Santesteban (1835–1906)
- [10129] Benjamín Orbón (1877–1944)
- [10142] Josep Marraco i Ferrer (1835–1913)
- [10164] Luis Sánchez Fernández (1907–1957)
- [10169] José Miró i Anoria (1815–1878)
- [10172] Eduardo López-Chávarri (1871–1970)
- [10176] Joan Baptista  Pujol (1835–1898)
- [10183] Victorí Agustí (1808–1884)
- [10200] Alicia de Larrocha (1923–2009)
- [10211] Ramón Cercós Pérez (1936–)
- [10212] Pedro Fernández de Castilleja (?–)
- [10225] Carmelo Bernaola (1929–2002)
- [10231] Enrique Jordá (1911–1996)
- [10240] Bernardino de Ribera (?–)
- [10290] Julio Estrada (1943–)
- [10293] Pedro Albéniz (1795–1855)
- [10301] Cándido Candi (1844–1911)
- [10317] José Antonio Abad Vidal (?–)
- [10320] Salvador Viniegra y Lasso de la Vega (1862–1914)
- [10323] Frank Marshall (1883–1959)
- [10326] Joaquín Espín y Pérez Colbran (?–)
- [10329] Gaspar Espinosa de los Monteros y Jiménez (?–)
- [10331] Narciso Yepes (1927–1997)
- [10348] Miguel Galiana Folqués (1814–1880)
- [10356] Santiago Riera (1867–)
- [10411] Alonso de Cobaleda (?–1731)
- [10412] Guillermo Massot (?–)
- [10428] Adolfo Salazar (1890–1958)
- [10441] Francisco González Pastor (?–)
- [10447] Matías Durango (?–1698)
- [10455] Tomás Micieces el menor (1655–1718)
- [10468] Enrique Muñoz Rubio (?–)
- [10568] Antonio Trueba Aginagalde (1855–1944)

## Germany (42)
- [9995] Carl Heymann (1854–1922)
- [10072] Helmut Walcha (1907–1991)
- [10098] Friedrich Wilhelm Pixis (1785–1842)
- [10103] Theodor W. Adorno (1903–1969)
- [10120] Franz Eck (?–)
- [10130] Sergiu Celibidache (1912–1996)
- [10136] Theodor Amadeus Müller (1798–1846)
- [10139] Johann Joachim Wachsmann (1787–1853)
- [10143] Karl Walter (1892–1983)
- [10168] Johannes Bonadies (?–)
- [10259] Johann Ambrosius Bach (1645–1695)
- [10271] Erhard Karkoschka (1923–2009)
- [10275] Julius Buths (1851–1920)
- [10277] Martin Friedrich Cannabich (?–1773)
- [10319] Christoph Bach (1613–1661)
- [10342] Gottlieb Friedrich Bach (1714–1785)
- [10346] Johann Gottfried Bernhard Bach (1715–1739)
- [10351] Anton Colander (?–)
- [10363] Carl Gotthelf Gerlach (1704–1761)
- [10364] Ernest Louis, Landgrave of Hesse-Darmstadt (1667–1739)
- [10382] Otto Dorn (1848–1931)
- [10383] Verena Wagner Lafferentz (1920–2019)
- [10396] Georg Liebling (1865–1946)
- [10427] Johann Georg Bach (1751–1797)
- [10435] Curt Sachs (1881–1959)
- [10450] Wieland Wagner (1917–1966)
- [10452] Walter Gieseking (1895–1956)
- [10481] Max Spicker (1858–1912)
- [10483] Johann Aegidius Bach (1645–1716)
- [10487] Holger Czukay (1938–2017)
- [10490] Jakob Adlung (1699–1762)
- [10491] Carl Friedberg (1872–1955)
- [10495] Gottfried Heinrich Bach (1724–1763)
- [10499] Jacob Praetorius the Elder (?–)
- [10515] Julius Klengel (1859–1933)
- [10516] Hans Georg Hinderberger (1970–)
- [10523] Walter Morse Rummel (1887–1953)
- [10529] Oskar Sala (1910–2002)
- [10533] Friedrich Benda (1745–1814)
- [10560] Klaus Pringsheim (1883–1972)
- [10561] Julius Hey (1832–1909)
- [10567] Johann Gottlob Töpfer (1791–1870)

## Sweden (26)
- [9990] Amanda Röntgen-Maier (1853–1894)
- [10047] Ika Peyron (1845–1922)
- [10064] Ingemar Liljefors (1906–1981)
- [10165] Hans Jacob Tengwall (1787–1863)
- [10360] Sara Wennerberg-Reuter (1875–1959)
- [10379] Princess Eugénie of Sweden (1830–1889)
- [10402] Tor Ahlberg (1913–2008)
- [10403] Johan Alfred Ahlström (1833–1910)
- [10405] B. Tommy Andersson (1964–)
- [10410] Hjalmar Berwald (1848–1930)
- [10417] Knut Bäck (1868–1953)
- [10420] Csaba Deák (1932–2018)
- [10422] Erik Drake (1788–1870)
- [10430] Åke Erikson (1937–2012)
- [10431] Nils Eriksson (1902–1978)
- [10434] Mauro Godoy-Villalobos (1967–)
- [10436] Carl Ludvig Hall (1814–)
- [10437] Wilhelm Heintze (1849–1895)
- [10438] John Jacobsson (1835–1909)
- [10448] Conrad Nordqvist (1840–1920)
- [10449] Edmund Passy (1789–1870)
- [10456] Per Ulrik Stenhammar (1829–1875)
- [10458] Gunno Södersten (1920–1998)
- [10459] Henry Weman (1897–1992)
- [10460] Ingvar Wieslander (1917–1963)
- [10526] Bengt-Arne Wallin (1926–2015)

## Russian Empire (25)
All RESOLVED except 10365 (deleted, see note below). Method: P19 (birthplace) + P27 (all
citizenships) cross-checked against each composer's own Wikipedia article opening sentence
(wikitext/native-language edition preferred when no English one exists); WP prose wins when it
disagrees with a birthplace-only inference (see Fritz Zweig precedent above). Sources saved to
data/wikipedia_pages/.

CAUTION found via Tedesco (below): a single citizenship-country's own-language Wikipedia can
carry real bias when it's describing where someone spent their *career*, not where they're
*from* -- Tedesco's ru.wikipedia called him "российский" (Russian) despite being born/raised in
Prague under Austrian rule, only moving to the Russian Empire as an adult; the independent
Jewish Encyclopedia calls him Austrian instead, which is what's now applied. Re-checked the other
"Russian" calls with the same risk shape (born outside Russia proper): Nikolayev (born Kyiv) --
confirmed via an independent second source (prabook), holds up fine. Ossovsky (born Chișinău),
Yavorsky (born Kharkiv, Polish surname), Gerchik (born Dnipro, only inferred from P27, never had
an explicit WP nationality statement) -- no independent corroboration found either way; kept as
Russian per the user's call, but confidence is lower than the others in this list.
- [10005] Arkadyev Ivan Petrovich (1882–1946) -- Russian (uk.wiki "російський радянський", Q106939275.uk.html)
- [10007] Glukhovtsev Oleksiy Stepanovich (1875–) -- Ukrainian (uk.wiki "український і російський", leads Ukrainian, Q107565256.uk.html)
- [10018] Коган Олександр Лазарович (1895–1980) -- Ukrainian (uk.wiki "українськи...", Q110617067.uk.html)
- [10019] Драненко Григорій Опанасович (1886–1944) -- Ukrainian (uk.wiki "український композитор", Q111270000.uk.html)
- [10021] Gribovitj-Bresjinskij Stepan Grigorovitj (?–) -- Ukrainian (uk.wiki "український співак, композитор", Q112028276.uk.html)
- [10022] Лебединец, Антон Дмитриевич (1894–1979) -- Ukrainian (ru.wiki "украинский советский композитор", Q112312209.ru.html)
- [10027] Pyotr Danilchenko (1857–) -- Ukrainian (uk.wiki "український віолончеліст", Q113484550.uk.html)
- [10052] Hryhoriĭ Mytrofanovych Davydovsʹkyĭ (1866–1952) -- Ukrainian (P27 includes Ukrainian
  People's Republic + Ukrainian SSR directly, born Melnia/Ukraine)
- [10073] Georg Schnéevoigt (1872–1947) -- Finnish (en.wiki "was a Finnish conductor", born
  Vyborg "Grand Duchy of Finland, now in Russia", Q133832.en.html)
- [10125] Stepan Demuryan (1871–1934) -- Armenian (hy.wiki "հայ երաժշտագետ...", Q16400117.hy.html)
- [10174] Leonid Nikolayev (1878–1942) -- Russian (en.wiki "was a Russian and Soviet pianist",
  despite Kyiv birthplace -- P27 has no Ukraine claim, Q2023778.en.html)
- [10177] Feodor Koenemann (1873–1937) -- Russian (en.wiki "was a Russian pianist", Q2035291.en.html)
- [10198] Serge Conus (1902–1988) -- Russian (en.wiki "was a Russian pianist", Q2272649.en.html)
- [10210] Boleslav Yavorsky (1877–1942) -- Russian (en.wiki "was a Soviet and Russian
  musicologist", despite Polish-sounding surname and Kharkiv birthplace, Q2471676.en.html)
- [10227] Aleksander Różycki (1855–1914) -- Polish (pl.wiki "polski kompozytor", Q26244368.pl.html)
- [10228] Antoni Kątski (1817–1889) -- Polish (P27 includes modern Poland directly)
- [10234] Semyon Viktorovich Panchenko (?–1937) -- Russian (ru.wiki "российский композитор", Q27732062.ru.html)
- [10322] Konstantin Lyadov (1820–1871) -- Russian (ru.wiki "русский дирижёр", father of
  Anatoly Lyadov, Q4272524.ru.html)
- [10328] Alexander Ossovsky (1871–1957) -- Russian (en.wiki "was a Russian and Soviet
  musicologist", Q4338440.en.html)
- [10336] Ignaz Amadeus Tedesco (1815–1882) -- RESOLVED Austrian, corrected from an initial
  Russian call. ru.wiki said "российский пианист... родом из чешских евреев" (Russian, of
  Czech-Jewish origin) -- but the independent Jewish Encyclopedia calls him "an Austrian
  pianist" instead, matching his actual origin (born/raised Prague under Austrian rule, only
  moved to the Russian Empire as an adult for his career, Q4453717.ru.html). See the CAUTION
  note above this section.
- [10365] Celina Szymanowska (1812–1855) -- DELETED. Both en.wikipedia and pl.wikipedia (her
  native language, checked directly) describe her purely as "wife of Adam Mickiewicz, mother of
  his six children" and daughter of pianist Maria Szymanowska -- no musical career of her own
  mentioned in either, despite fairly detailed biographical coverage in both. Wikidata's lone
  P106 "composer" tag looks like a data-quality artifact with nothing behind it. Same pattern as
  the Popper/Reményi Béla deletions.
- [10391] Kazimierz Wiłkomirski (1900–1995) -- Polish (P27 includes modern Poland directly)
- [10424] Vera Petrovna Gerchik (1911–) -- Russian (ru.wiki just "советский композитор", no
  Ukrainian identity stated despite Dnipro birthplace; P27 has no Ukraine claim either, Q56310080.ru.html)
- [10470] Lev Oborin (1907–1974) -- Russian (famous pianist, born Moscow, P27 Russia direct)
- [10476] Ludwika Jędrzejewicz Chopin (1807–1855) -- Polish (Chopin's sister; P27 includes
  modern Poland directly, born Warsaw)

## Soviet Union (25)
All overlap with Russian Empire above except the ones below (RESOLVED, same method/sources).
- [10010] Sergey Pavlovich Dobrovolsky (1910–1942) -- Ukrainian (uk.wiki "украї...", Q108453669.uk.html)
- [10024] Michail Aleksejevič Aleksejev (1933–1996) -- Russian. No Wikipedia article exists in
  any language (checked Wikidata sitelinks directly) -- P27 includes modern Russia (Q159) directly.
- [10055] Leopol‘d Ìvanovyč Jaščenko (1928–2016) -- Ukrainian (P27 includes modern Ukraine
  directly, born Kyiv)
- [10069] Camil Amirov (1957–) -- Azerbaijani (P27 includes modern Azerbaijan directly, born Baku)
- [10102] Mstislav Rostropovich (1927–2007) -- Russian (famous, P27 Russia direct)
- [10124] Yalchin Adigezalov (1959–) -- Azerbaijani (P27 includes modern Azerbaijan directly, born Baku)
- [10201] Fyodor Vasilyev (1920–2000) -- Chuvash (ru.wiki "чувашский советский композитор" --
  added as a new nationalities row, same granular-ethnicity precedent as the existing "Catalan"
  tag, Q23655419.ru.html)
- [10204] Tofig Guliyev (1917–2000) -- Azerbaijani (P27 has three separate Azerbaijan-related claims)
- [10229] Jansug Kakhidze (1936–2002) -- Georgian (P27 includes modern Georgia directly, born Tbilisi)
- [10335] Oleksandr Stetsiuk (1941–2007) -- Ukrainian (ru.wiki "украинский композитор", Q4442530.ru.html)
- [10439] Konstantin Igumnov (1873–1948) -- Russian (famous pianist, born Lebedyan/Russia proper)
- [10565] Alfrēds Kalniņš (1879–1951) -- Latvian (P27 includes modern Latvia directly, born Cēsis)
- [10566] Peeter Volkonski (1954–) -- Estonian (P27 includes modern Estonia directly, born Tallinn)

## United Kingdom (19)
(and the other UK-related sections below: United Kingdom of Great Britain and Ireland, Kingdom
of Great Britain, Kingdom of England, British Raj) -- deliberately left unassigned, not just
unreached yet. Unlike Czechoslovakia/Yugoslavia, P19 birthplace doesn't reliably disambiguate
English/Scottish/Welsh/Northern Irish identity (someone born in London can still identify as
Scottish, etc.), so there's no safe two-signal check here -- leave for manual judgment per
composer rather than guessing "English" by default.
- [9991] Emma-Jean Thackray (?–)
- [10109] Adelina de Lara (1872–1961)
- [10114] Harold Craxton (1885–1971)
- [10118] John Eliot Gardiner (1943–)
- [10162] Nikki Iles (1963–)
- [10166] Norman Del Mar (1919–1994)
- [10224] Anoushka Shankar (1981–)
- [10252] Lindsay Cooper (1951–2013)
- [10261] Harold Samuel (1879–1937)
- [10265] Donovan (1946–)
- [10270] Julian Lloyd Webber (1951–)
- [10300] Billy Mayerl (1902–1959)
- [10344] Noor Inayat Khan (1914–1944)
- [10347] Alissa Firsova (1986–)
- [10354] Arthur Elwell Fisher (?–)
- [10359] James McCartney (1977–)
- [10399] George Linstead (1908–1974)
- [10480] Marmaduke Barton (1865–1938)
- [10506] Robert Sherlaw Johnson (1932–2000)

## Kingdom of Italy (15)
- [9996] Camille-Marie Stamaty (1811–1870)
- [10031] Fernando Germani (1906–1998)
- [10041] Alessandro Busi (1833–1895)
- [10046] Mario Labroca (1896–1973)
- [10121] Beniamino Cesi (1845–1907)
- [10134] Paolo Serrao (1830–1907)
- [10217] Vito Frazzi (1888–1975)
- [10232] Luigi Mancinelli (1848–1921)
- [10258] Josef Neruda (1807–1875)
- [10295] Angelo Mascheroni (?–)
- [10297] Basilio Basili (1804–)
- [10303] Luigi Torchi (1858–1920)
- [10318] Anna Weiss-Busoni (?–)
- [10334] Cesare Sodero (1886–1947)
- [10522] Virginia Mariani Campolieti (1869–)

## Hungary (13)
- [10003] Károly Huber (1828–1885)
- [10026] Miklós Rékai (1906–1959)
- [10076] György Sándor (1912–2005)
- [10110] Emil Telmányi (1892–1988)
- [10152] Kálmán Oláh (1970–)
- [10195] Rudolf Bella (1890–1973)
- [10213] György Kurtág Jr. (1954–)
- [10253] Regina Berkovits (1887–)
- [10339] Victor von Herzfeld (1856–1919)
- [10389] Francis Korbay (1846–1913)
- [10420] Csaba Deák (1932–2018)
- [10473] Géza Wehner (1888–1947)
- [10569] Gábor Esterházy (1673–1704)

## Canada (13)
- [10038] David Mott (1945–)
- [10065] Pierre Mercure (1927–1966)
- [10135] Isabelle Delorme (1900–1991)
- [10173] Omer Létourneau (1891–1983)
- [10244] Antoine Bouchard (1932–2015)
- [10260] Gustave Gagnon (1842–1930)
- [10358] Boyd McDonald (1932–)
- [10373] Conrad Bernier (1904–1988)
- [10408] Elzéar Fortier (1915–1987)
- [10423] Léon Dessane (1863–1930)
- [10446] Humfrey Anger (1862–1913)
- [10484] Michel Perrault (1925–2010)
- [10517] Henri Gagnon (1887–1961)

## Austria (13)
- [10103] Theodor W. Adorno (1903–1969)
- [10141] Alexander Wunderer (1877–1955)
- [10274] Rudolf Dittrich (1861–1919)
- [10304] Micah Barnes (1960–)
- [10340] Heinrich Jalowetz (1882–1946)
- [10398] George Korngold (1928–1987)
- [10409] Rudolf Cahn-Speyer (1881–1940)
- [10415] Sepp Rosegger (1874–1948)
- [10418] Karl Pohlig (1864–1928)
- [10445] Hugo Kauder (1888–1972)
- [10518] Erich Kleiber (1890–1956)
- [10519] Erich Leinsdorf (1912–1993)
- [10531] Manon Gropius (1916–1935)

## United Kingdom of Great Britain and Ireland (13)
- [10109] Adelina de Lara (1872–1961)
- [10114] Harold Craxton (1885–1971)
- [10122] William Smyth Rockstro (1823–1895)
- [10261] Harold Samuel (1879–1937)
- [10300] Billy Mayerl (1902–1959)
- [10367] Charles Edward Horsley (1822–1876)
- [10380] Bettina Walker (?–1893)
- [10399] George Linstead (1908–1974)
- [10407] Joseph Barnby (1838–1896)
- [10471] Charles Hallé (1819–1895)
- [10480] Marmaduke Barton (1865–1938)
- [10482] Edward Dannreuther (1844–1905)
- [10498] Percy Hilder Miles (1878–1922)

## Belgium (11)
- [10009] André Collin (1898–1975)
- [10042] Hubert Léonard (1819–1890)
- [10063] Emiel Verrees (1857–1929)
- [10082] Martin Pierre Marsick (1847–1924)
- [10083] Eugène Guillaume (compositeur) (1882–1953)
- [10158] Mathieu Crickboom (1871–1947)
- [10180] Jean Louël (1914–2005)
- [10219] Félix Pardon (?–)
- [10268] Joseph Dupont (1838–1899)
- [10453] Jacques Gregoir (1817–1876)
- [10496] Jacques-Nicolas Lemmens (1823–1881)

## Poland (11)
- [10036] Amelia Załuska (1805–1858)
- [10059] Mieczysław Ziółkowski (?–)
- [10184] Moriz Rosenthal (1862–1946)
- [10188] Joseph Rosenstock (1895–1985)
- [10209] Henryk Sztompka (1901–1964)
- [10228] Antoni Kątski (1817–1889)
- [10391] Kazimierz Wiłkomirski (1900–1995)
- [10476] Ludwika Jędrzejewicz Chopin (1807–1855)
- [10545] Seweryn Barbag (1891–1944)
- [10559] Tadeusz Szeligowski (1896–1963)
- [10564] Grzegorz Fitelberg (1879–1953)

## Norway (11)
- [10048] Dagne Groven Myhren (1940–2024)
- [10111] Gustav Lange (1861–1939)
- [10149] Ketil Hvoslef (1939–)
- [10150] Fridtjof Backer-Grøndahl (1885–1959)
- [10255] Edmund Neupert (1842–1888)
- [10289] Trygve Madsen (1940–)
- [10309] Per Winge (1858–1935)
- [10341] Robert Levin (1912–1996)
- [10343] Conrad Baden (1908–1989)
- [10386] Finn Mortensen (1922–1983)
- [10477] Elise Wiel (1866–1926)

## Kingdom of Denmark (8)
- [10161] Johann Christian Gebauer (1808–1884)
- [10199] Henrik Lund (1875–1948)
- [10316] Julius Ernst Christian Johannsen (1826–1904)
- [10370] Christian Henrik Glass (1821–1893)
- [10479] Margaret Hamerik (1867–1942)
- [10497] Paul Hellmuth (1879–)
- [10507] Roger Henrichsen (1876–1926)
- [10528] Benjamin Koppel (1974–)

## Italy (7)
- [10002] Giampaolo Bracali (1941–2006)
- [10031] Fernando Germani (1906–1998)
- [10039] Alberta d'Angeli Cattini (1894–)
- [10046] Mario Labroca (1896–1973)
- [10217] Vito Frazzi (1888–1975)
- [10334] Cesare Sodero (1886–1947)
- [10555] Alessio Vlad (?–)

## Finland (7)
- [10020] Tarmo Peltokoski (2000–)
- [10073] Georg Schnéevoigt (1872–1947)
- [10144] Juho Ranta (?–)
- [10256] Leo Funtek (1885–1965)
- [10385] Pekka Savijoki (1952–)
- [10419] Fabian Dahlström (1930–)
- [10544] Jukka-Pekka Saraste (1956–)

## Austrian Empire (7)
- [10178] Philipp Schmutzer (1821–1898) -- RESOLVED Austrian (cs.wikipedia itself says "rakouský"
  despite his Bohemian birthplace, data/wikipedia_pages/Q2087022.cs.html)
- [10237] Franz Joseph Zierer (1822–1903) -- RESOLVED Austrian (born Vienna suburb + de.wikipedia
  "österreichischer", data/wikipedia_pages/Q27987632.de.html)
- [10267] Joseph von Blumenthal (1782–1850) -- RESOLVED Austrian (en.wikipedia "was an Austrian
  violinist", despite Brussels birthplace, data/wikipedia_pages/Q3182017.en.html)
- [10279] Alfred Jaëll (1832–1882) -- RESOLVED Austrian (en.wikipedia "was an Austrian pianist",
  despite Trieste birthplace, data/wikipedia_pages/Q330244.en.html)
- [10442] Friedrich von Hausegger (1837–1899) -- RESOLVED Austrian (de.wikipedia
  "österreichischer Musikwissenschaftler", data/wikipedia_pages/Q5871924.de.html)
- [10546] Archduke Rudolf of Austria (1788–1831) -- RESOLVED Austrian (Habsburg; en.wikipedia
  "an Austrian clergyman and noble", data/wikipedia_pages/Q93373.en.html)
- [10558] Josef Proksch (1794–1864) -- RESOLVED German (en.wikipedia "Bohemian-German pianist",
  data/wikipedia_pages/Q959789.en.html -- same German-speaking-Bohemian category as Fritz Zweig above)

## Kingdom of Prussia (7)
- [10467] Julius Rietz (1812–1877)
- [10471] Charles Hallé (1819–1895)
- [10485] August Wilhelmj (1845–1908)
- [10493] Theodor Kullak (1818–1882)
- [10500] Wilhelm Friedrich Wieprecht (1802–1872)
- [10530] Wilhelm Joseph von Wasielewski (1822–1896)
- [10534] Daniel Hünten (?–1823)

## Russia (6)
- [10024] Michail Aleksejevič Aleksejev (1933–1996)
- [10102] Mstislav Rostropovich (1927–2007)
- [10201] Fyodor Vasilyev (1920–2000)
- [10251] Boris Golovin (1955–)
- [10424] Vera Petrovna Gerchik (1911–)
- [10454] Victor Smolski (1969–)

## Japan (6)
- [10032] Kyōko Kiya (1971–)
- [10035] Toshi Isobe (1917–1998)
- [10208] Masakazu Natsuda (1968–)
- [10257] Satoru Ōnuma (1889–1944)
- [10292] Takanobu Saitō (1924–2004)
- [10387] Isao Tomita (1932–2016)

## Switzerland (6)
- [10057] Edwin Fischer (1886–1960)
- [10071] Emil Frey (1889–1946)
- [10103] Theodor W. Adorno (1903–1969)
- [10207] Pierre Segond (1913–2000)
- [10236] Fernande Peyrot (1888–1978)
- [10325] William Montillet (1879–1940)

## Austria–Hungary (6)
- [10058] Leó Popper (1886–1911) -- DELETED. Wikidata does list "composer" among his P106
  occupations, but real career/reputation (per Wikidata's own short description and
  hu.wikipedia's prose, data/wikipedia_pages/Q1239198.hu.html) is art historian/painter/critic --
  died at 25, son of cellist-composer David Popper (2323), pulled in only via the relation-
  discovery pipeline's child-relationship following. Same pattern as the Reményi Béla deletion
  earlier this session.
- [10190] Fritz Zweig (1893–1984) -- RESOLVED German, see Czechoslovakia above
- [10237] Franz Joseph Zierer (1822–1903) -- RESOLVED Austrian, see Austrian Empire above
- [10377] Josef Hellmesberger (1855–1907) -- RESOLVED Austrian (en.wikipedia "was an Austrian
  composer", data/wikipedia_pages/Q524466.en.html)
- [10472] František Kohout (1858–1929) -- RESOLVED Czech (cs.wikipedia "byl český hudební
  skladatel", data/wikipedia_pages/Q65720241.cs.html)
- [10489] Yevsevii Mandychesvky (1857–1929) -- RESOLVED Romanian (en.wikipedia's own opening
  sentence: "was a Romanian musicologist, composer, conductor, and teacher", despite a genuinely
  mixed Ukrainian-Bukovina/Austrian background, data/wikipedia_pages/Q701340.en.html)

## Greece (6)
- [10070] Minas Alexiadis (1960–)
- [10146] Danae Kara (1953–)
- [10352] Apostolos Paraskevas (1964–)
- [10353] Aristotelis Koundouroff (1896–1969)
- [10397] Giorgos Hadjinikos (1923–2015)
- [10503] Dionysis Savvopoulos (1944–2025)

## Kingdom of Saxony (6)
- [10163] Louis Plaidy (1810–1874)
- [10185] Carl Gottlieb Reissiger (1798–1859)
- [10189] August Ferdinand Anacker (1790–1854)
- [10333] Friedrich Wieck (1785–1873)
- [10467] Julius Rietz (1812–1877)
- [10469] Ernst Richter (1808–1879)

## Australia (5)
- [10117] Gordon Watson (1921–1999)
- [10206] Cyril Monk (1882–1970)
- [10337] Richard Toop (?–)
- [10361] Sarah McKenzie (?–)
- [10376] David Tunley (1930–2024)

## Mexico (5)
- [10127] María Grever (1885–1951)
- [10281] Ricardo Castro (1864–1907)
- [10290] Julio Estrada (1943–)
- [10428] Adolfo Salazar (1890–1958)
- [10554] Eduardo Mata (1942–1995)

## Republic of Venice (4)
- [10043] Giovanni Antonio Riccieri (1679–1746)
- [10106] Giovanni Battista Vivaldi (?–1736)
- [10345] Gaspara Stampa (?–1554)
- [10375] Angelo Gardano (?–1611)

## German Reich (4)
- [10074] Engelbert Röntgen (1829–1897)
- [10415] Sepp Rosegger (1874–1948)
- [10530] Wilhelm Joseph von Wasielewski (1822–1896)
- [10537] Wilhelm Middelschulte (1863–1943)

## Argentina (4)
- [10090] Felipe Boero (1884–1958)
- [10404] Daniel Piazzolla (1945–2025)
- [10421] Gustavo Moretto (1950–)
- [10518] Erich Kleiber (1890–1956)

## Brazil (4)
- [10128] Bianca Gismonti (?–)
- [10153] Alexandre Gismonti (1981–)
- [10330] Guiomar Novaes (1895–1979)
- [10384] Dinorá de Carvalho (1905–1980)

## Romania (4)
- [10130] Sergiu Celibidache (1912–1996)
- [10262] Florian Lungu (1943–)
- [10406] Cristian Măcelaru (1980–)
- [10489] Yevsevii Mandychesvky (1857–1929)

## Czechoslovakia (4)
- [10190] Fritz Zweig (1893–1984) -- RESOLVED German. P19 birthplace Olomouc (Moravia) would
  suggest Czech, but en.wikipedia's own opening sentence explicitly calls him a "German conductor"
  (data/wikipedia_pages/Q214915.en.html, likely a German-speaking Moravian, a real and common
  category pre-WWII) -- explicit WP prose wins over the coarser birthplace inference when they
  disagree.
- [10215] Antonín Bennewitz (1833–1926) -- RESOLVED Czech (P19 birthplace Přívrat + en.wikipedia
  "was a Czech violinist", data/wikipedia_pages/Q252556.en.html agree)
- [10502] Otakar Ševčík (1852–1934) -- RESOLVED Czech (also in Kingdom of Bohemia below; P19
  birthplace Horažďovice + en.wikipedia "was a Czech violinist", data/wikipedia_pages/Q726973.en.html)
- [10540] Otakar Dvořák (1885–1961) -- RESOLVED Czech (P19 birthplace Prague + cs.wikipedia "byl
  český bankovní úředník", data/wikipedia_pages/Q90274150.cs.html)

## German Empire (3)
- [10014] Paul Homeyer (1853–1908)
- [10103] Theodor W. Adorno (1903–1969)
- [10132] Walther Lampe (1872–1964)

## Republic of Lucca (3)
- [10017] Valerio Guami (?–1649)
- [10050] Domenico Guami (?–1631)
- [10051] Vincenzo Guami (?–)

## Empire of Japan (3)
- [10035] Toshi Isobe (1917–1998)
- [10292] Takanobu Saitō (1924–2004)
- [10387] Isao Tomita (1932–2016)

## Azerbaijan (3)
- [10069] Camil Amirov (1957–)
- [10124] Yalchin Adigezalov (1959–)
- [10204] Tofig Guliyev (1917–2000)

## Kingdom of Bavaria (3)
- [10115] Heinrich Domnich (1767–1844)
- [10349] Anna Caroline Oury (1808–1880)
- [10475] Sophie Menter (1846–1918)

## Grand Duchy of Baden (3)
- [10151] Franziska Pixis (1816–1904)
- [10494] Fritz Steinbach (1855–1916)
- [10536] Alexander Fesca (1820–1849)

## Kingdom of the Netherlands (3)
- [10193] Jaap Spaanderman (1896–1985)
- [10233] Johannes Eduardus Gerardus van Boom (?–1878)
- [10355] Samuel de Lange (1840–1911)

## Venezuela (3)
- [10214] Vicente Emilio Sojo (1887–1974)
- [10288] Juan Bautista Plaza (1898–1965)
- [10294] Alejandro Planchart (1935–2019)

## Cisleithania (3)
- [10409] Rudolf Cahn-Speyer (1881–1940) -- RESOLVED Austrian. No Wikipedia article exists in any
  language (checked Wikidata sitelinks directly) -- born Vienna, and P27 includes a direct claim
  to modern Austria (Q40), not just the historical Cisleithania/Austria-Hungary entities, so this
  is trustworthy even without a WP cross-check.
- [10415] Sepp Rosegger (1874–1948) -- RESOLVED Austrian. Same situation as Cahn-Speyer: no
  Wikipedia article at all, born Graz, P27 includes direct modern Austria (Q40).
- [10442] Friedrich von Hausegger (1837–1899) -- RESOLVED Austrian, see Austrian Empire above

## Portugal (2)
- [9997] Helena Sá e Costa (1913–2006)
- [9998] João de Freitas Branco (1922–1989)

## Ukraine (2)
- [10034] Ihor Tylyk (1968–)
- [10055] Leopol‘d Ìvanovyč Jaščenko (1928–2016)

## Bulgaria (2)
- [10056] Aleksandŭr Vladigerov (1933–1993)
- [10081] Marin Goleminov (1908–2000)

## Nazi Germany (2)
- [10132] Walther Lampe (1872–1964)
- [10487] Holger Czukay (1938–2017)

## West Germany (2)
- [10132] Walther Lampe (1872–1964)
- [10487] Holger Czukay (1938–2017)

## Slovenia (2)
- [10145] Blaženka Arnič-Lemež (1947–) -- RESOLVED Slovenian (also in Socialist Federal Republic
  of Yugoslavia below; P19 birthplace Ljubljana + sl.wikipedia "slovenska skladateljica",
  data/wikipedia_pages/Q17402271.sl.html)
- [10401] Leon Firšt (1994–) -- RESOLVED Slovenian (P19 birthplace Celje + sl.wikipedia
  "slovenski skladatelj", data/wikipedia_pages/Q55432435.sl.html)

## Hamburg (2)
- [10368] Eduard Marxsen (1806–1887)
- [10539] Henry Schradieck (1846–1918)

## Congress Poland (2)
- [10400] Jan Nepomucen Bobrowicz (1805–1881)
- [10466] Carl Tausig (1841–1871)

## German Democratic Republic (2)
- [10433] Hermann Abendroth (1883–1956)
- [10538] Erhard Mauersberger (1903–1982)

## Kingdom of Great Britain (2)
- [10461] John Valentine (?–1791)
- [10504] Richard Brind (?–1718)

## Cuba (1)
- [10000] Carlos Fariñas (1934–)

## Papal States (1)
- [10011] Cesare Zoilo (?–1626)

## Principality of Transylvania (1)
- [10013] Joseph Filtsch (1782–1860)

## County of Flanders (1)
- [10040] Alard du Gaucquier (?–)

## Ukrainian People's Republic (1)
- [10052] Hryhoriĭ Mytrofanovych Davydovsʹkyĭ (1866–1952)

## Ukrainian Soviet Socialist Republic (1)
- [10052] Hryhoriĭ Mytrofanovych Davydovsʹkyĭ (1866–1952)

## Venice (1)
- [10060] Francesco Bellazzi (?–)

## Lebanon (1)
- [10075] Marcel Khalife (1950–)

## New Spain (1)
- [10087] Miguel Pontaza (?–1807)

## Guatemala (1)
- [10087] Miguel Pontaza (?–1807)

## Colombia (1)
- [10095] Francisco Zumaque (1945–)

## Luxembourg (1)
- [10126] Max Menager (1874–1963)

## Socialist Federal Republic of Yugoslavia (1)
- [10145] Blaženka Arnič-Lemež (1947–) -- RESOLVED Slovenian, see Slovenia above

## Russian Soviet Federative Socialist Republic (1)
- [10174] Leonid Nikolayev (1878–1942)

## Chile (1)
- [10181] Sergio Ortega (1938–2003)

## Azerbaijan Democratic Republic (1)
- [10204] Tofig Guliyev (1917–2000)

## South Africa (1)
- [10205] Chris McGregor (1936–1990)

## Crown of Castile (1)
- [10212] Pedro Fernández de Castilleja (?–)

## Dutch Republic (1)
- [10216] Dirk Janszoon Sweelinck (?–1652)

## Kingdom of Portugal (1)
- [10222] Teodósio, Prince of Brazil (1634–1653)

## Georgia (1)
- [10229] Jansug Kakhidze (1936–2002)

## Crown of Aragon (1)
- [10240] Bernardino de Ribera (?–)

## Kingdom of France (1)
- [10264] Laurent Desmazures (1714–1778)

## Kingdom of Naples (1)
- [10308] Saverio Valente (?–)

## Electorate of Saxony (1)
- [10333] Friedrich Wieck (1785–1873)

## Duchy of Brunswick (1)
- [10338] Wilhelm Fitzenhagen (1848–1890)

## British Raj (1)
- [10344] Noor Inayat Khan (1914–1944)

## Kingdom of Württemberg (1)
- [10366] Ludwig Abeille (1761–1838)

## Ireland (1)
- [10380] Bettina Walker (?–1893)

## Byelorussian Soviet Socialist Republic (1)
- [10454] Victor Smolski (1969–)

## Belarus (1)
- [10454] Victor Smolski (1969–)

## Free City of Danzig (1)
- [10487] Holger Czukay (1938–2017)

## Kingdom of Bohemia (1)
- [10502] Otakar Ševčík (1852–1934) -- RESOLVED Czech, see Czechoslovakia above

## Kingdom of England (1)
- [10513] Sebastian Westcott (?–)

## Second Polish Republic (1)
- [10541] Gustaw Roguski (1839–1921)

## Latvia (1)
- [10565] Alfrēds Kalniņš (1879–1951)

## Estonia (1)
- [10566] Peeter Volkonski (1954–)

## No citizenship on Wikidata at all (86)
- [9992] Martha von Flotow (?–)
- [9993] Mary Paramore Comber (?–)
- [10001] Karoly Noszeda (?–)
- [10008] Fabrizio II Gesualdo (?–)
- [10012] Дяченко Григорій Онуфрійович (1896–)
- [10023] Christopher Lyndon-Gee (?–)
- [10025] Dürdana Amirova (?–)
- [10049] Glushkov Petro Tarasovich (1889–1966)
- [10053] shtvan Ferentsovich Marton (1923–1996)
- [10067] Ali Brezovský (1940–)
- [10089] Conrad Berens (?–)
- [10093] Florian Zajíc (1853–1926)
- [10094] Francesco Maria Cattaneo (?–1758)
- [10096] Franz Xaver Gruber (1826–1871)
- [10104] Giovanni Battista Mancini (1714–1800)
- [10105] Giovanni Battista Tibaldi (?–)
- [10108] Georg Jacob Vollweiler (1770–1847)
- [10112] Hans Georg Benda (1686–1757)
- [10113] Francesco Barbella (?–)
- [10119] Pablo M Berutti (1870–)
- [10133] Ilya Semyonovich Aisberg (1868–1942)
- [10138] Johann Aloys Miksch (1765–1845)
- [10147] Giovanni Domenico Rognoni Taeggio (?–)
- [10154] Alessandro Toeschi (?–1758)
- [10156] James Robert Sterndale-Bennett (?–)
- [10157] Philip James Meyer (?–)
- [10159] Wilhelm Hanser (1738–1796)
- [10160] Royden Barrie (?–)
- [10167] Heinrich van Eyken (1861–1908)
- [10170] Ottavio Catalani (?–)
- [10175] Joseph Franz Wolf (1802–1842)
- [10179] Domenico Tritto (1776–)
- [10186] José Ma. Alcácer (?–)
- [10191] Floriano Maria Arresti (1667–)
- [10196] Matous Habermann (?–)
- [10218] Ludovit Rajter starsi (1880–1945)
- [10220] Giuseppe Pilotti‏ (1785–1838)
- [10221] François de Godzinsky (1878–)
- [10226] Johann Kusser st. (?–)
- [10235] Emil Kühnel (1881–1971)
- [10238] Charles Louis Maucourt (?–)
- [10242] Аллаһияр Вәлиуллин (1924–)
- [10245] Antonio Puccini (?–1832)
- [10246] Lourenço Ribeiro (?–)
- [10263] Heinrich Praeger (1783–1854)
- [10273] Gaetano Carpani (?–1785)
- [10291] Petr Petrovich Evstafʹev (1861–1900)
- [10298] Benedetto Neri (1771–1841)
- [10299] Karel Stecker (1861–1918)
- [10302] Franz Seraph Cramer (1783–1835)
- [10307] Santino Garsi da Parma (1542–1604)
- [10311] Johann Christoph Walther (1715–1771)
- [10312] Johann Konrad Schlick (?–)
- [10313] Michele Giuliani (1801–1867)
- [10315] Matthias Durst (1815–1875)
- [10332] Félix Rault (?–)
- [10388] Mathias Haydn (1699–1763)
- [10390] Eduard Zaritsky (1946–2018)
- [10393] Esaias Reusner der Ältere (?–)
- [10394] Sophonias Päminger (?–)
- [10395] Girolamo Crescentini (1762–1846)
- [10413] Edmond Diet (1854–1924)
- [10414] Arthur Kalkbrenner (?–)
- [10416] Sigismund Päminger (?–)
- [10425] Emili Valdés Perlasia (?–)
- [10426] Julià Vilaseca (?–1929)
- [10432] Heinrich Romberg (1802–1859)
- [10443] Domenico da Piacenza (?–)
- [10444] Moritz Schön (?–1885)
- [10451] Luigi Piccinni (?–1827)
- [10457] Agostino Bendinelli (1635–)
- [10465] Vincent Lübeck (1684–)
- [10474] Telesforo Righi (1842–1930)
- [10486] Georg Hellmesberger (1830–1852)
- [10514] Otto Reinsdorf (1848–1890)
- [10524] Wilhelm Kuhe (1823–1912)
- [10532] Giulietta Guicciardi (1782–1856)
- [10535] Giovanni Andrea Bontempi (?–1705)
- [10542] Giacomo Insanguine (1728–1795)
- [10543] Vincenzo Manfredini (1737–1799)
- [10547] Alessandro Gardane (?–)
- [10549] Albert Noelte (?–)
- [10550] Theodor Blumer (1854–1932)
- [10551] Wilhelm Müller (?–)
- [10552] Maxmilian Koblížek (1866–1947)
- [10553] Jaroslav Ušák (1891–1965)
