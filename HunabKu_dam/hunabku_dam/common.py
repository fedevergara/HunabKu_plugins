"""MongoDB helpers shared by the sources.

A document is served without its long lists (the parts of the source); each part is served by pages,
read with $slice so a page does not load the whole document.
"""

API_KEYS = ("parts", "page")  # API metadata, left out of the JSON-LD graph


def size(expr):
    """Length of an array expression; 0 when it is missing or not an array."""
    return {"$size": {"$cond": [{"$isArray": expr}, expr, []]}}


def get(coll, _id, parts, exclude=(), add=None):
    """The document without its parts and the ``exclude`` fields, plus ``_totals`` (items in each part).

    ``add`` are extra $addFields (computed from the stored fields before they are excluded).
    """
    totals = {p: size("$" + p) for p in parts}
    pipeline = [{"$match": {"_id": _id}},
                {"$addFields": {"_totals": totals, **(add or {})}},
                {"$project": {k: 0 for k in ("_id",) + tuple(parts) + tuple(exclude)}}]
    return next(coll.aggregate(pipeline), None)


def part(coll, _id, name, skip, limit):
    """Items [skip, skip + limit) of the list ``name`` and its total; None if the document does not exist.

    Items come as (None, index in the list, item); sections of CvLAC use the title instead of None.
    """
    array = {"$cond": [{"$isArray": "$" + name}, "$" + name, []]}
    pipeline = [{"$match": {"_id": _id}},
                {"$project": {"total": size("$" + name), "items": {"$slice": [array, skip, limit]}}}]
    doc = next(coll.aggregate(pipeline), None)
    if doc is None:
        return None
    return [(None, skip + i, item) for i, item in enumerate(doc["items"])], doc["total"]
