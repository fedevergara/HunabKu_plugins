"""CvLAC profiles converted with cvlac-json: MongoDB queries and JSON-LD views (see common)."""
from cvlac_json import to_jsonld
from hunabku_dam import common

ID = "cod_rh"
PARTS = ("works", "projects", "events", "awards", "patents", "other_products")
EXCLUDE = ()  # fields that are not served


def get(coll, cod_rh):
    """The profile without PARTS, plus ``_totals``; None if it does not exist."""
    return common.get(coll, cod_rh, PARTS, EXCLUDE)


part = common.part
parser = common.parser


def part_body(name, cod_rh, window):
    return common.part_body(ID, cod_rh, name, window)


def jsonld(doc, base, name=None, window=()):
    return common.jsonld(to_jsonld, doc, base, name, window)
