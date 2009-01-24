"""\
Copyright (c) 2009 Paul J. Davis <paul.joseph.davis@gmail.com>
This file is part of hypercouch which is released uner the MIT license.
"""

from __future__ import with_statement

import os
import Queue
import sys
import threading
import traceback
import urllib

import couchdb
import hypy
import spidermonkey

try:
    import simplejson as json
except ImportError:
    import json

class PurgeIndexRequired(Exception):
    def __init__(self, dbname, mesg):
        self.dbname = dbname
        self.mesg = mesg

class Index(object):
    def __init__(self, idxdir, uri):
        self.idxdir = idxdir
        if not os.path.exists(idxdir):
            os.mkdir(idxdir)
        self.hdb = hypy.HDatabase()
        self.hdb.open(self.idxdir, "a")
        self.couch = couchdb.Server(uri)
        self.rt = spidermonkey.Runtime()
        self.cx = self.rt.new_context()
        self.cx.bind_callable("index", self.add_text)
        self.cx.bind_callable("property", self.add_attribute)
        self.lock = threading.RLock()
        self.comitted = False
        self.closing = False
        self.queue = Queue.Queue()
        self.state = {}
        self.values = []
        self.curr_doc = None
        self.indexer = threading.Thread(target=self.index)
        self.indexer.setDaemon(False)
        self.indexer.start()

    def close(self):
        with self.lock:
            self.closing = True
            self.hdb.close()
        self.indexer.join(5)

    def query(self, req):
        dbname = req["info"]["db_name"]
        self.queue.put((dbname, req["info"]["update_seq"]))
        (cond, highlight) = self.build(dbname, req["query"])
        with self.lock:
            if self.comitted:
                self.hdb.open(self.idxdir, "a")
                self.comitted = False
            res = self.hdb.search(cond)
        rows = []
        for doc in res:
            h = {"id": doc[u"@docid"]}
            if highlight:
                h["highlight"] = doc.teaser(res.hintWords(), highlight)
            for key in doc.keys():
                if key[:1] == "@":
                    continue
                h[key] = doc[key]
            rows.append(h)
        return {"code": 200, "json": {"total_rows": res._cresult.doc_num(), "rows": rows}}

    def build(self, dbname, req):
        # Known parameters
        query = unicode(req.get("q", "*.**"))
        matching = req.get("matching", "simple")
        limit = int(req.get("limit", 25))
        skip = int(req.get("skip", 0))
        order = unicode(req.get("order", ""))
        highlight = req.get("highlight", "")
        
        # Unclear on the specifics
        if matching not in ["simple", "rough", "union", "isect"]:
            matching = "simple"

        # Only supports html format so far.
        if highlight not in ["html"]:
            highlight = []

        # Build params
        ret = hypy.HCondition(query, matching="simple", max=limit, skip=skip)

        # Enforce this DB only.
        ret.addAttr(u"@db STREQ %s" % dbname)

        if order:
            ret.setOrder(order)

        # Add type conditions
        for k, v in req.iteritems():
            if k[:1] == "@" or k in ["q", "limit", "skip", "order", "highlight"]:
                continue
            ret.addAttr(u"%s %s" % (k, v))

        return (ret, highlight)

    def index(self):
        self.read_state()
        while True:
            try:
                with self.lock:
                    if self.closing:
                        return
                try:
                    (dbname, update_seq) = self.queue.get(True, 10)
                except Queue.Empty:
                    continue
                db = self.couch[dbname]
                (funcs, curr_seq) = self.prepare(db, dbname)

                if len(funcs) < 1:
                    continue
                elif update_seq < curr_seq:
                    raise PurgeIndexRequired(dbname, "Invalid update sequence.")
                elif update_seq == curr_seq:
                    continue
                # else update required

                updates = db.view("_all_docs_by_seq", startkey=curr_seq, limit=500)
                while len(updates) > 0:
                    docids = []
                    processed = {}
                    for row in updates.rows:
                        docids.append(row.id)
                    for row in db.view("_all_docs", keys=docids, include_docs=True):
                        if row.id.startswith("_design/"):
                            # Check if we deleted a design doc that had an index function
                            if row.value.get("deleted") and row.id in self.state[dbname]["functions"]:
                                raise PurgeIndexRequired(dbname, "Design document deleted.")
                            elif row.value.get("deleted"):
                                # A design doc we don't care about was deleted.
                                continue
                            # Check that ft_index is the same as we have
                            curr = self.state[dbname]["functions"].get(row.id)
                            if curr != row.doc.get("ft_index"):
                                raise PurgeIndexRequired(dbname, "Design ft_index changed.")
                            # Don't index design docs.
                            continue
                        if row.value.get("deleted"):
                            processed[row.id] = None
                            continue
                        self.curr_doc = hypy.HDocument(uri=self.mk_uri(dbname, row.id))
                        for ddoc, fn in funcs.iteritems():
                            fn(row.doc)
                        self.curr_doc[u"@db"] = unicode(dbname)
                        self.curr_doc[u"@docid"] = unicode(row.id)
                        processed[row.id] = self.curr_doc
                    curr_seq = updates.rows[-1]["key"]
                    with self.lock:
                        if self.closing:
                            return
                        for docid, doc in processed.iteritems():
                            if doc:
                                self.hdb.putDoc(doc)
                            else:
                                self.hdb.remove(uri=self.mk_uri(dbname, docid))
                        self.hdb.flush()
                        self.state[dbname]["update_seq"] = curr_seq
                        self.write_state()
                        self.comitted = True
                    updates = db.view("_all_docs_by_seq", startkey=curr_seq, limit=500)
            except PurgeIndexRequired, inst:
                sys.stderr.write("PURGING '%s': %s\n" % (inst.dbname, inst.mesg))
                self.purge(inst.dbname)
            except couchdb.ResourceNotFound:
                sys.stderr.write("PURGING '%s': Database was deleted.\n" % dbname)
                self.purge(dbname)
            # Indexing thread exiting.
            except Exception, inst:
                sys.stderr.write("Uncaught exception in indexing thread, shutting down forcefully.\n")
                traceback.print_exc()
                os._exit(-1)

    def prepare(self, db, dbname):
        funcs = {}
        update_seq = 0
        if "functions" in self.state.get(dbname, {}):
            for k, v in self.state[dbname]["functions"].iteritems():
                funcs[k] = self.cx.eval_script(v)
            if len(funcs) > 0:
                return (funcs, self.state[dbname]["update_seq"])
        self.state.setdefault(dbname, {})
        self.state[dbname].setdefault("update_seq", 0)
        self.state[dbname].setdefault("functions", {})
        for row in db.view("_all_docs", startkey="_deisgn/", endkey="_design0", include_docs=True):
            if "ft_index" in row.doc:
                self.state[dbname]["functions"][row.id] = row.doc["ft_index"]
                funcs[row.id] = self.cx.eval_script(row.doc["ft_index"])
        sig = self.state[dbname]["update_seq"]
        return (funcs, update_seq)

    def purge(self, dbname):
        cond = hypy.HCondition(u"*.**", matching="simple")
        cond.addAttr(u"@db STREQ %s" % dbname)
        with self.lock:
            res = self.hdb.search(cond)
            for row in res:
                self.hdb.remove(row)
            self.hdb.flush()
            del self.state[dbname]
            self.write_state()

    def read_state(self):
        fname = os.path.join(self.idxdir, "couchdb.state")
        if not os.path.exists(fname):
            return 0
        with open(fname) as handle:
            self.state = json.loads(handle.read())

    def write_state(self):
        fname = os.path.join(self.idxdir, "couchdb.state")
        with open(fname, "w") as handle:
            handle.write("%s" % json.dumps(self.state))

    def mk_uri(self, dbname, docid):
        return u"/%s/%s" % (urllib.quote(dbname), urllib.quote(docid))

    def add_text(self, text):
        self.curr_doc.addText(unicode(text))

    def add_attribute(self, key, value):
        self.curr_doc[unicode(key)] = unicode(value)

if __name__ == '__main__':
    main()
