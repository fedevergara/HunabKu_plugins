"""CvLAC profiles converted with cvlac-json: MongoDB queries and JSON-LD views.

A profile is served without its long lists (PARTS); each list is served by pages. Items keep the
JSON-LD @id they have in the whole document (``<profile IRI>#/works/<index>``), so the pages of a
profile merge into the same graph as the full document.
"""
from cvlac_json import to_jsonld
from cvlac_json.jsonld import pointer

PARTS = ("works", "projects", "events", "awards", "sections")
EXCLUDE = ("profile.Sexo",)  # personal data that is not served
API_KEYS = ("parts", "page")  # API metadata, left out of the JSON-LD graph


def _size(expr):
    return {"$size": {"$cond": [{"$isArray": expr}, expr, []]}}


def profile(coll, cod_rh):
    """The profile without PARTS, plus ``_totals`` (items in each part); None if it does not exist."""
    totals = {p: _size("$" + p) for p in PARTS if p != "sections"}
    totals["sections"] = {"$sum": {"$map": {"input": {"$objectToArray": {"$ifNull": ["$sections", {}]}},
                                            "in": _size("$$this.v")}}}
    pipeline = [{"$match": {"_id": cod_rh}},
                {"$addFields": {"_totals": totals}},
                {"$project": {k: 0 for k in ("_id",) + PARTS + EXCLUDE}}]
    return next(coll.aggregate(pipeline), None)


def part(coll, cod_rh, name, skip, size):
    """Items [skip, skip + size) of a part and its total; None if the profile does not exist.

    Items come as (section title or None, index in its list, item). Sections are paged as one
    list, in document order.
    """
    if name == "sections":
        doc = coll.find_one({"_id": cod_rh}, {"sections": 1})
        if doc is None:
            return None
        flat = [(title, i, item) for title, items in (doc.get("sections") or {}).items()
                for i, item in enumerate(items or [])]
        return flat[skip:skip + size], len(flat)
    array = {"$cond": [{"$isArray": "$" + name}, "$" + name, []]}
    pipeline = [{"$match": {"_id": cod_rh}},
                {"$project": {"total": _size("$" + name), "items": {"$slice": [array, skip, size]}}}]
    doc = next(coll.aggregate(pipeline), None)
    if doc is None:
        return None
    return [(None, skip + i, item) for i, item in enumerate(doc["items"])], doc["total"]


def part_body(name, cod_rh, window):
    """JSON document of a page of a part."""
    if name != "sections":
        return {"cod_rh": cod_rh, name: [item for _, _, item in window]}
    sections = {}
    for title, _, item in window:
        sections.setdefault(title, []).append(item)
    return {"cod_rh": cod_rh, "sections": sections}


def jsonld(doc, base, name=None, window=()):
    """JSON-LD view made by cvlac-json; for a page, items get the @id of their place in the profile."""
    ld = to_jsonld(doc, base=base)
    ld["@context"].update({k: None for k in API_KEYS})
    if name:
        iri = ld["@id"]
        items = [it for its in ld["sections"].values() for it in its] if name == "sections" else ld[name]
        for (title, i, _), item in zip(window, items):
            if isinstance(item, dict) and "@id" in item:
                item["@id"] = iri + (pointer("sections", title, i) if title is not None else pointer(name, i))
    return ld
