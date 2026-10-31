"""CvLAC profiles converted with cvlac-json: MongoDB queries and JSON-LD views.

In JSON-LD, items keep the @id they have in the whole document (``<profile IRI>#/works/<index>``), so
the pages of a profile merge into the same graph as the full document.
"""
from cvlac_json import to_jsonld
from cvlac_json.jsonld import pointer
from hunabku_dam import common

ID = "cod_rh"
PARTS = ("works", "projects", "events", "awards", "sections")
EXCLUDE = ("profile.Sexo",)  # personal data that is not served


def get(coll, cod_rh):
    """The profile without PARTS, plus ``_totals``; None if it does not exist."""
    sections = {"$sum": {"$map": {"input": {"$objectToArray": {"$ifNull": ["$sections", {}]}},
                                  "in": common.size("$$this.v")}}}
    doc = common.get(coll, cod_rh, PARTS, EXCLUDE, add={"_sections": sections})
    if doc is not None:
        doc["_totals"]["sections"] = doc.pop("_sections")
    return doc


def part(coll, cod_rh, name, skip, limit):
    """Like common.part; sections are paged as one list in document order, items carry their title."""
    if name != "sections":
        return common.part(coll, cod_rh, name, skip, limit)
    doc = coll.find_one({"_id": cod_rh}, {"sections": 1})
    if doc is None:
        return None
    flat = [(title, i, item) for title, items in (doc.get("sections") or {}).items()
            for i, item in enumerate(items or [])]
    return flat[skip:skip + limit], len(flat)


def part_body(name, cod_rh, window):
    """JSON document of a page of a part; sections are grouped by title."""
    if name != "sections":
        return {ID: cod_rh, name: [item for _, _, item in window]}
    sections = {}
    for title, _, item in window:
        sections.setdefault(title, []).append(item)
    return {ID: cod_rh, "sections": sections}


def jsonld(doc, base, name=None, window=()):
    """JSON-LD view made by cvlac-json; for a page, items get the @id of their place in the profile."""
    ld = to_jsonld(doc, base=base)
    ld["@context"].update({k: None for k in common.API_KEYS})
    if name:
        iri = ld["@id"]
        items = [it for its in ld["sections"].values() for it in its] if name == "sections" else ld[name]
        for (title, i, _), item in zip(window, items):
            if isinstance(item, dict) and "@id" in item:
                item["@id"] = iri + (pointer("sections", title, i) if title is not None else pointer(name, i))
    return ld


def parser(coll):
    """Parser of the collection, for the catalog."""
    p = (coll.find_one({}, {"_provenance.parser": 1}) or {}).get("_provenance", {}).get("parser", {})
    return {k: p.get(k) for k in ("name", "version", "commit")}
