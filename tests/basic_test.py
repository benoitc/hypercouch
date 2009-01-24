"""\
Copyright (c) 2009 Paul J. Davis <paul.joseph.davis@gmail.com>
This file is part of hypercouch which is released uner the MIT license.
"""
import time
import unittest
import couchdb

COUCHURI = "http://127.0.0.1:5984/"
TESTDB = "hyper_tests"

class BasicTest(unittest.TestCase):
    def setUp(self):
        self.srv = couchdb.Server(COUCHURI)
        if TESTDB in self.srv:
            del self.srv[TESTDB]
        self.db = self.srv.create(TESTDB)
        self.db["_design/tests"] = {"ft_index": "function(doc) {if(doc.body) index(doc.body);}"}
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

    def test_no_records(self):
        data = self._query(q="*.**")
        self.assertEqual(len(data["rows"]), 0)

    def test_add_docs(self):
        docs = [{"_id": str(i), "body": "This is document %d" % i} for i in range(10)]
        self.db.update(docs)
        self._wait(expect=10)
        data = self._query(q="document")
        self.assertEqual(len(data["rows"]), 10)

    def test_rem_docs(self):
        docs = [{"_id": str(i), "body": "This is document %d" % i} for i in range(10)]
        self.db.update(docs)
        self._wait(expect=10)
        del self.db["_design/tests"]
        self._wait(expect=0)

    def test_limit_skip(self):
        docs = [{"_id": str(i), "body": "This is document %d" % i} for i in range(10)]
        self.db.update(docs)
        self._wait(expect=10)
        
        data = self._query(q="*.**", order="@uri STRA")
        self.assertEqual(len(data["rows"]), 10)

        # Limit
        lim = self._query(q="*.**", limit=2, order="@uri STRA")
        self.assertEqual(len(lim["rows"]), 2)
        self.assertEqual(lim["rows"], data["rows"][:2])
        
        # Skip
        skip = self._query(q="*.**", skip=2, order="@uri STRA")
        self.assertEqual(len(skip["rows"]), 8)
        self.assertEqual(skip["rows"], data["rows"][2:])
        
        # Combined
        limskip = self._query(q="*.**", limit=5, skip=3, order="@uri STRA")
        self.assertEqual(len(limskip["rows"]), 5)
        self.assertEqual(limskip["rows"], data["rows"][3:8])

        # There was weirdness when not using an order
        limskip = self._query(q="*.**", limit=3, skip=5, order="@uri STRA")
        self.assertEqual(len(limskip["rows"]), 3)
        self.assertEqual(limskip["rows"], data["rows"][5:8])
