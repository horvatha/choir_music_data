"""
Helps creating the list of composers for downloading the wiki sources
and getting the lengths of the articles.

For the latter it uses dictionary from the name to the article name if it differs.
Article file names contain spaces, not underscores.

There is a plan for getting relationships (father, teacher...) using NLP or simpler tool.
"""


import os
import re
from operator import itemgetter
from pathlib import Path

import toolz

composers = [
    os.path.splitext(file_name)[0] for file_name in os.listdir(Path("composer_articles"))
    if file_name.endswith('wiki')
]


def print_iterable(it, length=None, **kwargs):
    if length:
        list_ = list(it)[:length]
    else:
        list_ = list(it)
    print(list_, **kwargs)


def print_iterable_separate_lines(it, tranformation=lambda x: x, **kwargs):
    list_ = "\n".join(tranformation(i) for i in it)
    print(list_, **kwargs)


def get_file_length(composer):
    return toolz.pipe(
        composer,
        get_article_name,
        lambda c: f"composer_articles/{c}.wiki",
        lambda file_name: open(file_name).read(),
        lambda file_content: len(file_content)
    )


def get_article_name(composer):
    article: str = alternative_names.get(composer, composer)
    article = article.replace('_', ' ')
    return article


def get_file_text(composer):
    return toolz.pipe(
        composer,
        lambda c: f"composer_articles/{c}.wiki",
        lambda file_name: open(file_name).read(),
    )


@toolz.functoolz.curry
def get_file_text_n(n, composer):
    return toolz.pipe(
        composer,
        lambda c: f"composer_articles/{c}.wiki",
        lambda file_name: open(file_name).read(),
    )


redir_regex = r'\s*\[\[([^\]]*)\]\]'


def get_redir_name(text, default='not found'):
    if not text[:9].upper() == "#REDIRECT":
        return None
    res = re.search(redir_regex, text[9:])
    if res:
        return res.groups(1)[0]
    else:
        return default


def lengths():
    lengths = toolz.map(get_file_length, composers)
    result = zip(composers, lengths)
    sorted_lengths = sorted(result, key=itemgetter(1), reverse=True)
    print_iterable(sorted_lengths, 22)
    print_iterable(sorted_lengths, file=open("lengths_.py", 'w'))


def redir():
    not_composers_with_text = filter(
        lambda pair: 'composer' not in pair[0].lower(),
        zip(map(get_file_text,  composers), composers)
    )
    not_composers_redirect_with_text = filter(
        lambda pair: 'composer' not in pair[0].lower() and '#REDIRECT' not in pair[0],
        zip(map(get_file_text,  composers), composers)
    )
    not_composers_redirect_with_text = filter(
        lambda pair: '#REDIRECT' in pair[0],
        zip(map(get_file_text,  composers), composers)
    )


    redir_data = map(toolz.compose(lambda s: s.split('\n')[0], itemgetter(0)), not_composers_with_text)

    # redir_re_data = map(toolz.compose(lambda s: re.search(redir_regex, s).groups(1), itemgetter(0)), not_composers_with_text)
    not_composers = map(itemgetter(1), not_composers_redirect_with_text)
    # print_iterable_separate_lines(redir_data)


    not_composers_text = map(get_file_text_n(77), not_composers)
    # print_iterable(not_composers_text, end='\n-------------------', file=open("result.txt", 'w'))

    # print_iterable_separate_lines(not_composers, file=open("_not_redirects.txt", 'w'))

    name_pairs = map(lambda pair: ",".join([pair[1], get_redir_name(pair[0]),]), not_composers_redirect_with_text)
    # print_iterable_separate_lines(name_pairs, repr)
    print_iterable_separate_lines(name_pairs, file=open('redirects_.txt', 'w'))


alternative_name_files = ["redirects.txt", "not_redirects.txt"]


def get_real_article_titles():
    import pandas as pd
    articles = set()

    for file in alternative_name_files:
        df = pd.read_csv(file)
        articles |= set(df.article)
    sorted_articles = sorted(articles)
    print('\n'.join(sorted_articles), file=open('real_articles.txt', "w"))


def get_alternative_names() -> dict:
    import pandas as pd
    names  = list()
    articles = list()
    for file in alternative_name_files:
        df = pd.read_csv(file)
        articles.extend(df.article)
        names.extend(df.name)
    alternative_names = dict()
    for name, article in zip(names, articles):
        alternative_names[name] = article
    # print(alternative_names, file=open('alternative_names_.py', "w"))
    return alternative_names


def create_composer_dict():
    for file in files.splitlines():
        print(f'mv "composer_articles/old/{file}" composer_articles/old/redirects')


if __name__ == '__main__':
    # redir()
    # get_real_article_titles()
    alternative_names = get_alternative_names()
    lengths()