# Use CouchDB to create a CouchDB client
# from cloudant.client import CouchDB
# client = CouchDB(USERNAME, PASSWORD, url='http://127.0.0.1:5984', connect=True)

# Use Cloudant to create a Cloudant client using account
import base64
import os
import time

from cloudant.client import Cloudant
from cloudant.client import CloudantDatabase
# client = Cloudant(USERNAME, PASSWORD, account=ACCOUNT_NAME, connect=True)
# or using url
USERNAME = 'horvath.arpad.ingatlan@gmail.com'
ACCOUNT_NAME = 'horvath.arpad.ingatlan@gmail.com'
PASSWORD = 'Ibm4Mikka'
# client = Cloudant(USERNAME, PASSWORD, url='https://b1598dbc-97a9-45ed-9b63-3a98176dd1bf-bluemix.cloudantnosqldb.appdomain.cloud')

ACCOUNT_NAME = 'b1598dbc-97a9-45ed-9b63-3a98176dd1bf-bluemix'
# API_KEY = "JFA-m5cqje-ntjFWqaJCHOJOEuE4J2rFXEvF4tcPcz49"
API_KEY = "ue1d6t9wKNzLBvuk6qjx14EhPcl9FnoYu849jyV5CgU_"
client = Cloudant.iam(ACCOUNT_NAME, API_KEY, connect=True)

# or with a 429 replay adapter that includes configured retries and initial backoff
# client = Cloudant(USERNAME, PASSWORD, account=ACCOUNT_NAME,
#                   adapter=Replay429Adapter(retries=10, initialBackoff=0.01))

# or with a connect and read timeout of 5 minutes
# client = Cloudant(USERNAME, PASSWORD, account=ACCOUNT_NAME,
#                   timeout=300)

# Perform client tasks...
session = client.session()
print(session)
# print('Username: {0}'.format(session['userCtx']['name']))
print('Databases: {0}'.format(client.all_dbs()))

composers: CloudantDatabase = client['composers']
print(dir(composers))
print(composers.values())
# print(type(composers.values))
print(composers.keys())


import pandas as pd
csv = pd.read_csv("composers_21st_century.csv")
print(csv.columns)
import uuid


partition = "composer"

for i, row in csv.iterrows():
    if i % 10 == 9:
        time.sleep(1.1)
    key = base64.urlsafe_b64encode(os.urandom(18)).decode("utf-8")
    key = uuid.uuid4().hex
    composer_dict = dict()
    composer_dict['name'] = row['name']
    composer_dict['birth'] = int(row['birth'])
    death = row['death']
    if death:
        composer_dict['death'] = int(death)
    composer_dict['nationality'] = row['nationality']
    composer_dict['era'] = row['era']
    composers.create_document(dict(
        _id=f"{partition}:{key}",
        **composer_dict,
    )
    )

# Disconnect from the server
client.disconnect()
