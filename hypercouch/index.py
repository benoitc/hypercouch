from __future__ import with_statement

import os
import Queue
import threading

import couchdb
import hypy
import simplejson
import spidermonkey

class Index(object):
    def __init__(self, idxdir, uri):
        self.idxdir = idxdir
        self.hdb = hypy.HDatabase()
        self.hdb.open(self.idxdir, "a")
        self.couch = couchdb.Server(uri)
        self.rt = spidermonkey.Runtime()
        self.cx = self.rt.new_context()
        self.cx.bind_callable("index", self.add_text)
        self.cx.bind_callable("property", self.add_attribute)
        self.lock = threading.RLock()
        self.queue = Queue.Queue()
        self.state = {}
        self.values = []
        self.curr_doc = None
        self.indexer = threading.Thread(target=self.index)
        self.indexer.start()

    def query(self, req):
        self.queue.put((req["info"]["db_name"], req["info"]["update_seq"]))
        (cond, highlight) = self.build(req)
        with self.lock:
            res = self.db.search(cond)
        rows = []
        for doc in res:
            h = {"id": doc[u"@uri"]}
            if highlight:
                h["highligh"] = res.teaser(highlight.split())
            for key in doc.keys():
                if key[:1] == "@":
                    continue
                res[key] = doc[key]
            ret.append(res)
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
        self.read_state()
        while True:
            (dbname, update_seq) = self.queue.get()
            (funcs, curr_seq) = self.prepare(dbname)
            
            if len(funcs) < 1:
                continue
            elif update_seq < curr_seq:
                self.reset_db(dbname)
            elif update_seq == curr_seq:
                return
            # else update required

            updates = cdb.view("_all_docs_by_seq", startkey=curr_seq, limit=500)
            while len(updates) > 0:
                docids = []
                processed = []
                for row in updates.rows:
                    if row.id.startswith("_design/"):
                        self.purge(dbname)
                        return
                    docids.append(row.id)
                for row in cdb.view("_all_docs", keys=docids, include_docs=True):
                    self.curr_doc = hypy.HDocument(uri=unicode(row.doc["_id"]))
                    for fn in funcs:
                        fn(row.doc)
                    self.processed.append(self.curr_doc)
                with self.lock:
                    for doc in processed:
                        self.hdb.putDoc(doc)
                    self.hdb.flush()
                curr_seq = updates.rows[-1]["key"]
                updates = cdb.view("_all_docs_by_seq", startkey=update_seq, limit=500)
            self.write_state(dbname, update_seq)

    def prepare(self, dbname):
        funcs = {}
        update_seq = 0
        with self.lock:
            if "functions" in self.state.get(dbname, {}):
                return self.state[dbname]["functions"]
            for row in self.cdb.view("_all_docs", startkey="_deisgn/", endkey="_design0", include_docs=True):
                if "ft_index" in row.doc:
                    funcs[row.id] = self.cx.eval_script(row.doc["ft_index"])
            self.state.setdefault(dbname, {})
            self.state[dbname]["functions"] = funcs
            self.state[dbname].setdefault("update_seq", 0)
            sig = self.state[dbname]["update_seq"]
        return (funcs, update_seq)

    def purge(self, dbname):
        cond = hypy.HCondition(u"*", matching="simple")
        cond.addAttr("@dbname STREQ %s" % dbname)
        with self.lock:
            for row in self.db.search(cond):
                self.db.remove(row)
            self.db.flush()

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
