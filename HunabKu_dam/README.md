<center><img src="https://raw.githubusercontent.com/colav/colav.github.io/master/img/Logo.png"/></center>

# HunabKu dam
Hunabku plugin to serve collections of the `dam` database as JSON and JSON-LD.

Routes tell the stage of the data, not the collection version: `/dam/catalog` says which collection is behind
each route. Each route reads only its own collection.

| Route | Collection (config param) | Content |
|---|---|---|
| `/dam/catalog` | | Routes, collections, number of documents and parser |
| `/dam/scraped/cvlac/{cod_rh}` | `scraped_cvlac` | CvLAC profile converted by [cvlac-json](https://github.com/restrepo/cvlac-json) from the scraped page, without its long lists |
| `/dam/scraped/cvlac/{cod_rh}/{part}` | `scraped_cvlac` | One page of `works`, `projects`, `events`, `awards`, `patents` or `other_products` (`page`, `size`) |
| `/dam/scraped/gruplac/{col}` | `scraped_gruplac` | GrupLAC group converted by [gruplac-json](https://github.com/restrepo/gruplac-json) from the scraped page, without its long lists |
| `/dam/scraped/gruplac/{col}/{part}` | `scraped_gruplac` | One page of `members`, `works`, `projects`, `events` or `other_products` (`page`, `size`) |
| `/dam/normalized/projects/{project_id}` | `normalized_projects` | Project normalized by Yuku, whole |
| `/dam/normalized/person/{cod_rh}` | `normalized_person` | Person normalized by Yuku, whole |

* **Pages**: `other_products` (lists by section title) is paged as one list in document order, and each page
  groups its items by title again.
* **Formats**: `?format=json` (default) or `?format=jsonld`, or the `Accept: application/ld+json` header.
  The JSON-LD view is the one of the parser (`cvlac_json.to_jsonld`, `gruplac_json.to_jsonld`): the same document
  plus `@context`, `@id` and `@type`. In a page, each item keeps the `@id` it has in the whole document
  (`.../dam/scraped/cvlac/0000000639#/works/120`). Normalized entities use [their vocabulary](docs/normalized.md).
* **Links** are made only from ids already in each document: the authors of a project are
  `/dam/normalized/person/{cod_rh}`, and a project `prov:wasDerivedFrom` the scraped CvLAC and GrupLAC documents
  in its `source_metadata.occurrences` (document level: the index of a record depends on the parser).
* **Provenance**: `_provenance.source` (scraped page: collection, URL, date, SHA-256) and `_provenance.parser`
  (name, version, commit and options of the parser).
* **Large documents**: a document that did not fit in MongoDB (16 MB) is stored with its largest lists in
  `<collection>_overflow` (`{_id, doc, path, start, items}`, listed in the `_overflow` field of the document); the
  plugin and the dumps put them back.
* **Personal data** is served as stored: sex (CvLAC, normalized person), birthplace (normalized person), e-mail of
  the group (GrupLAC). `EXCLUDE` in each module lists the fields that are not served (none now).

# Access
The `/dam` endpoints are open (an `apikey` parameter is accepted and ignored):

```sh
curl http://localhost:8080/dam/scraped/cvlac/0000000639
curl "http://localhost:8080/dam/scraped/cvlac/0000000639/works?page=2&size=50&format=jsonld"
```

# Dumps
Whole copies of the routes, one `.jsonld.gz` per route (`{"@graph": [...]}` with the documents as the API serves
them in JSON-LD), made offline and served by `/dam/dumps` (list, with SHA-256) and `/dam/dumps/{name}`:

```sh
python -m hunabku_dam.dump --out /data/dam_dumps --public-url https://api.dam.colav.co   # all routes
python -m hunabku_dam.dump --out /data/dam_dumps --public-url https://api.dam.colav.co --route normalized/projects
```

`--public-url` must be the `public_url` of the plugin, so the @id of the dumps and of the API are the same;
set `dumps_dir` to the `--out` directory. A dump is written to a temporary file and renamed when complete.

# Production
`hunabku_server` starts Flask's development server with `debug=True`: do not expose it. Serve the app with a
WSGI server instead, e.g. with this `wsgi.py` next to `config.py`:

```py
import importlib.machinery, importlib.util, shutil
from hunabku.Hunabku import Hunabku

loader = importlib.machinery.SourceFileLoader("config", "config.py")
module = importlib.util.module_from_spec(importlib.util.spec_from_loader(loader.name, loader))
loader.exec_module(module)
server = Hunabku(module.config)
server.apidoc_setup()
server.load_plugins()
if shutil.which("node"):  # apidoc needs node; without it, keep docs generated elsewhere in hunabku_website/static/apidoc
    server.generate_doc()
app = server.app
```

```sh
gunicorn -w 4 -b 127.0.0.1:8080 --preload wsgi:app   # --preload: one apidoc_setup, not one per worker
```

Install the plugin without `pip install -e` (or with `--config-settings editable_mode=compat`): Hunabku finds
plugins with `pkgutil.iter_modules`, which does not see the default editable installs.

# Config
```py
config.hunabku_dam.Dam.Dam.db_uri = "mongodb://localhost:27017/"
config.hunabku_dam.Dam.Dam.db_name = "dam"
config.hunabku_dam.Dam.Dam.public_url = "https://api.dam.colav.co"  # base of links and JSON-LD @id; empty: the request URL
config.hunabku_dam.Dam.Dam.scraped_cvlac = "cvlac_json_f8c70f2_20260823"
config.hunabku_dam.Dam.Dam.scraped_gruplac = "gruplac_json_50594ce_20261017"
config.hunabku_dam.Dam.Dam.normalized_projects = "minciencias_projects_v08_20261017"
config.hunabku_dam.Dam.Dam.normalized_person = "minciencias_person_v04_20261017"
config.hunabku_dam.Dam.Dam.dumps_dir = "/data/dam_dumps"
config.hunabku_dam.Dam.Dam.page_size = 100
config.hunabku_dam.Dam.Dam.max_page_size = 500
```

Requires `cvlac-json` >= 0.7 and `gruplac-json` with `to_jsonld` (after 0.3.0), which need Python >= 3.10.
