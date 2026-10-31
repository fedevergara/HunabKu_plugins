<center><img src="https://raw.githubusercontent.com/colav/colav.github.io/master/img/Logo.png"/></center>

# HunabKu dam
Hunabku plugin to serve collections of the `dam` database as JSON and JSON-LD.

Routes tell the stage of the data, not the collection version: `/dam/catalog` says which collection is behind
each route. Each route reads only its own collection.

| Route | Collection (config param) | Content |
|---|---|---|
| `/dam/catalog` | | Routes, collections, number of documents and parser |
| `/dam/scraped/cvlac/{cod_rh}` | `scraped_cvlac` | CvLAC profile converted by [cvlac-json](https://github.com/restrepo/cvlac-json) from the scraped page, without its long lists |
| `/dam/scraped/cvlac/{cod_rh}/{part}` | `scraped_cvlac` | One page of `works`, `projects`, `events`, `awards` or `sections` (`page`, `size`) |
| `/dam/scraped/gruplac/{group_code}` | `scraped_gruplac` | GrupLAC group converted by Yuku from the scraped page, without members and production |
| `/dam/scraped/gruplac/{group_code}/{part}` | `scraped_gruplac` | One page of `members` or `production` (`page`, `size`) |

* **Formats**: `?format=json` (default) or `?format=jsonld`, or the `Accept: application/ld+json` header.
  The JSON-LD view is the one of `cvlac_json.to_jsonld`: the same document plus `@context`, `@id` and `@type`.
  In a page, each item keeps the `@id` it has in the whole profile (`.../dam/scraped/cvlac/0000000639#/works/120`).
  GrupLAC uses the same terms where the keys mean the same, and [its vocabulary](docs/gruplac.md) otherwise.
* **Provenance**: `_provenance.source` (scraped page: collection, URL, date, SHA-256), `_provenance.parser`
  (name, version, commit and options of the parser) and, for GrupLAC, `_provenance.bibliographic_transformation`.
* **Not served**: sex (CvLAC), e-mail of the group (GrupLAC).

# Authentication
The server has to be started with `HUNABKU_APIKEY`; with Hunabku's default apikey the `/dam` endpoints answer 503.
The apikey goes in the `X-API-Key` header (recommended: it stays out of URLs and logs) or in the `apikey` parameter.

```sh
curl -H "X-API-Key: XXXX" http://localhost:8080/dam/scraped/cvlac/0000000639
curl -H "X-API-Key: XXXX" "http://localhost:8080/dam/scraped/cvlac/0000000639/works?page=2&size=50&format=jsonld"
```

# Production
`hunabku_server` starts Flask's development server with `debug=True`: do not expose it. Serve the app with a
WSGI server instead, e.g. with this `wsgi.py` next to `config.py`:

```py
import importlib.machinery, importlib.util, os
from hunabku.Hunabku import Hunabku

loader = importlib.machinery.SourceFileLoader("config", "config.py")
module = importlib.util.module_from_spec(importlib.util.spec_from_loader(loader.name, loader))
loader.exec_module(module)
# config.py keeps the apikey it was generated with: take it from the environment
module.config.apikey = os.environ["HUNABKU_APIKEY"]
server = Hunabku(module.config)
server.apidoc_setup()
server.load_plugins()
server.generate_doc()
app = server.app
```

```sh
HUNABKU_APIKEY=XXXX gunicorn -w 4 -b 127.0.0.1:8080 wsgi:app
```

Install the plugin without `pip install -e` (or with `--config-settings editable_mode=compat`): Hunabku finds
plugins with `pkgutil.iter_modules`, which does not see the default editable installs.

# Config
```py
config.hunabku_dam.Dam.Dam.db_uri = "mongodb://localhost:27017/"
config.hunabku_dam.Dam.Dam.db_name = "dam"
config.hunabku_dam.Dam.Dam.public_url = "https://apis.colav.co"  # base of links and JSON-LD @id; empty: the request URL
config.hunabku_dam.Dam.Dam.scraped_cvlac = "cvlac_json_f104110_20260823"
config.hunabku_dam.Dam.Dam.scraped_gruplac = "gruplac_related_works_reconciled_minciencias_catalog_20261017"
config.hunabku_dam.Dam.Dam.page_size = 100
config.hunabku_dam.Dam.Dam.max_page_size = 500
```

Requires `cvlac-json` with `to_jsonld` (after 0.4.0), which needs Python >= 3.10.
