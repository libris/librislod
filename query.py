import sys
from rdflib import *
import requests

endpoint = sys.argv[1]

query = sys.argv[2]

data = requests.post(endpoint, data={'query': query}).content
try:
    Graph().parse(data=data).serialize(sys.stdout, format="turtle")
except:
    print "Error:"
    print data

