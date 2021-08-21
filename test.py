import pytest

from fetch_wikipedia import (
    get_table_eras, era_config, romantic_pattern, regex, list_pattern,
    list_pattern_irregular_dates, list_pattern_interwiki_irregular,
    list_pattern_interwiki, get_date_info, birth_death_flourish_from_lifetime)
from investigate_wikipedia_pages import get_redir_name

table_eras = {
    "Classical-era",
    "Romantic-era",
    "20th-century classical",
    "21st-century classical"
}


def test_table_eras():
    assert set(get_table_eras(era_config)) == table_eras


def test_romantic_pattern():
    line = "| [[Mikhail Glinka]] || 1804 || 1857 || Russian || [[File:Mikhail Glinka 1840.jpg|right|thumb|130px|Mikhail Glinka]]nationalist composer whose works include the opera, ''[[A Life for the Tsar]]''"
    match = regex.match(romantic_pattern, line, flags=regex.VERBOSE)
    assert bool(match)
    assert match.groups() == (None, 'Mikhail Glinka', '1804', '1857', 'Russian')
    assert match.group(0) == """| [[Mikhail Glinka]] || 1804 || 1857 || Russian || """


def test_romantic_pattern_parenthesis():
    line = "| [[James Hewitt (musician)|James Hewitt]] || 1770 || 1827 || American || composer, conductor and music publisher"
    match = regex.match(romantic_pattern, line, flags=regex.VERBOSE)
    assert bool(match)
    assert match.groups() == ('James Hewitt (musician)', 'James Hewitt', '1770', '1827', 'American')
    assert match.group(0) == """| [[James Hewitt (musician)|James Hewitt]] || 1770 || 1827 || American || """


lines = """* [[Pierre van Maldere]] (1729–1768)
* [[Antonio Soler]] (1729–1783)
* [[Capel Bond]] (1730–1790)<!--Very late English 'baroque': wrote sub-Handelian concerti grossi--> 
* [[Gabriele Leone]] (c. 1735-1790)
* [[Jacques Morel (composer)|Jacques Morel]] (''fl.'' c. 1700–1749)
* [[Joseph Abaco]], or ''dall'Abaco'' (1710–1805)"""

lines_irreg = """* [[Lucia Quinciani]] (born c. 1566; ''fl.'' 1611)
* [[Cesarina Ricci de Tingoli|Cesarina Ricci ''de Tingoli'']] (born c. 1573, ''fl.'' 1597)
* [[Sulpitia Cesis]] (b. 1577; ''fl.'' 1619)
* [[John Marchant (composer)|John Marchant]] (died 1611)
* [[Richard Martin (composer)|Richard Martin]] (fl. c. 1610)
* [[Girolamo Dalla Casa]] (fl. from 1568; d. 1601)
* [[William Tisdale]] (born 1570)<!--there were 2 William Tisdales. One died in 1603. And the other one died in 1605-->
* [[Henry Lichfild]] (died 1613)
* [[Thomas Greaves (musician)|Thomas Greaves]] (fl. 1604)
* [[Richard Sumarte]] (d. after 1630)
* [[Richard Nicholson (composer)|Richard Nicholson]] (died 1639)
* [[Jacques de Gouy]] (died after 1650)
* [[George Handford (composer)|George Handford]] (fl. c. 1609)
* [[Robert Tailour]] (fl. 1615)
* [[Charles Coleman (composer)|Charles Coleman]] (died 1646)
* [[Giovanni Battista Grillo]] (died 1622)
* [[Marcantonio Negri]] (died 1624)
* [[Adam of Wągrowiec|Adam z Wągrowca]] (died 1629)
* [[Mikołaj Zieleński]] (''fl.'' 1611) <!--can't verify the following dates (c. 1560–c. 1620); moved to this section since we only have one firm date of publication-->
* [[Alba Trissina]] (born 1622)
* [[Bartholomäus Aich]] (''fl.'' 1648)
* [[John Gamble (musician)|John Gamble]] (fl. from 1641, died 1687)
* [[Bernardo Gianoncelli]] (''fl.'' early 17th century; d. before 1650)
* [[Bartłomiej Pękiel]] (died c. 1670)
* [[Bernardo Sabadini]] (''fl.'' from 1662; d. 1718)
* [[Louis Saladin]] (''fl.'' c. 1670)
* [[Bernardo Storace]] (''fl.'' 1664)
* [[Giovanni Giorgi (composer)|Giovanni Giorgi]] (''fl.'' from 1719; d. 1762)
* [[Caterina Benedicta Grazianini]] (born 17th century; ''fl.'' from 1705)
* [[Le Sieur de Machy]] (d. after 1692)
* [[Mrs Philarmonica]] (''fl.'' 1715)
* [[Marieta Morosina Priuli]] (''fl.'' 1665)
* [[Alexander Maasmann]] (''fl.'' 1713)
"""

"""* [[August Verdufen]], or ''Werduwen'' (17th century) <small>([https://web.archive.org/web/20110725070521/http://jonathan.dunford.free.fr/html/manuscri.htm])</small>
"""

