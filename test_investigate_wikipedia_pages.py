import pytest

from investigate_wikipedia_pages import get_redir_name, get_not_unique_composers

redirect_texts = """#REDIRECT [[Richard Wilkins]]
#REDIRECT [[Sophia Dussek]] {{R from alternate name}}
#REDIRECT [[Tôn-Thất Tiết]] {{R from title without diacritics}}
#redirect [[Zacharia Paliashvili]]"""


def test_redir_name():
    redir_names = ["Richard Wilkins", "Sophia Dussek", "Tôn-Thất Tiết", "Zacharia Paliashvili"]
    for s, redir in zip(redirect_texts.splitlines(), redir_names):
        res = get_redir_name(s)
        assert res == redir


@pytest.mark.parametrize(
    "era1,  era2, example_article",
    [
        ('Baroque', 'Renaissance', 'Robert Johnson (English composer)'),
        ('20_century', '21_century', 'Robert_Ward_(composer)'),
    ]
)
def test_get_not_unique_composers(era1,  era2, example_article):
    assert example_article in get_not_unique_composers(era1, era2)