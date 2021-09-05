#!/usr/bin/env python3
import dataclasses
from operator import itemgetter

import numpy as np
import pandas as pd
import toolz
from icecream import ic

from fetch_wikipedia import get_csv_file_names
from utils import get_name_for_ordering

base, csv = get_csv_file_names()[1]


def get_value_or_empty_string(value):
    return str(value) if not pd.isnull(value) else ""


def create_circa(value: str):
    value = value.strip()
    if value.startswith('c.'):
        return f"{{{{circa|{value[3:]}}}}}"
    return value


@dataclasses.dataclass
class Lifetime:
    birth: str
    death: str
    flourish: str


def create_wikitable(base, csv):
    df = pd.read_csv(csv)
    df.sort_values('order', inplace=True)
    with open(f"table_{base}_.wiki", "w") as f:
        # print("== Whole table ordered by approximate birth date ==\n ", file=f)
        print('{| class="wikitable sortable plainrowheaders"\n|+ Renaissance composers', file=f)
        print(
            '''! scope="col" | Name
! scope="col" | Lifetime
! scope="col" | Nationality
! scope="col" | Works
! scope="col" class="unsortable"|{{Abbr|Ref.|Reference}}''',
            file=f
        )
        for i in df.iterrows():
            index, row = i
            lifetime = Lifetime(
                create_circa(get_value_or_empty_string(row.birth)),
                create_circa(get_value_or_empty_string(row.death)),
                create_circa(get_value_or_empty_string(row.flourish)),
            )
            if lifetime.birth and lifetime.death:
                first = f"{lifetime.birth} – {lifetime.death}"
            elif lifetime.death:
                first = f"died {lifetime.death}"
            elif lifetime.birth:
                first = f"born {lifetime.birth}"
            else:
                first = ""

            if lifetime.flourish:
                lifetime.flourish.replace('-', '–')
                second = f"{{{{fl|{lifetime.flourish}}}}}"
            else:
                second = ""

            lifetime_str = ", ".join([first, second]) if first and second else first + second
            approx_birth = row[9]
            ordered_lifetime = f"{{{{sort|{approx_birth}|{lifetime_str}}}}}"

            wikilink = f"[[{row.article}|{row['name']}]]" if row.article else f"{row['name']}"
            if row.article == row["name"]:
                wikilink = f"[[{row['name']}]]"
            ordered_wikilink = f"{{{{sort|{get_name_for_ordering(row['name'])}|{wikilink}}}}}"

            cols = "\n| ".join(
                str(get_value_or_empty_string(val))
                for val in toolz.concat([itemgetter(5, 7)(row), iter([""])]))
            print(f"|-\n| {ordered_wikilink} || {ordered_lifetime} || {cols}", file=f)
        print("|}", file=f)


def create_wikitable1(base, csv):
    csv = "Ren.csv"
    df = pd.read_csv(csv)
    df.sort_values('order', inplace=True)
    with open(f"table_{base}_.wiki", "w") as f:
        print('{| class="wikitable"\n|+ Renaissance composers', file=f)
        print(
            "|-\n! " + " !! ".join(('Name', 'Year of Birth', 'Year of Death', 'Flourished', 'Nationality', 'Remark')),
            file=f
        )
        for i in df.iterrows():
            index, row = i
            wikilink = f"[[{row.article}|{row['name']}]]" if row.article else f"{row['name']}"
            if row.article == row["name"]:
                wikilink = f"[[{row['name']}]]"
            flourish = get_value_or_empty_string(row.flourish)
            cols = " || ".join(str(get_value_or_empty_string(val)) for val in itemgetter(2, 3, 4, 5, 7)(row))
            print(f"|-\n| {wikilink} || {cols}", file=f)
        print("|}", file=f)


def save_ordered():
    csv = "Ren.csv"
    df = pd.read_csv(csv)
    df.sort_values('order', inplace=True)
    ic(df.head())
    df.to_csv('Ren_ordered_.csv', index=False)


century_dict = {'late 15th century ': '1470',
 'late 15th century–early 16th century': '1500',
 '14th century': '1350',
 'sometime in the first half of the 15th century': '1425',
 'late 15th – early 16th century': '1500',
 'early 16th century': '1520',
 'early 17th century ': '1620',
 'late 14th century': '1380',
 'second half of the 14th century': '1375',
 'second half of the 15th century': '1475',
 'late 15th century': '1480'}


if __name__ == '__main__':
    csv = "Ren.csv"  # TODO remove
    create_wikitable(base, csv)
    # save_ordered()
