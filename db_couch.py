from typing import Any

import couchdb
client: couchdb.Server = couchdb.Server('http://admin:admin@127.0.0.1:5984/')

#print(dir(client))
#print(client.session.__doc__)
# Perform client tasks...
#session = client.session()
#print(session)
# print('Username: {0}'.format(session['userCtx']['name']))
# print('Databases: {0}'.format(client.()))

db_name = "composers"
# client.delete(db_name)
# client.create(db_name)
composers: couchdb.client.Database = client[db_name]
print(dir(composers))
print(type(composers))
print(composers.info())


import pandas as pd
csv = pd.read_csv("composers.csv")
print(csv.columns)
import uuid
import base64
import os


partition = "composer"

for i, row in csv.iterrows():
    key = base64.urlsafe_b64encode(os.urandom(18)).decode("utf-8")
    key = uuid.uuid4().hex
    composer_dict = dict()
    composer_dict['name'] = row['name']
    composer_dict['birth'] = int(row['birth'])
    death = row['death']
    if not pd.isna(death):
            composer_dict['death'] = int(death)
    composer_dict['nationality'] = row['nationality']
    composer_dict['era'] = row['era']
    if True:
        composers.save(dict(
            _id=f"{partition}:{key}",
            **composer_dict,
        )
        )

# Disconnect from the server
for id in composers:
    composer = composers[id]
    # print(composer.items())
    comp_dict = dict(composer)
    if "death" not in comp_dict:
        print(comp_dict)

print(len(composers))
print(len(csv))
