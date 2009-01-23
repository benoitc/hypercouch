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

import couchdb
import hypy
import simplejson
import spidermonkey

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
        self.queue.put((req["info"]["db_name"], req["info"]["update_seq"]))
        (cond, highlight) = self.build(req)
        with self.lock:
            if self.comitted:
                self.hdb.open(self.idxdir, "a")
                self.comitted = False
            res = self.hdb.search(cond)
        rows = []
        for doc in res:
            h = {"id": doc[u"@uri"]}
            if highlight:
                h["highligh"] = res.teaser(highlight.split())
            for key in doc.keys():
                if key[:1] == "@":
                    continue
                h[key] = doc[key]
            rows.append(h)
        return {"code": 200, "json": {"rows": rows}}

    def build(self, req):
        # Known parameters
        query = unicode(req.get("q", "*.**"))
        limit = int(req.get("limit", 25))
        skip = int(req.get("skip", 0))
        order = unicode(req.get("order", ""))
        highlight = req.get("highlight", "")
        
        # Build params
        ret = hypy.HCondition(query, matching="simple", max=limit, skip=skip)
        if order:
            ret.setOrder(order)

        # Add type conditions
        for k, v in req.iteritems():
            if k in ["q", "limit", "skip", "order", "highlight"]:
                continue
            ret.addAttr(u"%s %s" % (k, v))

        return (ret, highlight)

    def index(self):
        try:
            self.read_state()
            while True:
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
                    self.purge(dbname)
                    continue
                elif update_seq == curr_seq:
                    continue
                # else update required

                updates = db.view("_all_docs_by_seq", startkey=curr_seq, limit=500)
                while len(updates) > 0:
                    docids = []
                    processed = []
                    for row in updates.rows:
                        docids.append(row.id)
                    for row in db.view("_all_docs", keys=docids, include_docs=True):
                        if row.id.startswith("_design/"):
                            if "ft_indx" not in row.doc:
                                continue
                            if row.id not in funcs or row.doc["ft_index"] != funcs[row.id]:
                                self.purge(dbname)
                            continue
                        self.curr_doc = hypy.HDocument(uri=unicode(row.doc["_id"]))
                        for ddoc, fn in funcs.iteritems():
                            fn(row.doc)
                        processed.append(self.curr_doc)
                    curr_seq = updates.rows[-1]["key"]
                    with self.lock:
                        if self.closing:
                            return
                        for doc in processed:
                            self.hdb.putDoc(doc)
                        self.hdb.flush()
                        self.state[dbname]["update_seq"] = curr_seq
                        self.write_state()
                        self.comitted = True
                    updates = db.view("_all_docs_by_seq", startkey=curr_seq, limit=500)
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
        cond = hypy.HCondition(u"*", matching="simple")
        cond.addAttr(u"@dbname STREQ %s" % dbname)
        for row in self.hdb.search(cond):
            self.hdb.remove(row)
        self.hdb.flush()
        del self.state[dbname]
        self.write_state()

    def read_state(self):
        fname = os.path.join(self.idxdir, "couchdb.state")
        if not os.path.exists(fname):
            return 0
        with open(fname) as handle:
            self.state = simplejson.loads(handle.read())

    def write_state(self):
        fname = os.path.join(self.idxdir, "couchdb.state")
        with open(fname, "w") as handle:
            handle.write("%s" % simplejson.dumps(self.state))

    def add_text(self, text):
        self.curr_doc.addText(unicode(text))

    def add_attribute(self, key, value):
        self.curr_doc[unicode(key)] = unicode(value)

if __name__ == '__main__':
    main()
