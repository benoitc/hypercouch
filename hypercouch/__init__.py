"""\
Copyright (c) 2009 Paul J. Davis <paul.joseph.davis@gmail.com>
This file is part of hypercouch which is released uner the MIT license.
"""

from __future__ import with_statement

import optparse as op
import os
import sys

#python 2.6
try:
    import simplejson as json
except ImportError:
    import json

import hypercouch.index

def options():
    return [
        op.make_option("-d", "--dir", dest="dir", default="/tmp/hypercouch",
            help = "Directory to store databases in. [%default]"),
        op.make_option("-u", "--uri", dest="uri", default="http://127.0.0.1:5984",
            help = "CouchDB Server URI [%default]"),
    ]

def requests():
    line = sys.stdin.readline()
    while line:
        #sys.stderr.write("%s\n\n" % line.strip())
        yield json.loads(line)
        line = sys.stdin.readline()

def main():
    parser = op.OptionParser(usage="usage: %prog [OPTIONS]", option_list=options())
    opts, args = parser.parse_args()
    if len(args) > 0:
        print "Unknown arguments: %s" % ' '.join(args)
        parser.print_help()
        exit(-1)
    idx = hypercouch.index.Index(opts.dir, opts.uri)
    try:
        for req in requests():
            try: 
                resp = idx.query(req)
            except Exception, inst:
                resp = {"code": 500, "body": str(inst)}
            sys.stdout.write("%s\n" % json.dumps(resp))
            sys.stdout.flush()
    finally:
        idx.close()
        os._exit(-1)

if __name__ == '__main__':
    main()
