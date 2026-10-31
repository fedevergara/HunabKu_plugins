"""GrupLAC groups converted by Yuku (yuku.gruplac_related_works): MongoDB queries and JSON-LD views.

The JSON-LD view is the same document plus @context, @id and @type, as cvlac-json does for CvLAC: it uses
the same terms where the keys mean the same (title, authors, doi, cod_rh...) and the GrupLAC vocabulary
otherwise. Members and products get ``<group IRI>#/members/<index>`` and ``#/production/<index>``.
"""
from cvlac_json.jsonld import context, pointer
from hunabku_dam import common

ID = "group_code"
VOCAB = "https://github.com/colav/HunabKu_plugins/blob/main/HunabKu_dam/docs/gruplac.md#"
PARTS = ("members", "production")
EXCLUDE = ("basic.E-mail",)  # personal data that is not served
PROVENANCE = ("parser", "source", "bibliographic_transformation")
TYPES = {"members": "schema:OrganizationRole", "production": "schema:CreativeWork"}
TERMS = {
    "group_code": "schema:identifier",
    "group_name": "schema:name",
    "url_gruplac": "schema:url",
    "year": {"@id": "schema:datePublished", "@type": "xsd:gYear"},
    "issn": "schema:issn",
    "isbn": "schema:isbn",
    "publisher": "schema:publisher",
    "language": "schema:inLanguage",
    "start_date": "schema:startDate",
    "end_date": "schema:endDate",
}


def get(coll, group_code):
    """The group without PARTS and with its provenance under ``_provenance``, plus ``_totals``."""
    provenance = {"_provenance": {k: "$" + k for k in PROVENANCE}}
    return common.get(coll, group_code, PARTS, EXCLUDE + PROVENANCE, add=provenance)


part = common.part


def part_body(name, group_code, window):
    return {ID: group_code, name: [item for _, _, item in window]}


def jsonld(doc, base, name=None, window=()):
    ctx = context(VOCAB, labels=list(doc.get("basic") or {}))
    ctx.update(TERMS)
    ctx.update({k: None for k in common.API_KEYS})
    iri = base + doc[ID]
    for key in PARTS:
        indexes = [i for _, i, _ in window] if key == name else range(len(doc.get(key) or []))
        for i, item in zip(indexes, doc.get(key) or []):
            item["@id"], item["@type"] = iri + pointer(key, i), TYPES[key]
    return {"@context": ctx, "@id": iri, "@type": ["schema:Organization", "GruplacGroup"], **doc}


def parser(coll):
    p = (coll.find_one({}, {"parser": 1}) or {}).get("parser", {})
    return {k: p.get(k) for k in ("name", "version", "commit")}