# Can't handle the extra parentheses yet
"""* [[Georg Reutter II|Georg Reutter]] (the younger) (1708–1772)
* [[Jean-Marie Leclair the younger|Jean-Marie Leclair]] ''le cadet'' (the younger) (1703–1777)
*[[Jean-Baptiste Niel]] (Nieil or Nielle) (1690-1775)
* [[Gregory (Gregorius) Howet (Huwet)]] (1550–1617)
* [[Massimiliano Neri (composer)]] (1621-1666)
* [[Johann Bernhard Bach (the younger)]] (1700–1743)
* [[Giacomo Puccini (senior)]] (1712-1781)
* [[Kaspar Förster]] (the younger) (1616–1673)
* [[Monsieur de Sainte-Colombe the younger|Monsieur de Sainte-Colombe]] ''le fils'' (the younger) (c. 1660–c. 1720) <small>([http://www.medieval.org/emfaq/cds/ads6042.htm])</small>
* [[Jean-Baptiste Lully fils]] (the younger) (1665–1743)
"""

# What to do with lines like that? I've done them manually
"""*Simon Simon (1735 ? - 1787 ?)"""


def test_list_pattern():
    expected = (
        ((None, 'Pierre van Maldere', '', '1729–1768', '1729', '1768', ''), '* [[Pierre van Maldere]] (1729–1768)'),
        ((None, 'Antonio Soler', '', '1729–1783', '1729', '1783', ''), '* [[Antonio Soler]] (1729–1783)'),
        ((None,
          'Capel Bond', '',
          '1730–1790',
          '1730',
          '1790',
          "<!--Very late English 'baroque': wrote sub-Handelian concerti grossi--> "),
         "* [[Capel Bond]] (1730–1790)<!--Very late English 'baroque': wrote sub-Handelian concerti grossi--> "),
        ((None, 'Gabriele Leone', '', 'c. 1735-1790', 'c. 1735', '1790', ''), '* [[Gabriele Leone]] (c. 1735-1790)'),
        (('Jacques Morel (composer)', 'Jacques Morel', '', "''fl.'' c. 1700–1749", "''fl.'' c. 1700", '1749', ''), "* [[Jacques Morel (composer)|Jacques Morel]] (''fl.'' c. 1700–1749)"),
        ((None, 'Joseph Abaco', ", or ''dall'Abaco'' ", '1710–1805', '1710', '1805', ''), "* [[Joseph Abaco]], or ''dall'Abaco'' (1710–1805)"),
    )
    for line, (groups, text) in zip(lines.splitlines(), expected):
        match = regex.match(list_pattern, line, flags=regex.VERBOSE)
        assert bool(match)
        assert match.groups() == groups
        assert match.group(0) == text


def test_list_pattern_irregular_dates():
    for line in lines_irreg.splitlines():
        match = regex.match(list_pattern_irregular_dates, line, flags=regex.VERBOSE)
        assert bool(match)


lines_interwiki_irregular = """* {{Ill|Gioan Pietro Del Buono|fr}} (''fl.'' 1641–1644; d. 1657)"""


lines_interwiki = """* {{Ill|Michel Farinel|de}} (1649–1726)
* {{Interlanguage link multi|Romanus Weichlein|de}} (1652–1706)
* {{Interlanguage link multi|Giovanni Antonio Piani|de}}, or ''Jean-Antoine Desplanes'' (1678–1760)
* {{ill|Jacques Morel (composer)|lt=Jacques Morel|fr|Jacques Morel (compositeur)}} (c. 1680 - c. 1740)"""


def test_list_pattern_interwiki_irregular_dates():
    for line in lines_interwiki_irregular.splitlines():
        match = regex.match(list_pattern_interwiki_irregular, line, flags=regex.VERBOSE)
        assert bool(match)


def test_list_pattern_interwiki():
    for line in lines_interwiki.splitlines():
        match = regex.match(list_pattern_interwiki, line, flags=regex.VERBOSE)
        assert bool(match)


redirect_texts = """#REDIRECT [[Richard Wilkins]]
#REDIRECT [[Sophia Dussek]] {{R from alternate name}}
#REDIRECT [[Tôn-Thất Tiết]] {{R from title without diacritics}}
#redirect [[Zacharia Paliashvili]]"""


def test_redir_name():
    redir_names = ["Richard Wilkins", "Sophia Dussek", "Tôn-Thất Tiết", "Zacharia Paliashvili"]
    for s, redir in zip(redirect_texts.splitlines(), redir_names):
        res = get_redir_name(s)
        assert res == redir


date_infos = """born 1622
fl. from 1641, died 1687
''fl.'' 1666, d. before 1650
''fl.'' early 17th century; d. before 1650
died c. 1670
''fl.'' from 1662; d. 1718
''fl.'' c. 1670
''fl.'' 1664
born 17th century; ''fl.'' from 1705
d. after 1692
''fl.'' 1715
b. 1577; ''fl.'' 1619"""
date_infos_results = [
    ('1622', '', ''),
    ('', '1687', 'from 1641'),
    ('', 'before 1650', '1666'),
    ('', 'before 1650', 'early 17th century'),
    ('', 'c. 1670', ''),
    ('', '1718', 'from 1662'),
    ('', '', 'c. 1670'),
    ('', '', '1664'),
    ('17th century', '', 'from 1705'),
    ('', 'after 1692', ''),
    ('', '', '1715'),
    ('1577', '', '1619'),
]


def test_get_date_info():
    for line, expected in zip(date_infos.splitlines(), date_infos_results):
        res = get_date_info(line)
        assert res == expected


@pytest.mark.parametrize(
    'lifetime,expected',
    [
        ('fl. 1418 – after 1421', ('', '', '1418 – after 1421')),
        ('1357 – 1423', ('1357', '1423', '')),
        ('died 1418', ('', '1418', '')),
        ('c.1200 – before 1269', ('c.1200', 'before 1269', '')),
    ])
def test_birth_death_flourish_from_lifetime(lifetime, expected):
    assert birth_death_flourish_from_lifetime(lifetime) == expected

