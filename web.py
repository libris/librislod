# -*- coding: UTF-8 -*-
import os
import itertools
import json
from rdflib import Graph, URIRef, Namespace, RDF, RDFS, OWL, XSD
from rdflib.resource import Resource
from rdflib.namespace import NamespaceManager, ClosedNamespace
import requests
from flask import Flask, request, render_template, redirect


SKOS = Namespace("http://www.w3.org/2004/02/skos/core#")
DC11 = Namespace("http://purl.org/dc/elements/1.1/")
DC = Namespace("http://purl.org/dc/terms/")
FOAF = Namespace("http://xmlns.com/foaf/0.1/")
BIBO = Namespace("http://purl.org/ontology/bibo/")
RDES = Namespace("http://RDVocab.info/Elements/")
RDES2 = Namespace("http://RDVocab.info/ElementsGr2/")
DBPOWL = Namespace("http://dbpedia.org/ontology/")
DBPROP = Namespace("http://dbpedia.org/property/")
LIBRIS = Namespace("http://libris.kb.se/vocabulary/experimental#")
KSAMSOK = Namespace("http://kulturarvsdata.se/ksamsok#")


NAMESPACES = {k: o for k, o in vars().items()
        if isinstance(o, (Namespace, ClosedNamespace))}

ns_mgr = NamespaceManager(Graph())
for k, v in NAMESPACES.items():
    ns_mgr.bind(k.lower(), v)

RQ_PREFIXES = u"\n".join("prefix %s: <%s>" % (k.lower(), v)
        for k, v in NAMESPACES.items())

LANG = 'sv'

with open(os.path.join(os.path.dirname(__file__), 'labels.json')) as f:
    LABELS = json.load(f)


def type_curies(r):
    return " ".join(t.qname() for t in r.objects(RDF.type))

def l10n(literals, lang=LANG):
    for l in literals:
        if l.language == lang:
            break
    return l

def is_resource(o):
    return isinstance(o, Resource)

def is_described(resource):
    return (resource.identifier, None, None) in resource.graph


# {bib | auth | hld?} / {id}
RESOURCE_BASE = "http://libris.kb.se/resource/"
#data_base = "http://data.libris.kb.se/open/"

SERVICES = {
    "dbp": "http://dbpedia.org/sparql",
    #"raa": "http://193.10.40.180:8080/ksamsok/query",
    "raa": "http://192.121.221.30/sparql/raa",
    "ra": "http://192.121.221.30/sparql/ra"
}
ENDPOINT = u"http://libris.kb.se/sparql"

def to_graph(data):
    graph = Graph()
    graph.parse(data=data, format='turtle')
    graph.namespace_manager = ns_mgr
    return graph

def run_query(rq, accept='text/turtle'):
    return requests.post(ENDPOINT, data={'query': rq},
            headers={'Accept': accept})


MIMETYPES = {
    'html': 'text/html',
    'xhtml': 'application/xhtml+xml',
    'ttl': 'text/turtle',
    'n3': 'text/n3',
    'rdf': 'application/rdf+xml',
    'xml': 'text/xml',
    'json': 'application/json',
    'jsontxt': 'text/json'
}
mime_names = {v: k for k, v in MIMETYPES.items()}

accept_mimetypes = MIMETYPES.values()

def _conneg_format(suffix=None):
    fmt = request.args.get('format') or suffix
    req_mime = request.accept_mimetypes.best_match(accept_mimetypes, 'text/html')
    if req_mime and not fmt:
        fmt = mime_names.get(req_mime)
    return fmt


vocab = u"http://schema.org/"
prefixes = u"\n    ".join("%s: %s" % (k.lower(), v)
        for k, v in sorted(NAMESPACES.items())
        if k not in u'RDF RDFS OWL XSD SKOS DC DC11 FOAF')


def datasource_label(resource):
    rid = resource.identifier
    if "dbpedia.org" in rid:
        return u"DBPedia"
    elif "viaf.org" in rid:
        return u"VIAF"
    elif "id.riksarkivet.se" in rid:
        return u"NAD"
    elif "kulturarvsdata.se" in rid:
        return u"K-samsök"
    else:
        return rid

def app_link(ref):
    return ref.replace(RESOURCE_BASE, "/")

def ext_link(ref):
    if "kulturarvsdata.se" in ref:
        return ref.replace("kulturarvsdata.se/", "kringla.nu/kringla/objekt?referens=")
    else:
        return ref


app = Flask(__name__)


@app.context_processor
def inject_view_context():
    ctx = {var: globals()[var] for var in
        ('prefixes', 'vocab', 'type_curies',
                'l10n', 'is_resource', 'is_described',
                'datasource_label', 'app_link', 'ext_link')}
    ctx.update(vars(itertools))
    ctx.update(vars(__builtins__))
    ctx.update(NAMESPACES)
    ctx.update(lang=LANG, labels=LABELS[LANG])
    return ctx


@app.route('/')
def index():
    return redirect('/auth')


@app.route('/auth')
def auth_index():
    res = run_query(render_template('queries/index.rq', prefixes=RQ_PREFIXES))
    graph = to_graph(res.content)
    ctx = dict(graph=graph)
    return render_template("index.html", **ctx)


@app.route('/<rtype>/<rid>')
def view(rtype, rid):
    if '.' in rid:
        rid, suffix = rid.rsplit('.', 1)
    else:
        suffix = None
    path = rtype + '/' + rid

    fmt = _conneg_format(suffix)
    uri = URIRef(RESOURCE_BASE + path)
    #if template:
    rq = render_template("queries/%s.rq" % rtype,
            prefixes=RQ_PREFIXES, this=uri.n3(), services=SERVICES)
    if fmt == 'rq':
        return rq, 200, {'Content-Type': 'text/plain'}
    res = run_query(rq)
    #else:
    #    url = data_base + path + '.n3'
    #    res = requests.get(url)
    graph = to_graph(res.content)
    this = graph.resource(uri)

    if fmt in ('html', 'xhtml'):
        return render_template(rtype + '.html',
                path=path, this=this, curies=graph.qname)
    else:
        headers = {'Content-Type': MIMETYPES.get(fmt) or 'text/plain'}
        fmt = {'rdf': 'xml', 'ttl': 'turtle'}.get(fmt) or fmt
        return graph.serialize(format=fmt), 200, headers


if __name__ == '__main__':

    from optparse import OptionParser
    oparser = OptionParser()
    oparser.add_option('-d', '--debug', action='store_true', default=False)
    oparser.add_option('-p', '--port', type=int, default=5000)
    oparser.add_option('-l', '--lang')
    oparser.add_option('-s', '--use-services')
    opts, args = oparser.parse_args()

    app.debug = opts.debug

    if opts.lang:
        LANG = opts.lang

    if opts.use_services:
        use_services = opts.use_services.split(',')
        SERVICES = {k: v for (k, v) in SERVICES.items() if k in use_services}
        print "Using services:", SERVICES

    app.run(host='0.0.0.0', port=opts.port)
