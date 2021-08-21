import logging
from typing import Tuple

import pandas as pd
try:
    import regex
except ImportError:
    import re as regex
import yaml

logging.basicConfig(level=logging.INFO, format='{asctime} {message}', style='{')

BASE_URL = "https://en.wikipedia.org/wiki"
lists = [
    "List of Medieval composers",
    "List of Renaissance composers",
    "List of Baroque composers",
    "List of Classical-era composers",
    "List of Romantic-era composers",
    "List of 20th-century classical composers",
    "List of 21st-century classical composers",
    ]

era_config = """
Medieval:
    type: list
Renaissance:
    type: list
Baroque:
    type: list
Classical-era:
    type: table
    birth_col: Date born
    died_col: Date died
Romantic-era:
    type: table
    birth_col: Date born
    died_col: Date died
20th-century classical:
    type: table
    birth_col: Year of birth
    died_col: Year of death
21st-century classical:
    type: table
    birth_col: Date born
    died_col: Date died
"""
era_config = yaml.safe_load(era_config)


"""
PART 1
Fetching tables from internet as HTML and parsing those
This first part was not useful as I remember, use the A1*.ipynb instead
"""


def fetch_composer_list(era_name: str, era_config: dict = era_config) -> pd.DataFrame:
    config = era_config[era_name]
    assert config["type"] == "table"
    list_name = f"List of {era_name} composers".replace(' ', '%20')
    url = f"{BASE_URL}/{list_name}"
    logging.info(f"Fetching url {url}")
    df = find_composer_table(url)
    df.rename(columns={config["birth_col"]: "birth", config["died_col"]: "death", }, inplace=True)
    df["era"] = era_name
    # df = dfs[2]
    logging.info(df.head())
    return df


def find_composer_table(url):
    dfs = pd.read_html(url)
    logging.info(f"{len(dfs)} tables on the page")
    for i, df in enumerate(dfs):
        print(i, df.columns)
        print(df.head(2))
        if "Name" in df.columns and "Nationality" in df.columns:
            break
    logging.info(i)
    return df


def get_table_eras(config: dict) -> list:
    return [era_name for era_name in config if config[era_name]['type'] == 'table']


def main():
    """Does not work well, maybe I should delete it"""
    dfs = []
    columns = 'Name birth death Nationality era'.split()
    exclude = ["Classical-era", "21st-century classical"]
    for era_name in get_table_eras(era_config):
        if era_name in exclude:
            continue
        df = fetch_composer_list(era_name)
        print(df.head(1), df.columns)
        df = df[columns]
        dfs.append(df)
        print(len(df), df.columns)
    full_df = pd.concat(dfs, sort=False)
    print([len(df) for df in dfs], len(full_df))
    full_df.to_csv('composers_.csv', index=False)
    print(full_df.head())


"""
PART 2
Fetching data from wiki articles
The useful part
"""


def fetch_from_wiki(era_name: str, get_nationality_from_title: bool = True) -> pd.DataFrame:
    with open(f"List of {era_name} composers.wiki".replace(" ", "_")) as f:
        data = []
        nationality = ''
        for line in f:

            if get_nationality_from_title and line.startswith('=='):
                match = regex.match('==([^=][^=]*)==', line)
                if match:
                    nationality = match.group(1).strip()
                    print(nationality)

            if line.startswith("*"):
                for regexp, transformation in (
                        (list_pattern_irregular_dates, list_irregular_transformation),
                        (list_pattern, list_normal_transformation),
                        (list_pattern_interwiki_irregular, list_irregular_transformation),
                        (list_pattern_interwiki, list_normal_transformation),
                ):
                    match = regex.match(regexp, line, flags=regex.VERBOSE)
                    if match:
                        article, name, birth, death, flourish = transformation(match)
                        break

                if not match:
                    print(line)
                else:
                    data.append((article, name, birth, death, flourish, nationality))

        # different_article = [(name, a, birth, death) for a, name, birth, death in data if a is not None and a != name]
        # print(*different_article, sep="\n")

        data = [(a if a else name, name, birth, death, flourish, nationality) for a, name, birth, death, flourish, nationality in data]
        dat = list(zip(['article', 'name', 'birth', 'death', 'flourish', 'nationality'], list(zip(*data))))
        # print(dat[:4])
        df = pd.DataFrame(dict(dat))
        df['era'] = era_name
        print(df.head())
        df.to_csv(f'composers_{era_name}_.csv', index=False)


def list_normal_transformation(match):
    """Works for both normal and interwiki link"""
    article, name, _, _, birth, death, *comment = match.groups()
    flourish = ''
    return article, name, birth, death, flourish


def list_irregular_transformation(match):
    """Works for both normal and interwiki link"""
    article, name, _, date_info, *comment = match.groups()
    birth, death, flourish = get_date_info(date_info)
    return article, name, birth, death, flourish


