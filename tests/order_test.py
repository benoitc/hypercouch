"""\
Copyright (c) 2009 Paul J. Davis <paul.joseph.davis@gmail.com>
This file is part of hypercouch which is released uner the MIT license.
"""
import time
import unittest
import couchdb

COUCHURI = "http://127.0.0.1:5984/"
TESTDB = "hyper_tests"

class OrderTest(unittest.TestCase):
    def setUp(self):
        self.srv = couchdb.Server(COUCHURI)
        if TESTDB in self.srv:
            del self.srv[TESTDB]
        self.db = self.srv.create(TESTDB)
        self.db["_design/tests"] = {
            "ft_index": """\
                function(doc) {
                    if(doc.body) index(doc.body);
                    if(doc.foo) property("foo", doc.foo);
                    if(doc.bar) property("bar", doc.bar);
                }
            """
        }
        self._wait()
    def tearDown(self):
        del self.srv[TESTDB]
    def _query(self, **kwargs):
        resp, data = self.db.resource.get("_fti", **kwargs)
        return data
    def _wait(self, expect=0, retries=10):
        data = self._query(q="*.**")
        while retries > 0 and len(data["rows"]) != expect:
            retries -= 1
            time.sleep(0.2)
            data = self._query(q="*.**")
        if retries < 1:
            raise RuntimeError("Failed to find expected index state.")

    def _cmp(self, docids, rows):
        for did, hit in zip(docids, rows):
            self.assertEqual(did, hit["id"])

    def test_order(self):
        docids = [str(i) for i in range(25)]
        docs = [{"_id": str(i), "body": "This is document %d" % i, "foo": i, "bar": str(i*i)} for i in range(25)]
        self.db.update(docs)
        self._wait(expect=25)
      
        docids.sort()
        data = self._query(q="*.**", order="foo STRA")
        self._cmp(docids, data["rows"])
     
        docids.sort(reverse=True)
        data = self._query(q="*.**", order="@uri STRD")
        self._cmp(docids, data["rows"])

        docids.sort(key=int)
        data = self._query(q="*.**", order="foo NUMA")
        self._cmp(docids, data["rows"])

        docids.sort(key=int, reverse=True)
        data = self._query(q="*.**", order="foo NUMD")
        self._cmp(docids, data["rows"])
