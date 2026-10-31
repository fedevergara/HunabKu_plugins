"""Offline dumps of the dam routes: one ``.jsonld.gz`` per route, served by /dam/dumps.

Each dump is a JSON-LD document ``{"@graph": [...]}`` whose nodes are the documents of the route as the
API serves them in JSON-LD (whole, without pages, without the fields that are not served); each node keeps
its own @context. It is written by streaming, so memory does not grow with the collection, to a temporary
file renamed at the end, next to a manifest ``<dump>.json`` (route, collection, documents, size, SHA-256).

    python -m hunabku_dam.dump --out /data/dam_dumps --public-url https://apis.colav.co [--route scraped/cvlac]
"""
import argparse
import datetime
import gzip
import hashlib
import json
import os
import sys
import time

from pymongo import MongoClient

from hunabku_dam import cvlac, gruplac, normalized

# route -> default collection (the same as the plugin config)
ROUTES = {
    "scraped/cvlac": "cvlac_json_f104110_20260823",
    "scraped/gruplac": "gruplac_related_works_reconciled_minciencias_catalog_20261017",
    "normalized/projects": "minciencias_projects_v08_20261017",
    "normalized/person": "minciencias_person_v04_20261017",
}


def _default(o):
    return o.isoformat() if isinstance(o, (datetime.datetime, datetime.date)) else str(o)


def projection(route):
    if route == "scraped/cvlac":
        return {k: 0 for k in ("_id",) + cvlac.EXCLUDE}
    if route == "scraped/gruplac":
        return {k: 0 for k in ("_id",) + gruplac.EXCLUDE}
    return {k: 0 for k in normalized.EXCLUDE[route.split("/")[1]]} or None


def served(route, doc, root):
    """A whole document of the route as the API serves it in JSON-LD."""
    if route == "scraped/cvlac":
        return cvlac.jsonld(doc, f"{root}/dam/scraped/cvlac/")
    if route == "scraped/gruplac":
        doc["_provenance"] = {k: doc.pop(k) for k in gruplac.PROVENANCE if k in doc}
        return gruplac.jsonld(doc, f"{root}/dam/scraped/gruplac/")
    return normalized.jsonld(doc, route.split("/")[1], root)


def file_name(route, collection):
    return f"{route.replace('/', '_')}__{collection}.jsonld.gz"


def manifests(directory):
    """Manifests of the finished dumps in ``directory``, by route."""
    found = []
    for name in sorted(os.listdir(directory)) if directory and os.path.isdir(directory) else []:
        if name.endswith(".jsonld.gz.json"):
            with open(os.path.join(directory, name)) as fh:
                m = json.load(fh)
            if os.path.exists(os.path.join(directory, m["name"])):
                found.append(m)
    return found


def dump(db, route, collection, out, root, log=print):
    name = file_name(route, collection)
    path, tmp = os.path.join(out, name), os.path.join(out, name + ".tmp")
    coll = db[collection]
    total, started, n = coll.estimated_document_count(), time.time(), 0
    log(f"{route}: {collection} ({total} documents) -> {path}")
    with gzip.open(tmp, "wt", encoding="utf-8", compresslevel=6) as fh:
        fh.write('{"@graph": [\n')
        for doc in coll.find({}, projection(route)).sort("_id", 1).batch_size(500):
            fh.write((",\n" if n else "") + json.dumps(served(route, doc, root), ensure_ascii=False, default=_default))
            n += 1
            if n % 20000 == 0:
                rate = n / (time.time() - started)
                log(f"{route}: {n}/{total} | {rate:.0f}/s | ~{(total - n) / rate / 60:.1f} min left")
        fh.write("\n]}\n")
    sha = hashlib.sha256()
    with open(tmp, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            sha.update(block)
    os.replace(tmp, path)
    manifest = {"name": name, "route": "/dam/" + route, "collection": collection, "documents": n,
                "bytes": os.path.getsize(path), "sha256": sha.hexdigest(), "public_url": root,
                "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat()}
    with open(path + ".json", "w") as fh:
        json.dump(manifest, fh, indent=1)
    log(f"{route}: done, {n} documents, {manifest['bytes'] / 2**20:.0f} MB, {(time.time() - started) / 60:.1f} min")
    return manifest


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", required=True, help="directory of the dumps (config dumps_dir of the plugin)")
    ap.add_argument("--public-url", required=True, help="base URL of the JSON-LD @id, as the plugin public_url")
    ap.add_argument("--route", action="append", choices=list(ROUTES), help="route to dump (repeatable); default all")
    ap.add_argument("--collection", action="append", default=[], metavar="ROUTE=COLLECTION",
                    help="collection of a route, when it is not the default")
    ap.add_argument("--db-uri", default="mongodb://localhost:27017/")
    ap.add_argument("--db-name", default="dam")
    a = ap.parse_args(argv)
    collections = {**ROUTES, **dict(c.split("=", 1) for c in a.collection)}
    os.makedirs(a.out, exist_ok=True)
    db = MongoClient(a.db_uri)[a.db_name]
    log = lambda m: print(f"{datetime.datetime.now():%F %T} {m}", flush=True)  # noqa: E731
    for route in a.route or list(ROUTES):
        dump(db, route, collections[route], a.out, a.public_url.rstrip("/"), log)
    return 0


if __name__ == "__main__":
    sys.exit(main())
