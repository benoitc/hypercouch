"""\
Copyright (c) 2009 Paul J. Davis <paul.joseph.davis@gmail.com>
This file is part of hypercouch which is released uner the MIT license.
"""
import time
import unittest
import couchdb

COUCHURI = "http://127.0.0.1:5984/"
TESTDBA = "hyper_tests_a"
TESTDBB = "hyper_tests_b"

class MultiDbTest(unittest.TestCase):
    def setUp(self):
        self.srv = couchdb.Server(COUCHURI)
        if TESTDBA in self.srv:
            del self.srv[TESTDBA]
        if TESTDBB in self.srv:
            del self.srv[TESTDBB]
        self.dba = self.srv.create(TESTDBA)
        self.dbb = self.srv.create(TESTDBB)
        self.dba["_design/tests"] = {
            "ft_index": """\
                function(doc) {
                    if(doc.body) index(doc.body);
                    if(doc.foo) property("foo", doc.foo);
                    if(doc.bar) property("bar", doc.bar);
                }
            """
        }
        doc = self.dba["_design/tests"]
        del doc["_rev"]
        self.dbb["_design/tests"] = doc
        self._wait(self.dba)
        self._wait(self.dbb)
    def tearDown(self):
        del self.srv[TESTDBA]
        del self.srv[TESTDBB]
    def _query(self, db, **kwargs):
        resp, data = db.resource.get("_fti", **kwargs)
        return data
    def _wait(self, db, expect=0, retries=10):
        data = self._query(db, q="*.**")
        while retries > 0 and len(data["rows"]) != expect:
            retries -= 1
            time.sleep(0.2)
            data = self._query(db, q="*.**")
        if retries < 1:
            raise RuntimeError("Failed to find expected index state.")

    def test_multi(self):
        docsa = [{"_id": str(i), "body": "This is document %d" % i, "foo": i} for i in range(10)]
        self.dba.update(docsa)
        self._wait(self.dba, expect=10)
        docsb = [{"_id": str(i), "body": "This is document %d" % i, "bar": i} for i in range(10)]
        self.dbb.update(docsb)
        self._wait(self.dbb, expect=10)

        data = self._query(self.dba, q="*.**")
        self.assertEqual(len(data["rows"]), 10)
        data = self._query(self.dbb, q="*.**")
        self.assertEqual(len(data["rows"]), 10)

        data = self._query(self.dba, q="*.**", bar="NUMGT 0")
        self.assertEqual(len(data["rows"]), 0)

        data = self._query(self.dbb, q="*.**", foo="NUMEQ 5")
        self.assertEqual(len(data["rows"]), 0)
