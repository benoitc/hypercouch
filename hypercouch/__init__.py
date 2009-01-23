from __future__ import with_statement

import optparse as op

import simplejson

import hypercouch.index

def options():
    return [
        op.make_option("-d", "--dir", dest="dir", default="./",
            help = "Directory to store databases in. [%default]"),
        op.make_option("-u", "--uri", dest="uri", default="http://127.0.0.1:5984",
            help = "CouchDB Server URI [%default]"),
    ]

def requests():
    line = sys.stdin.readline()
    while line:
        yield simplejson.loads(line)
        line = sys.stdin.readline()

def main():
    parser = op.OptionParser(usage="usage: %prog [OPTIONS]", option_list=options())
    opts, args = parser.parse_args()
    if len(args) > 0:
        print "Unknown arguments: %s" % ' '.join(args)
        parser.print_help()
        exit(-1)
    idx = hypercouch.index.Index(opts.dir, opts.uri)
    for req in requests():
        idx.query(req)

if __name__ == '__main__':
    main()
