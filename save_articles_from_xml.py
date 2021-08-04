"""
https://en.wikipedia.org/wiki/Special%3aExport
"""


from lxml import etree

tree = etree.parse('Wikipedia-20210804072445.xml')

kwargs = dict(namespaces=dict(x="http://www.mediawiki.org/xml/export-0.10/"))
xpath = tree.xpath(r'//x:page', **kwargs)

for elem in xpath:
    for child in elem:
        if child.tag.endswith('title'):
            file_name = f"composer_articles/{child.text}.wiki"
        elif child.tag.endswith('revision'):
            for text in child:
                if text.tag.endswith('text'):
                    # print((text.text[:77]))
                    with open(file_name, "w") as f:
                        f.write(text.text)
