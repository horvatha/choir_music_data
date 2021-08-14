"""
https://towardsdatascience.com/wikipedia-api-for-python-241cfae09f1c
https://pypi.org/project/wikipedia/

https://towardsdatascience.com/wikipedia-as-a-valuable-data-science-tool-6769991b43b7 base article with many links

See also other tool, the bot https://www.mediawiki.org/wiki/Manual:Pywikibot
"""

import wikipedia

mozart = wikipedia.page('Wolfgang Amadeus Mozart')
print(mozart.summary)
