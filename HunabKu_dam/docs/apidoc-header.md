## Colav dam API

Collections of the `dam` database as JSON and JSON-LD. Routes tell the stage of the data:

* **scraped**: what was taken from the CvLAC and GrupLAC pages, converted to JSON by a parser
  (CvLAC: [cvlac-json](https://github.com/restrepo/cvlac-json); GrupLAC: Yuku).
* **normalized**: entities built by Yuku from the scraped records (projects, persons).

`/dam/catalog` tells which collection, and which parser version, is behind each route.

### Authentication
Every endpoint needs the apikey, preferably in the `X-API-Key` header (it stays out of URLs and logs):

```
curl -H "X-API-Key: XXXX" https://api.dam.colav.co/dam/catalog
```

### Formats
`?format=json` (default) or `?format=jsonld`, or the header `Accept: application/ld+json`.
The JSON-LD view is the same document plus `@context`, `@id` and `@type`; its vocabularies:
[CvLAC](https://github.com/fedevergara/cvlac-json/blob/feature/dam-integration/docs/cvlac_json_esquema.md),
[GrupLAC](https://github.com/fedevergara/HunabKu_plugins/blob/feature/dam-plugin/HunabKu_dam/docs/gruplac.md),
[normalized entities](https://github.com/fedevergara/HunabKu_plugins/blob/feature/dam-plugin/HunabKu_dam/docs/normalized.md).

### Pages
Long lists (works of a profile, production and members of a group) are served by pages: the document
gives their totals and URLs under `parts`, and each page gives `prev` and `next`.

### Not served
Sex, marital status, birthplace and birthdate of persons, and the e-mail of groups.

### Dumps
`/dam/dumps` lists whole copies of each route (`.jsonld.gz`, with SHA-256), to download all at once.
