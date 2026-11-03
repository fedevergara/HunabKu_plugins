## Colav dam API

Collections of the `dam` database as JSON and JSON-LD. Routes tell the stage of the data:

* **scraped**: what was taken from the CvLAC and GrupLAC pages, converted to JSON by a parser
  (CvLAC: [cvlac-json](https://github.com/restrepo/cvlac-json); GrupLAC: [gruplac-json](https://github.com/restrepo/gruplac-json)).
* **normalized**: entities built by Yuku from the scraped records (projects, persons).

`/dam/catalog` tells which collection, and which parser version, is behind each route.

### Access
The API is open:

```
curl https://api.dam.colav.co/dam/catalog
```

### Formats
`?format=json` (default) or `?format=jsonld`, or the header `Accept: application/ld+json`.
The JSON-LD view is the same document plus `@context`, `@id` and `@type`; its vocabularies:
[CvLAC](https://github.com/restrepo/cvlac-json/blob/main/docs/cvlac_json_esquema.md),
[GrupLAC](https://github.com/restrepo/gruplac-json/blob/main/docs/gruplac_json_esquema.md),
[normalized entities](https://github.com/fedevergara/HunabKu_plugins/blob/feature/dam-plugin/HunabKu_dam/docs/normalized.md).

### Pages
Long lists (works, projects, events, other products of a profile or a group, members of a group) are served by
pages: the document gives their totals and URLs under `parts`, and each page gives `prev` and `next`.

### Personal data
Documents are served as stored, with the personal data published in CvLAC, GrupLAC and the open data of
Minciencias: sex and birthplace of persons, e-mail of groups.

### Dumps
`/dam/dumps` lists whole copies of each route (`.jsonld.gz`, with SHA-256), to download all at once.
