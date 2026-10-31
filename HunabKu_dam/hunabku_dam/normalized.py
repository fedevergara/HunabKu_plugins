"""Normalized entities (minciencias_<entity>_vNN collections): MongoDB queries and JSON-LD views.

Documents are small (hundreds of KB at most), so they are served whole. The JSON-LD view is the same
document plus @context, @id and @type, and links made only from ids that are already in the document:

- authors of a project -> ``/dam/normalized/person/<id>``
- a project ``prov:wasDerivedFrom`` the scraped documents it was built from (``source_metadata.occurrences``
  of kind cvlac or gruplac) -> ``/dam/scraped/<kind>/<source_id>``, at document level, because the
  index of a record in its document depends on the parser.
"""
VOCAB = "https://github.com/colav/HunabKu_plugins/blob/main/HunabKu_dam/docs/normalized.md#"
EXCLUDE = {
    "projects": (),
    "person": ("sex", "marital_status", "birthplace", "birthdate"),  # personal data that is not served
}
TYPES = {"projects": "schema:ResearchProject", "person": "schema:Person"}
SCRAPED_KINDS = ("cvlac", "gruplac")
TERMS = {
    "title": "schema:name",
    "full_name": "schema:name",
    "first_names": "schema:givenName",
    "last_names": "schema:familyName",
    "abstract": "schema:abstract",
    "keywords": "schema:keywords",
    "lang": "schema:inLanguage",
    "url": {"@id": "schema:url", "@type": "@id"},
    "authors": {"@id": "schema:author", "@container": "@list"},
}


def get(coll, entity, _id):
    projection = {k: 0 for k in EXCLUDE[entity]}
    return coll.find_one({"_id": _id}, projection or None)


def jsonld(doc, entity, root):
    """``root`` is the base URL of the service, e.g. https://apis.colav.co."""
    ctx = {"@version": 1.1, "@vocab": VOCAB, "schema": "https://schema.org/",
           "prov": "http://www.w3.org/ns/prov#", "xsd": "http://www.w3.org/2001/XMLSchema#", **TERMS}
    ld = {"@context": ctx, "@id": f"{root}/dam/normalized/{entity}/{doc['_id']}", "@type": TYPES[entity], **doc}
    authors = ld.get("authors") if entity == "projects" else None
    for author in authors or []:
        if isinstance(author, dict) and author.get("id"):
            author["@id"] = f"{root}/dam/normalized/person/{author['id']}"
    sources = []
    for occ in (ld.get("source_metadata") or {}).get("occurrences") or []:
        iri = f"{root}/dam/scraped/{occ.get('source_kind')}/{occ.get('source_id')}"
        if occ.get("source_kind") in SCRAPED_KINDS and occ.get("source_id") and iri not in sources:
            sources.append(iri)
    if sources:
        ld["prov:wasDerivedFrom"] = [{"@id": iri} for iri in sources]
    return ld
