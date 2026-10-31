# GrupLAC vocabulary

Terms of the JSON-LD view of `/dam/scraped/gruplac`. The document is the one written by Yuku
(`yuku.gruplac_related_works`) from the scraped GrupLAC page; terms not listed here use schema.org (see the
`@context` of each response). Page labels (`basic`) keep their Spanish name, percent-encoded in the IRI.

| Term | Meaning |
|---|---|
| GruplacGroup | A research group as shown in GrupLAC |
| nro | Number of the group in the listing it was scraped from |
| basic | Fields of the "Datos básicos" table, by label (the e-mail is not served) |
| institutions | Institutions of the group: `name`, `endorsed` (the institution endorses the group) |
| strategic_plan | Texts of the strategic plan (TXT_PLAN_TRABAJO, TXT_ESTADO_ARTE, TXT_OBJETIVOS, TXT_RETOS, TXT_VISION) |
| research_lines | Research lines |
| members | Members: `cod_rh` (CvLAC id), `full_name`, `role`, `hours` (hours per week), `period` |
| members_count, production_count | Number of members and of products |
| production | Products. Common keys: `product_type` (GrupLAC label), `type_impactu` (type in ImpactU), `title`, `year`, `authors`, `doi`, `issn`, `isbn`, `source_section`, `validated`, `raw_text` (text of the page); other keys depend on the type of product |
| group_status | Download status of the group |
| _provenance | `parser` (Yuku module and version), `source` (scraped page: collection, URL, date, SHA-256) and `bibliographic_transformation` (DOI reconciliation run) |
