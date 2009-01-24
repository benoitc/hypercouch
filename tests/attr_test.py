"""\
Copyright (c) 2009 Paul J. Davis <paul.joseph.davis@gmail.com>
This file is part of hypercouch which is released uner the MIT license.
"""
import time
import unittest
import couchdb

COUCHURI = "http://127.0.0.1:5984/"
TESTDB = "hyper_tests"

class AttrTest(unittest.TestCase):
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

    def test_attr(self):
        docs = [{"_id": str(i), "body": "This is document %d" % i, "foo": i, "bar": str(i*i)} for i in range(10)]
        self.db.update(docs)
        self._wait(expect=10)
       
        data = self._query(q="document", foo="NUMEQ 3")
        self.assertEqual(data["total_rows"], 1)
        self.assertEqual(data["rows"][0]["id"], "3")

        data = self._query(q="document", foo="NUMBT 2 4", order="foo NUMA")
        self.assertEqual(data["total_rows"], 3)
        for i in range(2,5):
            self.assertEqual(data["rows"][i-2]["id"], str(i))
        
        data = self._query(q="document", bar="STREW 0")
        self.assertEqual(data["total_rows"], 1)
        self.assertEqual(data["rows"][0]["id"], "0")

        data = self._query(q="*.**", foo="NUMLE 4", bar="NUMGE 9", order="bar NUMD")
        self.assertEqual(data["total_rows"], 2)
        self.assertEqual(data["rows"][0]["id"], "4")
        self.assertEqual(data["rows"][1]["id"], "3")
