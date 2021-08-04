from collections import Counter

import pandas as pd

# from fetch_wikipedia import era_config


def get_article_col(df, article_col=0):
    col = df[df.columns[article_col]]
    return list(col)


# def get_eras():
#     era_config = """
# Medieval:
#     type: list
# Renaissance:
#     type: list
# Baroque:
#     type: list
# Classical-era:
#     type: table
#     birth_col: Date born
#     died_col: Date died
# Romantic-era:
#     type: table
#     birth_col: Date born
#     died_col: Date died
# 20th-century classical:
#     type: table
#     birth_col: Year of birth
#     died_col: Year of death
# 21st-century classical:
#     type: table
#     birth_col: Date born
#     died_col: Date died
# """
#     eras = []
#     for k in era_config.splitlines():
#         if k.startswith(' '):
#             continue
#         k = k[:-1]
#         eras.append(k)
#     return eras


# eras = get_eras()
csv_files = "composers_21_century.csv  composers_Baroque.csv  composers_Classical-era.csv  composers.csv".split()
# csv_files = "composers_Baroque.csv  composers_Classical-era.csv  composers.csv".split()
# csv_files_col_num = [(fname, 0) for fname in csv_files]
csv_files_col_num = [('composers_21_century.csv', 1), ('composers_Baroque.csv', 0), ('composers_Classical-era.csv', 0), ('composers.csv', 0)]
# print(csv_files)
print(csv_files_col_num)


def get_articles(csv_files_col_num):
    article_titles = list()
    for file, col_num in csv_files_col_num:
        df = pd.read_csv(file)
        article_titles += get_article_col(df, article_col=col_num)
    return article_titles


def get_nones(csv_files):
    for file in csv_files:
        print(file)
        df = pd.read_csv(file)
        print(df[pd.isna(df.iloc[:, 0])].iloc[:, :5])

articles = get_articles(csv_files_col_num)
# print(articles)
# print(f"{len(set(articles))=}\n{len((articles))}")

# acount = Counter(articles)
# for art, count in acount.items():
#     if count > 1:
#         print(art, count)
# get_nones(csv_files)


def save_article_titles():
    ...
    articles = get_articles(csv_files_col_num)
    with open('articles_sort.txt', 'w') as f:
        f.write("\n".join(sorted(set(articles))) + "\n")


if __name__ == '__main__':
    save_article_titles()