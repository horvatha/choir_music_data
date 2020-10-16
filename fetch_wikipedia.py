import logging
import pandas as pd
import regex
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
era_config = yaml.load(era_config)


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
    full_df.to_csv('composers.csv', index=False)
    print(full_df.head())


def fetch_from_wiki(era_name: str) -> pd.DataFrame:
    with open(f"List of {era_name} composers.wiki".replace(" ", "_")) as f:
        data = []
        for line in f:
            pattern = r"""\*\s*
               \[\[
                 ([^)|]*)
                 (?:\|([^)]*))?
               \]\]
               \s*
               \(
                 (
                    ([^)-]*)
                      -
                    ([^)]*)
                )"""
            pattern = r"""\*\s*
               \[\[
                 (?:([^)|]*)\|)?
                 ([^)|]*)
               \]\]
               \s*
               \(
                 (
                    ([^)-]*)
                      -
                    ([^)]*)
                )"""
            match = regex.match(pattern, line, regex.VERBOSE)
            if match:
                article, name, _, birth, death = match.groups()
                # if name2 is None:
                #     name2 = name
                data.append((article, name, birth, death))
        print(*[(name, a, len(name), len(a)) for a, name, birth, death in data if a is not None and a != name], sep="\n")


if __name__ == '__main__':
    # main()
    # df = fetch_composer_list("Classical-era")
    # print(df.columns, df.head())
    fetch_from_wiki("Baroque")