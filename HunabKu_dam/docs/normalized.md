# Normalized entities vocabulary

Terms of the JSON-LD view of `/dam/normalized/projects` and `/dam/normalized/person`. The documents are the
ones written by Yuku (`minciencias_<entity>_vNN` collections, Kahi schema); terms not listed here use
schema.org or PROV-O (see the `@context` of each response). Dates as integers are Unix timestamps.

| Term | Meaning |
|---|---|
| titles | Titles: `title`, `lang`, `source` |
| updated | Last update by source: `source`, `time` |
| types | Types of the entity by source: `type`, `level`, `parent` |
| external_ids | Ids of the entity in other sources: `provenance`, `source`, `id` |
| external_urls | URLs of the entity in other sources |
| date_init, date_end, year_init, year_end | Start and end of a project |
| author_count, authors | Authors of a project (`id` is the CvLAC id); in JSON-LD each one is `/dam/normalized/person/<id>` |
| groups, ranking | Groups of a project; rankings of a project or person (`rank`, `date`, `source`) |
| source_metadata | How Yuku built the entity: versions of the schema and the normalizer, `identity_key` and `identity_rule` (how the records were merged), `occurrences` (the scraped records it was built from: `source_kind`, `source_id`, `record_index`, `metadata`) and `entity_graph` |
| initials, aliases | Initials and other forms of the name of a person |
| affiliations | Affiliations of a person: `id`, `name`, `types`, `start_date`, `end_date`, `position` |
| degrees | Academic degrees of a person |
| subjects, citations_count, products_count | Subjects, citations and number of products of a person |
| related_works | Works of a person: `source`, `id` (e.g. a DOI URL), `author_count` |

Not served: sex, marital status, birthplace and birthdate of a person.
