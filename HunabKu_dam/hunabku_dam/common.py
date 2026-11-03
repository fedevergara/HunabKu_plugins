"""MongoDB queries and JSON-LD views shared by the scraped sources (cvlac-json and gruplac-json documents).

A document is served without its long lists (the parts of the source); each part is served by pages,
read with $slice so a page does not load the whole document. ``other_products`` (lists by section title) is
paged as one list in document order, and each page groups its items by title again.

Documents that did not fit in MongoDB (16 MB) were stored with their largest lists moved to
``<collection>_overflow`` (``_overflow`` in the document says which, see the batch that wrote them): they are
read back from there.
"""
from cvlac_json.jsonld import pointer

API_KEYS = ("parts", "page")  # API metadata, left out of the JSON-LD graph
MAPS = ("other_products",)  # parts that are lists by section title


def size(expr):
    """Length of an array expression; 0 when it is missing or not an array."""
    return {"$size": {"$cond": [{"$isArray": expr}, expr, []]}}


def map_size(expr):
    """Items in all the lists of an object expression (lists by section title)."""
    return {"$sum": {"$map": {"input": {"$objectToArray": {"$ifNull": [expr, {}]}}, "in": size("$$this.v")}}}


def restore(coll, doc, parts=None):
    """Puts back in ``doc`` the lists moved to the overflow collection (only those of ``parts``, if given)."""
    overflow = coll.database[coll.name + "_overflow"]
    for o in doc.pop("_overflow", None) or []:
        path = o["path"]
        if parts is not None and path[0] not in parts:
            continue
        chunks = overflow.find({"doc": doc["_id"], "path": path}).sort("start", 1)
        parent = doc.setdefault(path[0], {}) if len(path) > 1 else doc
        parent[path[-1]] = [it for c in chunks for it in c["items"]]
    return doc


def get(coll, _id, parts, exclude=()):
    """The document without its parts and the ``exclude`` fields, plus ``_totals`` (items in each part)."""
    totals = {p: map_size("$" + p) if p in MAPS else size("$" + p) for p in parts}
    pipeline = [{"$match": {"_id": _id}},
                {"$addFields": {"_totals": totals}},
                {"$project": {k: 0 for k in ("_id",) + tuple(parts) + tuple(exclude)}}]
    doc = next(coll.aggregate(pipeline), None)
    for o in (doc or {}).pop("_overflow", None) or []:
        doc["_totals"][o["path"][0]] += o["total"]
    return doc


def part(coll, _id, name, skip, limit):
    """Items [skip, skip + limit) of the part ``name`` and its total; None if the document does not exist.

    Items come as (section title or None, index in its list, item).
    """
    if name in MAPS:
        doc = coll.find_one({"_id": _id}, {name: 1, "_overflow": 1})
        if doc is None:
            return None
        restore(coll, doc, (name,))
        flat = [(title, i, item) for title, items in (doc.get(name) or {}).items() for i, item in enumerate(items or [])]
        return flat[skip:skip + limit], len(flat)
    array = {"$cond": [{"$isArray": "$" + name}, "$" + name, []]}
    pipeline = [{"$match": {"_id": _id}},
                {"$project": {"total": size("$" + name), "items": {"$slice": [array, skip, limit]}, "_overflow": 1}}]
    doc = next(coll.aggregate(pipeline), None)
    if doc is None:
        return None
    if any(o["path"] == [name] for o in doc.get("_overflow") or []):
        items = restore(coll, {"_id": _id, "_overflow": doc["_overflow"]}, (name,))[name]
        doc = {"total": len(items), "items": items[skip:skip + limit]}
    return [(None, skip + i, item) for i, item in enumerate(doc["items"])], doc["total"]


def part_body(id_key, _id, name, window):
    """JSON document of a page of a part; lists by section title are grouped by title."""
    if name not in MAPS:
        return {id_key: _id, name: [item for _, _, item in window]}
    sections = {}
    for title, _, item in window:
        sections.setdefault(title, []).append(item)
    return {id_key: _id, name: sections}


def jsonld(to_jsonld, doc, base, name=None, window=()):
    """JSON-LD view made by the parser's ``to_jsonld``; for a page, items get the @id of their place in the
    whole document (``<IRI>#/works/120``), so the pages merge into the same graph as the document."""
    ld = to_jsonld(doc, base=base)
    ld["@context"].update({k: None for k in API_KEYS})
    if name:
        items = [it for its in ld[name].values() for it in its] if name in MAPS else ld[name]
        for (title, i, _), item in zip(window, items):
            if isinstance(item, dict) and "@id" in item:
                item["@id"] = ld["@id"] + (pointer(name, title, i) if title is not None else pointer(name, i))
    return ld


def parser(coll):
    """Parser of the collection, for the catalog."""
    p = (coll.find_one({}, {"_provenance.parser": 1}) or {}).get("_provenance", {}).get("parser", {})
    return {k: p.get(k) for k in ("name", "version", "commit")}
