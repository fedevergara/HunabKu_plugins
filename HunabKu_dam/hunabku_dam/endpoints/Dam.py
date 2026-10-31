from hunabku.HunabkuBase import HunabkuPluginBase, endpoint
from hunabku.Config import Config, Param
from pymongo import MongoClient
from hunabku_dam import cvlac, gruplac
import datetime
import hmac
import math

DEFAULT_APIKEY = "colavudea"  # Hunabku's apikey when HUNABKU_APIKEY is not set
FORMATS = {"json": "application/json", "jsonld": "application/ld+json"}
# route -> (module with the queries and the JSON-LD view, config param with the collection, source name)
SCRAPED = {"cvlac": (cvlac, "scraped_cvlac", "CvLAC"), "gruplac": (gruplac, "scraped_gruplac", "GrupLAC")}


def _default(o):
    return o.isoformat() if isinstance(o, (datetime.datetime, datetime.date)) else str(o)


class Dam(HunabkuPluginBase):
    config = Config()
    config += Param(db_uri="mongodb://localhost:27017/",
                    doc="MongoDB string connection")
    config += Param(db_name="dam",
                    doc="Database with the collections")
    config += Param(public_url="",
                    doc="Base URL for links and JSON-LD @id, e.g. https://apis.colav.co; empty: the URL of the request")
    config += Param(scraped_cvlac="cvlac_json_f104110_20260823",
                    doc="Collection behind /dam/scraped/cvlac: CvLAC profiles converted with cvlac-json")
    config += Param(scraped_gruplac="gruplac_related_works_reconciled_minciencias_catalog_20261017",
                    doc="Collection behind /dam/scraped/gruplac: GrupLAC groups converted by Yuku")
    config += Param(page_size=100,
                    doc="Default number of items per page")
    config += Param(max_page_size=500,
                    doc="Maximum number of items per page")

    def __init__(self, hunabku):
        super().__init__(hunabku)
        self.db = MongoClient(self.config.db_uri)[self.config.db_name]
        if self.global_config["apikey"] == DEFAULT_APIKEY:
            self.logger.error("hunabku_dam: the server was started without HUNABKU_APIKEY, /dam endpoints answer 503")

    def send(self, data, fmt="json", status=200):
        return self.app.response_class(response=self.json.dumps(data, ensure_ascii=False, default=_default),
                                       status=status, mimetype=FORMATS[fmt])

    def error(self, status, error, message):
        return self.send({"error": error, "message": message}, status=status)

    def check(self, params):
        """Returns (error response or None, format). The apikey comes in the X-API-Key header or the apikey parameter."""
        key = self.global_config["apikey"]
        if key == DEFAULT_APIKEY:
            return self.error(503, "Service Unavailable", "the server was started without HUNABKU_APIKEY"), None
        given = self.request.headers.get("X-API-Key") or self.request.args.get("apikey") or ""
        if not hmac.compare_digest(given.encode(), key.encode()):
            return self.apikey_error(), None
        if not self.valid_parameters(params):
            return self.error(400, "Bad Request", f"valid parameters are {list(params)}"), None
        fmt = self.request.args.get("format")
        if fmt is None:
            best = self.request.accept_mimetypes.best_match(list(FORMATS.values()), default=FORMATS["json"])
            fmt = "jsonld" if best == FORMATS["jsonld"] else "json"
        if fmt not in FORMATS:
            return self.error(400, "Bad Request", f"format must be one of {list(FORMATS)}"), None
        return None, fmt

    def base(self, route):
        return (self.config.public_url or self.request.url_root).rstrip("/") + route

    def format_query(self):
        """Links keep the format when it was asked as a parameter."""
        fmt = self.request.args.get("format")
        return f"format={fmt}&" if fmt else ""

    def serve_doc(self, route, _id):
        """A document of a scraped source without its parts; parts gives their totals and URLs."""
        err, fmt = self.check(("apikey", "format"))
        if err:
            return err
        module, param, source = SCRAPED[route]
        doc = module.get(self.db[self.config[param]], _id)
        if doc is None:
            return self.error(404, "Not Found", f"{source} {_id} not found")
        base = self.base(f"/dam/scraped/{route}/")
        totals, query = doc.pop("_totals"), self.format_query()
        doc["parts"] = {p: {"total": totals[p], "url": f"{base}{_id}/{p}?{query}page=1"} for p in module.PARTS}
        if fmt == "jsonld":
            doc = module.jsonld(doc, base)
        return self.send(doc, fmt)

    def serve_part(self, route, _id, part):
        """One page of a part of a document of a scraped source."""
        err, fmt = self.check(("apikey", "format", "page", "size"))
        if err:
            return err
        module, param, source = SCRAPED[route]
        if part not in module.PARTS:
            return self.error(404, "Not Found", f"part must be one of {list(module.PARTS)}")
        try:
            page = int(self.request.args.get("page", 1))
            size = int(self.request.args.get("size", self.config.page_size))
        except ValueError:
            page = size = 0
        if page < 1 or not 1 <= size <= self.config.max_page_size:
            return self.error(400, "Bad Request", f"page must be >= 1 and size between 1 and {self.config.max_page_size}")
        found = module.part(self.db[self.config[param]], _id, part, (page - 1) * size, size)
        if found is None:
            return self.error(404, "Not Found", f"{source} {_id} not found")
        window, total = found
        pages = max(math.ceil(total / size), 1)
        if page > pages:
            return self.error(404, "Not Found", f"{part} of {_id} has {pages} pages of {size}")
        base = self.base(f"/dam/scraped/{route}/")
        url = f"{base}{_id}/{part}?{self.format_query()}size={size}&page="
        doc = module.part_body(part, _id, window)
        if fmt == "jsonld":
            doc = module.jsonld(doc, base, part, window)
        doc["page"] = {"part": part, "number": page, "size": size, "total": total, "pages": pages,
                       "prev": f"{url}{page - 1}" if page > 1 else None,
                       "next": f"{url}{page + 1}" if page < pages else None}
        return self.send(doc, fmt)

    @endpoint('/dam/catalog', methods=['GET'])
    def catalog(self):
        """
        @api {get} /dam/catalog Catalog
        @apiName Catalog
        @apiGroup Dam
        @apiDescription Routes served by the plugin and the collection of the dam database behind each one.
                        Routes do not carry versions or dates: the collection behind a route can change, this
                        endpoint tells which one is served.

        @apiParam {String} apikey  Credential for authentication (or the X-API-Key header)

        @apiSuccess {Object[]} routes  route, stage, source, collection, documents, parser, parts and formats.

        @apiError (Error 401) msg  The HTTP 401 Unauthorized invalid authentication apikey for the target resource.
        @apiError (Error 503) msg  The server was started without HUNABKU_APIKEY.

        @apiExample {curl} Example usage:
            curl -H "X-API-Key: XXXX" https://apis.colav.co/dam/catalog
        """
        err, _ = self.check(("apikey",))
        if err:
            return err
        routes = []
        for route, (module, param, source) in SCRAPED.items():
            coll = self.db[self.config[param]]
            routes.append({
                "route": f"/dam/scraped/{route}/{{{module.ID}}}",
                "stage": "scraped",
                "source": source,
                "collection": coll.name,
                "documents": coll.estimated_document_count(),
                "parser": module.parser(coll),
                "parts": [f"/dam/scraped/{route}/{{{module.ID}}}/{p}" for p in module.PARTS],
                "formats": list(FORMATS),
            })
        return self.send({"routes": routes})

    @endpoint('/dam/scraped/cvlac/<cod_rh>', methods=['GET'])
    def scraped_cvlac(self, cod_rh):
        """
        @api {get} /dam/scraped/cvlac/:cod_rh CvLAC profile
        @apiName ScrapedCvlac
        @apiGroup Dam
        @apiDescription CvLAC profile as converted by cvlac-json from the scraped page, with the provenance of the
                        page and of the parser. Long lists (works, projects, events, awards, sections) are served
                        by pages: parts gives their totals and URLs. Sex is not served.

        @apiParam {String} cod_rh  CvLAC id, e.g. 0000000639
        @apiParam {String} apikey  Credential for authentication (or the X-API-Key header)
        @apiParam {String} [format]  json (default) or jsonld; also chosen with the Accept header (application/ld+json)

        @apiSuccess {Object}  profile  The cvlac-json document without its long lists, plus parts and _provenance.

        @apiError (Error 401) msg  The HTTP 401 Unauthorized invalid authentication apikey for the target resource.
        @apiError (Error 400) msg  Bad request, unknown parameter or format.
        @apiError (Error 404) msg  Profile not found.

        @apiExample {curl} Example usage:
            curl -H "X-API-Key: XXXX" https://apis.colav.co/dam/scraped/cvlac/0000000639
            curl -H "X-API-Key: XXXX" https://apis.colav.co/dam/scraped/cvlac/0000000639?format=jsonld
        """
        return self.serve_doc("cvlac", cod_rh)

    @endpoint('/dam/scraped/cvlac/<cod_rh>/<part>', methods=['GET'])
    def scraped_cvlac_part(self, cod_rh, part):
        """
        @api {get} /dam/scraped/cvlac/:cod_rh/:part CvLAC profile part
        @apiName ScrapedCvlacPart
        @apiGroup Dam
        @apiDescription One page of a long list of a CvLAC profile. Sections are paged as one list in document
                        order and grouped by title in each page. In JSON-LD each item keeps the @id it has in the
                        whole profile, e.g. .../dam/scraped/cvlac/0000000639#/works/120.

        @apiParam {String} cod_rh  CvLAC id, e.g. 0000000639
        @apiParam {String} part  works, projects, events, awards or sections
        @apiParam {String} apikey  Credential for authentication (or the X-API-Key header)
        @apiParam {Number} [page=1]  Page number
        @apiParam {Number} [size=100]  Items per page, at most max_page_size (500)
        @apiParam {String} [format]  json (default) or jsonld; also chosen with the Accept header (application/ld+json)

        @apiSuccess {Object}  part  cod_rh, the items of the page under the part name and page (number, size, total, pages, prev, next).

        @apiError (Error 401) msg  The HTTP 401 Unauthorized invalid authentication apikey for the target resource.
        @apiError (Error 400) msg  Bad request, unknown parameter, format, page or size.
        @apiError (Error 404) msg  Profile, part or page not found.

        @apiExample {curl} Example usage:
            curl -H "X-API-Key: XXXX" "https://apis.colav.co/dam/scraped/cvlac/0000000639/works?page=2&size=50"
        """
        return self.serve_part("cvlac", cod_rh, part)

    @endpoint('/dam/scraped/gruplac/<group_code>', methods=['GET'])
    def scraped_gruplac(self, group_code):
        """
        @api {get} /dam/scraped/gruplac/:group_code GrupLAC group
        @apiName ScrapedGruplac
        @apiGroup Dam
        @apiDescription GrupLAC group as converted by Yuku from the scraped page; parser, source and
                        bibliographic_transformation are grouped under _provenance. Members and production are
                        served by pages: parts gives their totals and URLs. The e-mail of the group is not served.

        @apiParam {String} group_code  GrupLAC id, e.g. COL0008423
        @apiParam {String} apikey  Credential for authentication (or the X-API-Key header)
        @apiParam {String} [format]  json (default) or jsonld; also chosen with the Accept header (application/ld+json)

        @apiSuccess {Object}  group  The group without members and production, plus parts and _provenance.

        @apiError (Error 401) msg  The HTTP 401 Unauthorized invalid authentication apikey for the target resource.
        @apiError (Error 400) msg  Bad request, unknown parameter or format.
        @apiError (Error 404) msg  Group not found.

        @apiExample {curl} Example usage:
            curl -H "X-API-Key: XXXX" https://apis.colav.co/dam/scraped/gruplac/COL0008423
        """
        return self.serve_doc("gruplac", group_code)

    @endpoint('/dam/scraped/gruplac/<group_code>/<part>', methods=['GET'])
    def scraped_gruplac_part(self, group_code, part):
        """
        @api {get} /dam/scraped/gruplac/:group_code/:part GrupLAC group part
        @apiName ScrapedGruplacPart
        @apiGroup Dam
        @apiDescription One page of the members or the production of a GrupLAC group. In JSON-LD each item keeps
                        the @id of its place in the group, e.g. .../dam/scraped/gruplac/COL0008423#/production/120.

        @apiParam {String} group_code  GrupLAC id, e.g. COL0008423
        @apiParam {String} part  members or production
        @apiParam {String} apikey  Credential for authentication (or the X-API-Key header)
        @apiParam {Number} [page=1]  Page number
        @apiParam {Number} [size=100]  Items per page, at most max_page_size (500)
        @apiParam {String} [format]  json (default) or jsonld; also chosen with the Accept header (application/ld+json)

        @apiSuccess {Object}  part  group_code, the items of the page under the part name and page (number, size, total, pages, prev, next).

        @apiError (Error 401) msg  The HTTP 401 Unauthorized invalid authentication apikey for the target resource.
        @apiError (Error 400) msg  Bad request, unknown parameter, format, page or size.
        @apiError (Error 404) msg  Group, part or page not found.

        @apiExample {curl} Example usage:
            curl -H "X-API-Key: XXXX" "https://apis.colav.co/dam/scraped/gruplac/COL0008423/production?page=2"
        """
        return self.serve_part("gruplac", group_code, part)
