import os
import itertools
from rdflib import Graph, URIRef, Namespace, RDF, RDFS, OWL, XSD
from rdflib.resource import Resource
from rdflib.namespace import NamespaceManager, ClosedNamespace
import requests
from flask import Flask, request, render_template, render_template_string, redirect


SKOS = Namespace("http://www.w3.org/2004/02/skos/core#")
DCES = Namespace("http://purl.org/dc/elements/1.1/")
DCT = Namespace("http://purl.org/dc/terms/")
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

rq_prefixes = u"\n".join("prefix %s: <%s>" % (k.lower(), v)
        for k, v in NAMESPACES.items())

LANG = 'sv'

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

query_templates = {}
def load_query_templates():
    for name in ['auth', 'index']:
        with open(os.path.join(os.path.dirname(__file__), name + '.rq')) as f:
            text = rq_prefixes + "\n"*2 + f.read()
            query_templates[name] = (lambda text=text, **kws:
                    render_template_string(text, **kws))
load_query_templates()

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
prefixes = u"\n    ".join("%s: %s" % (k.lower(), v) for k, v in NAMESPACES.items()
        if k not in u'RDF RDFS OWL XSD')

view_context = {var: globals()[var] for var in
    ('prefixes', 'vocab', 'type_curies', 'l10n', 'is_resource', 'is_described')}
view_context.update(vars(itertools))
view_context.update(vars(__builtins__))
view_context.update(NAMESPACES,
        libris_link=lambda ref: ref.replace(RESOURCE_BASE, "/"),
        kringla_link=lambda ref: ref.replace("kulturarvsdata.se/", "kringla.nu/kringla/objekt?referens="))


app = Flask(__name__)

@app.before_request
def reload_templates():
    if app.debug:
        load_query_templates()


@app.route('/')
def index():
    return redirect('/auth')


@app.route('/auth')
def auth_index():
    res = run_query(query_templates['index']())
    graph = to_graph(res.content)
    ctx = dict(view_context, lang=LANG, graph=graph)
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
    qt = query_templates[rtype]
    #if qt:
    rq = qt(this=uri.n3(), services=SERVICES)
    if fmt == 'rq':
        return rq, 200, {'Content-Type': 'text/plain'}
    res = run_query(rq)
    #else:
    #    url = data_base + path + '.n3'
    #    res = requests.get(url)
    graph = to_graph(res.content)
    this = graph.resource(uri)

    if fmt in ('html', 'xhtml'):
        ctx = dict(view_context, path=path, lang=LANG, this=this, curies=graph.qname)
        return render_template(rtype + '.html', **ctx)
    else:
        headers = {'Content-Type': MIMETYPES.get(fmt) or 'text/plain'}
        fmt = {'rdf': 'xml', 'ttl': 'turtle'}.get(fmt) or fmt
        return graph.serialize(format=fmt), 200, headers


if __name__ == '__main__':

    from optparse import OptionParser
    oparser = OptionParser()
    oparser.add_option('-d', '--debug', action='store_true', default=False)
    oparser.add_option('-s', '--use-services')
    opts, args = oparser.parse_args()

    app.debug = opts.debug

    if opts.use_services:
        use_services = opts.use_services.split(',')
        SERVICES = {k: v for (k, v) in SERVICES.items() if k in use_services}
        print "Using services:", SERVICES

    app.run(host='0.0.0.0')