def get_date_info(date_info):
    date_info = date_info.replace(',', ';')
    date_chunks = date_info.split(';')
    prefixes = (
        ('born ', 'birth'),
        ('b. ', 'birth'),
        ('died ', 'death'),
        ('d. ', 'death'),
        ("fl. ", 'flourish'),
        ("fl.c. ", 'flourish'),
        ("''fl.'' ", 'flourish'),
    )

    date_dict = dict()
    for ch in date_chunks:
        ch = ch.strip()
        for prefix, field in prefixes:
            if ch.startswith(prefix):
                date_dict[field] = ch[len(prefix):]
                break
        else:  # no break == none of them fit
            print(ch)
    return tuple(map(lambda k: date_dict.get(k, ''), ("birth", "death", "flourish")))


name_regex = r"""
   \[\[
     (?:([^|]*)\|)?
     ([^|]*)
   \]\]
   """
regular_date_pattern = r"""
   ([^(]*)
   \s*
   \(
     (
        ([^-)–]*)
          [-–]
        ([^)]*)
    )
   \)
   \s*
   (.*)"""
irregular_data_pattern = """     \s*
        (?:
        \s*died[^,;)]*(?:[;,])?
        |
        \s*born[^,;)]*(?:[;,])?
        |
        \s*[bd]\.[^,;)]*(?:[;,])?
        |
        \s*(?:'')?fl[^,;)]*(?:[;,])?
        )+
     \s*
"""
list_pattern = rf"""\*\s*
   {name_regex}
   \s*
    {regular_date_pattern}
   """
list_pattern_irregular_dates = rf"""\*
   \s*
   {name_regex}
   \s*
   ([^(]*)
   \s*
   \(
   (
      {irregular_data_pattern}
   )
   \)
   \s*
   (.*)
   """
list_pattern_interwiki = rf"""\*
   \s*
   ()
   \{{\{{
     [^|}}]*
     \|
     ([^|}}]*)
     \|
     [^}}]*
   \}}\}}
   \s*
   {regular_date_pattern}
   """
list_pattern_interwiki_irregular = rf"""\*
   \s*
   ()
   \{{\{{
     [^|}}]*
     \|
     ([^|}}]*)
     \|
     [^}}]*
   \}}\}}
   \s*
   ([^(]*)
   \s*
   \(
   (
      {irregular_data_pattern}
   )
   \)
   \s*
   (.*)
   """
table_separator = r"\s*\|\|\s*"
romantic_pattern = rf"""\|\s*
   {name_regex}
   {table_separator}
    ([^|]*?)
   {table_separator}
    ([^|]*?)
   {table_separator}
    ([^|]*?)
   {table_separator}
   """


def fetch_from_wiki_romantic(era_name: str = 'Romantic-era') -> pd.DataFrame:
    with open(f"List of {era_name} composers.wiki".replace(" ", "_")) as f:
        data = []
        for line in f:
            match = regex.match(romantic_pattern, line, regex.VERBOSE)
            # if line.startswith("*"):
            #     print(line, match)
            if match:
                article, name, birth, death, nationality = match.groups()
                # if name2 is None:
                #     name2 = name
                data.append((article, name, birth, death, nationality))

        df = transform_data(data, era_name)
        df.to_csv(f'composers_{era_name}_.csv', index=False)


def transform_data(data, era_name):
    different_article = [
        (name, a, birth, death, nationality)
        for a, name, birth, death, nationality in data
        if a is not None and a != name]
    print(*different_article, sep="\n")
    data = [(a if a else name, name, birth, death, nationality) for a, name, birth, death, nationality in data]
    dat = list(zip(['article', 'name', 'birth', 'death', 'nationality'], list(zip(*data))))
    print(dat[:4])
    df = pd.DataFrame(dict(dat))
    df['era'] = era_name
    print(df.head())
    return df


def unify_renaissance_data_frames():
    """Unify the data from tables and lists into one file.

    Before that create the composers_Renaissance_.csv file and
    mv composers_Renaissance_.csv composers_Renaissance_list_.csv
    """
    dft = pd.read_csv("composers_Renaissance_table_.csv")
    dfl = pd.read_csv("composers_Renaissance_list_.csv")
    dfc = pd.concat([dfl, dft])
    dfc.to_csv("composers_Renaissance_.csv", index=False)


def birth_death_flourish_from_lifetime(lifetime: str) -> Tuple[str, str, str]:
    """Used for Medieval composers"""
    if lifetime.startswith("fl."):
        return "", "", lifetime[3:].strip()
    if lifetime.startswith("died"):
        return "", lifetime[4:].strip(), ""
    if lifetime.startswith("d."):
        return "", lifetime[2:].strip(), ""
    print(lifetime)
    birth, death = [t.strip() for t in lifetime.split("–")]
    return birth, death, ""


if __name__ == '__main__':
    # main()
    # df = fetch_composer_list("Classical-era")
    # print(df.columns, df.head())
    fetch_from_wiki("Renaissance")
    # fetch_from_wiki("Baroque")
    # fetch_from_wiki("Classical-era")
    # fetch_from_wiki("Medieval")
    # test_pattern()
    # fetch_from_wiki_romantic()
