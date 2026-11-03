from hunabku.HunabkuBase import HunabkuPluginBase, endpoint
from hunabku.Config import Config, Param
from pymongo import MongoClient
from flask import send_from_directory
from hunabku_dam import cvlac, dump, gruplac, normalized
import datetime
import math
import os

FORMATS = {"json": "application/json", "jsonld": "application/ld+json"}
# route -> (module with the queries and the JSON-LD view, config param with the collection, source name)
SCRAPED = {"cvlac": (cvlac, "scraped_cvlac", "CvLAC"), "gruplac": (gruplac, "scraped_gruplac", "GrupLAC")}
# route -> (config param with the collection, name of the id)
NORMALIZED = {"projects": ("normalized_projects", "project_id"), "person": ("normalized_person", "cod_rh")}


def _default(o):
    return o.isoformat() if isinstance(o, (datetime.datetime, datetime.date)) else str(o)


class Dam(HunabkuPluginBase):
    config = Config()
    config += Param(db_uri="mongodb://localhost:27017/",
                    doc="MongoDB string connection")
    config += Param(db_name="dam",
                    doc="Database with the collections")
    config += Param(public_url="",
                    doc="Base URL for links and JSON-LD @id, e.g. https://api.dam.colav.co; empty: the URL of the request")
    config += Param(scraped_cvlac=dump.ROUTES["scraped/cvlac"],
                    doc="Collection behind /dam/scraped/cvlac: CvLAC profiles converted with cvlac-json")
    config += Param(scraped_gruplac=dump.ROUTES["scraped/gruplac"],
                    doc="Collection behind /dam/scraped/gruplac: GrupLAC groups converted with gruplac-json")
    config += Param(normalized_projects=dump.ROUTES["normalized/projects"],
                    doc="Collection behind /dam/normalized/projects: projects normalized by Yuku")
    config += Param(normalized_person=dump.ROUTES["normalized/person"],
                    doc="Collection behind /dam/normalized/person: persons normalized by Yuku")
    config += Param(dumps_dir="",
                    doc="Directory of the dumps made with python -m hunabku_dam.dump; empty: no dumps")
    config += Param(page_size=100,
                    doc="Default number of items per page")
    config += Param(max_page_size=500,
                    doc="Maximum number of items per page")

    def __init__(self, hunabku):
        super().__init__(hunabku)
        self.db = MongoClient(self.config.db_uri)[self.config.db_name]

    def send(self, data, fmt="json", status=200):
        return self.app.response_class(response=self.json.dumps(data, ensure_ascii=False, default=_default),
                                       status=status, mimetype=FORMATS[fmt])

    def error(self, status, error, message):
        return self.send({"error": error, "message": message}, status=status)

    def check(self, params):
        """Returns (error response or None, format). The API is open: an apikey parameter is ignored, so the
        URLs given when it needed one still work."""
        if not self.valid_parameters(tuple(params) + ("apikey",)):
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
        err, fmt = self.check(("format",))
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
        err, fmt = self.check(("format", "page", "size"))
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

    def serve_normalized(self, entity, _id):
        """A normalized entity, whole."""
        err, fmt = self.check(("format",))
        if err:
            return err
        doc = normalized.get(self.db[self.config[NORMALIZED[entity][0]]], entity, _id)
        if doc is None:
            return self.error(404, "Not Found", f"{entity} {_id} not found")
        if fmt == "jsonld":
            doc = normalized.jsonld(doc, entity, self.base(""))
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


        @apiSuccess {Object[]} routes  route, stage, source, collection, documents, parser, parts and formats.


        @apiExample {curl} Example usage:
            curl https://api.dam.colav.co/dam/catalog
        """
        err, _ = self.check(())
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
        for entity, (param, id_name) in NORMALIZED.items():
            coll = self.db[self.config[param]]
            sample = coll.find_one({}, {"source_metadata.schema_version": 1, "source_metadata.normalizer_version": 1})
            meta = (sample or {}).get("source_metadata", {})
            routes.append({
                "route": f"/dam/normalized/{entity}/{{{id_name}}}",
                "stage": "normalized",
                "collection": coll.name,
                "documents": coll.estimated_document_count(),
                "normalizer": {k: meta.get(k) for k in ("schema_version", "normalizer_version")},
                "parts": [],
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
                        page and of the parser. Long lists (works, projects, events, awards, patents,
                        other_products) are served by pages: parts gives their totals and URLs.

        @apiParam {String} cod_rh  CvLAC id, e.g. 0000000639
        @apiParam {String} [format]  json (default) or jsonld; also chosen with the Accept header (application/ld+json)

        @apiSuccess {Object}  profile  The cvlac-json document without its long lists, plus parts and _provenance.

        @apiError (Error 400) msg  Bad request, unknown parameter or format.
        @apiError (Error 404) msg  Profile not found.

        @apiExample {curl} Example usage:
            curl https://api.dam.colav.co/dam/scraped/cvlac/0000000639
            curl https://api.dam.colav.co/dam/scraped/cvlac/0000000639?format=jsonld
        """
        return self.serve_doc("cvlac", cod_rh)

    @endpoint('/dam/scraped/cvlac/<cod_rh>/<part>', methods=['GET'])
    def scraped_cvlac_part(self, cod_rh, part):
        """
        @api {get} /dam/scraped/cvlac/:cod_rh/:part CvLAC profile part
        @apiName ScrapedCvlacPart
        @apiGroup Dam
        @apiDescription One page of a long list of a CvLAC profile. other_products is paged as one list in
                        document order and grouped by section title in each page. In JSON-LD each item keeps the @id it has in the
                        whole profile, e.g. .../dam/scraped/cvlac/0000000639#/works/120.

        @apiParam {String} cod_rh  CvLAC id, e.g. 0000000639
        @apiParam {String} part  works, projects, events, awards, patents or other_products
        @apiParam {Number} [page=1]  Page number
        @apiParam {Number} [size=100]  Items per page, at most max_page_size (500)
        @apiParam {String} [format]  json (default) or jsonld; also chosen with the Accept header (application/ld+json)

        @apiSuccess {Object}  part  cod_rh, the items of the page under the part name and page (number, size, total, pages, prev, next).

        @apiError (Error 400) msg  Bad request, unknown parameter, format, page or size.
        @apiError (Error 404) msg  Profile, part or page not found.

        @apiExample {curl} Example usage:
            curl "https://api.dam.colav.co/dam/scraped/cvlac/0000000639/works?page=2&size=50"
        """
        return self.serve_part("cvlac", cod_rh, part)

    @endpoint('/dam/scraped/gruplac/<group_code>', methods=['GET'])
    def scraped_gruplac(self, group_code):
        """
        @api {get} /dam/scraped/gruplac/:group_code GrupLAC group
        @apiName ScrapedGruplac
        @apiGroup Dam
        @apiDescription GrupLAC group as converted by gruplac-json from the scraped page, with the provenance of
                        the page and of the parser. Long lists (members, works, projects, events, other_products)
                        are served by pages: parts gives their totals and URLs.

        @apiParam {String} group_code  GrupLAC id, e.g. COL0008423
        @apiParam {String} [format]  json (default) or jsonld; also chosen with the Accept header (application/ld+json)

        @apiSuccess {Object}  group  The gruplac-json document without its long lists, plus parts and _provenance.

        @apiError (Error 400) msg  Bad request, unknown parameter or format.
        @apiError (Error 404) msg  Group not found.

        @apiExample {curl} Example usage:
            curl https://api.dam.colav.co/dam/scraped/gruplac/COL0008423
        """
        return self.serve_doc("gruplac", group_code)

    @endpoint('/dam/scraped/gruplac/<group_code>/<part>', methods=['GET'])
    def scraped_gruplac_part(self, group_code, part):
        """
        @api {get} /dam/scraped/gruplac/:group_code/:part GrupLAC group part
        @apiName ScrapedGruplacPart
        @apiGroup Dam
        @apiDescription One page of a long list of a GrupLAC group. other_products is paged as one list in
                        document order and grouped by section title in each page. In JSON-LD each item keeps the @id
                        of its place in the group, e.g. .../dam/scraped/gruplac/COL0008423#/works/120.

        @apiParam {String} group_code  GrupLAC id, e.g. COL0008423
        @apiParam {String} part  members, works, projects, events or other_products
        @apiParam {Number} [page=1]  Page number
        @apiParam {Number} [size=100]  Items per page, at most max_page_size (500)
        @apiParam {String} [format]  json (default) or jsonld; also chosen with the Accept header (application/ld+json)

        @apiSuccess {Object}  part  col, the items of the page under the part name and page (number, size, total, pages, prev, next).

        @apiError (Error 400) msg  Bad request, unknown parameter, format, page or size.
        @apiError (Error 404) msg  Group, part or page not found.

        @apiExample {curl} Example usage:
            curl "https://api.dam.colav.co/dam/scraped/gruplac/COL0008423/works?page=2"
        """
        return self.serve_part("gruplac", group_code, part)

    @endpoint('/dam/normalized/projects/<project_id>', methods=['GET'])
    def normalized_projects(self, project_id):
        """
        @api {get} /dam/normalized/projects/:project_id Normalized project
        @apiName NormalizedProjects
        @apiGroup Dam
        @apiDescription Project normalized by Yuku from the CvLAC and GrupLAC records that describe it
                        (source_metadata.occurrences). In JSON-LD, authors link to /dam/normalized/person/:cod_rh
                        and prov:wasDerivedFrom links to the scraped CvLAC and GrupLAC documents it was built from.

        @apiParam {String} project_id  Project id
        @apiParam {String} [format]  json (default) or jsonld; also chosen with the Accept header (application/ld+json)

        @apiSuccess {Object}  project  The normalized project.

        @apiError (Error 400) msg  Bad request, unknown parameter or format.
        @apiError (Error 404) msg  Project not found.

        @apiExample {curl} Example usage:
            curl https://api.dam.colav.co/dam/normalized/projects/e5a249d9892d4abcc010bdca3274e1644a82eb2201f73b2af5
        """
        return self.serve_normalized("projects", project_id)

    @endpoint('/dam/normalized/person/<cod_rh>', methods=['GET'])
    def normalized_person(self, cod_rh):
        """
        @api {get} /dam/normalized/person/:cod_rh Normalized person
        @apiName NormalizedPerson
        @apiGroup Dam
        @apiDescription Person normalized by Yuku.

        @apiParam {String} cod_rh  CvLAC id, e.g. 0000000639
        @apiParam {String} [format]  json (default) or jsonld; also chosen with the Accept header (application/ld+json)

        @apiSuccess {Object}  person  The normalized person.

        @apiError (Error 400) msg  Bad request, unknown parameter or format.
        @apiError (Error 404) msg  Person not found.

        @apiExample {curl} Example usage:
            curl https://api.dam.colav.co/dam/normalized/person/0000000639?format=jsonld
        """
        return self.serve_normalized("person", cod_rh)

    @endpoint('/dam/dumps', methods=['GET'])
    def dumps(self):
        """
        @api {get} /dam/dumps Dumps
        @apiName Dumps
        @apiGroup Dam
        @apiDescription Whole copies of the routes, one JSON-LD file compressed with gzip per route, made offline
                        with python -m hunabku_dam.dump. Each file is {"@graph": [...]} with the documents as the
                        API serves them in JSON-LD.


        @apiSuccess {Object[]} dumps  name, url, route, collection, documents, bytes, sha256, created_at.


        @apiExample {curl} Example usage:
            curl https://api.dam.colav.co/dam/dumps
        """
        err, _ = self.check(())
        if err:
            return err
        found = dump.manifests(self.config.dumps_dir)
        for m in found:
            m["url"] = self.base("/dam/dumps/" + m["name"])
        return self.send({"dumps": found})

    @endpoint('/dam/dumps/<name>', methods=['GET'])
    def dump_file(self, name):
        """
        @api {get} /dam/dumps/:name Dump file
        @apiName DumpFile
        @apiGroup Dam
        @apiDescription Downloads a dump listed by /dam/dumps (application/gzip). Check it with its sha256.

        @apiParam {String} name  File name, as listed by /dam/dumps

        @apiError (Error 404) msg  Dump not found.

        @apiExample {curl} Example usage:
            curl -o projects.jsonld.gz https://api.dam.colav.co/dam/dumps/normalized_projects__minciencias_projects_v08_20261017.jsonld.gz
        """
        err, _ = self.check(())
        if err:
            return err
        if name not in {m["name"] for m in dump.manifests(self.config.dumps_dir)}:
            return self.error(404, "Not Found", f"dump {name} not found, see /dam/dumps")
        return send_from_directory(os.path.abspath(self.config.dumps_dir), name, mimetype="application/gzip",
                                   as_attachment=True)
