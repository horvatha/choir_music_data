# Composer database project

This project is about collecting composer data and share them via Internet.
There is a plan for getting relationships (father, teacher...) using NLP or simpler tool and investigate that network.
If this project can give back to the data sources we use, it will.
(I still [made some corrections](https://en.wikipedia.org/wiki/Special:Contributions/Harp) in the Wikipedia composer lists when I found some typo or misleading information.)

You can see the [collected data](https://pyedu.hu/arpad/composers/) here.

If you want to participate in this project, or you can give me some data, [reach me](https://pyedu.hu/arpad/email.png).

## Lists of composers we use

From this page: https://en.wikipedia.org/wiki/Lists_of_composers

- List of Medieval composers
- List of Renaissance composers
- List of Baroque composers
- List of Classical-era composers
- List of Romantic-era composers
- List of 20th-century classical composers
- List of 21st-century classical composers

## How to collect data?

- table data: using the A1*.ipynb notebooks
- lists: using fetch_wikipedia.py

## TODO

- Adding nationality to Renaissance
- Merge Renaissance and Renaissance table (fetched from http tables)
- Creating the Medieval csv
- Fetching the missing articles from Wikipedia
  (see save_articles_from_xml.py and investigate_wikipedia_pages.py)
- Sanity checking
- Web page
- Search in Web page
- There is a plan for getting relationships (father, teacher...) using NLP or simpler tool.

## Useful data

- Useful music databases https://libguides.butler.edu/c.php?g=34052&p=216855
- https://www.naxos.com/feature/Naxos-Works-Database.asp
