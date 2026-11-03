"""GrupLAC groups converted with gruplac-json: MongoDB queries and JSON-LD views (see common)."""
from gruplac_json import to_jsonld
from hunabku_dam import common

ID = "col"
PARTS = ("members", "works", "projects", "events", "other_products")
EXCLUDE = ()  # fields that are not served


def get(coll, col):
    """The group without PARTS, plus ``_totals``; None if it does not exist."""
    return common.get(coll, col, PARTS, EXCLUDE)


part = common.part
parser = common.parser


def part_body(name, col, window):
    return common.part_body(ID, col, name, window)


def jsonld(doc, base, name=None, window=()):
    return common.jsonld(to_jsonld, doc, base, name, window)
