HyperCouch
==========

Full text indexing for [CouchDB][couchdb]. (I really mean it this time.)

Requriements
------------

There are a couple dependancies that should hopefully be easy to overcome. I have things working on OS X 10.4 so Linux should be a breeze. Windows installation is left as an exercise to the reader.


1. [CouchDB][couchdb] - Obviously
1. [HyperEstraier][hyper] - Full text indexing goodness
1. [Spidermonkey][spider] - Requirement of CouchDB as well **Might require Spidermonkey 1.7**
1. [hypy][hypy] - Python bindings to HyperEstraier
1. [python-spidermonkey][pyspider] - **My version on github**
1. [hypercouch][hypercouch] - This project?

OpenBSD: 
    $ pkg_add -iv py-simplejson
    $ pkg_add -iv py-httplib2

OS X python modules:

    $ sudo port install py25-simplejson
    $ sudo port install py25-httplib2

Ubuntu:

    $ sudo apt-get install simplejson
    $ sudo apt-get isntall httplib2

And couchdb-python:

    $ svn checkout http://couchdb-python.googlecode.com/svn/trunk/ couchdb-python
    $ cd couchdb-python
    $ sudo python setup.py install

For the moment I haven't performed this installation on Linux. Tomorrow I'll sit down and install on one of my severs but for now I'll just go over the OS X procedure and hope the Linux equivalent isn't too far off.

Installation
------------

I won't go over installing CouchDB because it's pretty well covered on the [wiki][wiki]. If you need help with it check there or hop onto the IRC channel (#couchdb on irc.freenode.net) and ask questions.

Linux People
------------

Make sure you have the python dev stuff installed for building extensions:

    $ sudo apt-get install python2.5-dev

HyperEstraier
-------------

HyperEstraier should probably be in your package manager. On OS X it's merely:

    $ sudo port install libestraier-dev libqdbm-dev

Ubuntu:

    $ sudo apt-get install libestraier-dev

Openbsd:

Install Hyperestraier from sources:
    
    $ pkg_add -iv qdbm
    $ ftp http://hyperestraier.sourceforge.net/hyperestraier-1.4.13.tar.gz
    $ tar xvzf hyperestraier-1.4.13.tar.gz
    $ cd hyperestraier-1.4.13
    $ ./configure && gmake && gmake install


Spidermonkey
------------

Spidermonkey is similar

    $ sudo port install spidermonkey

Ubuntu:

    $ sudo apt-get install libmozjs-dev

OpenBSD:
    
    $ pkg_add -iv spidermonkey

Activation Errors
-----------------

If either of your port commands fails due to activation conflicts, you can just deactivate and then rerun the install to get things right:

    $ sudo port deactivate [package]
    $ sudo port install [package]

Hopefully that was the hard part. The rest of the stuff is just about getting the python bindings installed.

HyPy
----

Get the source here: [http://hypy-source.goonmill.org/archive/tip.tar.gz][hypy-download]

For me hypy was easy to install with the caveat that I had to make a minor tweak to `setup.py` to help it find HyperEstraier installed by `ports`. We just need to add `/opt/local/include` to the list of include directories:

From: (About line 10 in Hypy's setup.py)

    ext = Extension("_estraiernative",
                    ["estraiernative.c"],
                    libraries=["estraier"],
                    include_dirs=["/usr/include/estraier", "/usr/include/qdbm"],
                    )

To:

    ext = Extension("_estraiernative",
                    ["estraiernative.c"],
                    libraries=["estraier"],
                    library_dirs=["/usr/local/lib", "/usr/lib"],
                    include_dirs=["/usr/local/include", "/usr/include/estraier", "/usr/include/qdbm", "/opt/local/include/"],
                    )

Hopefully that builds just dandy for you.

python-spidermonkey
-------------------

I actually had to download and patch this project to allow the execution of JavaScript functions from Python. I'm very unsure of the build stability but hopefully it works without too much effort. For the time being you can either `git clone` it or download the tarball to install. At some point in the near future I'm going to give it a more thorough re-working to make it a real project.

Using git:

    $ git clone git://github.com/davisp/python-spidermonkey.git 
    $ cd python-spidermonkey

No git:

    $ wget http://github.com/davisp/python-spidermonkey/tarball/master
    $ tar -xvzf davisp-python-spidermonkey-${HASH}.tar.gz
    $ cd davisp-python-spidermonkey-${HASH}
    
Installing:

    $ python setup.py build
    $ sudo python setup.py isntall

HyperCouch
----------

Installing HyperCouch should be relatively straight forward. Just `git clone` or download the tarball and install.

Using git:

    $ git clone git://github.com/davisp/hypercouch.git
    $ cd hypercouch

No git:

    $ wget http://github.com/davisp/hypercouch/tarball/master
    $ tar -xvzf davisp-hypercouch-${HASH}.tar.gz
    $ cd davisp-hypercouch-${HASH}

Installing:

    $ sudo python setup.py install

Configuring CouchDB
-------------------

You'll need to edit your `local.ini` or alternatively your `local_dev.ini` if you're a fan of `make dev` like I am.

    [external]
    hyper = /path/to/python -m hypercouch

    [httpd_db_handlers]
    _fti = {couch_httpd_external, handle_external_req, <<"hyper">>}

Alternatively, in your `[external]` section you can use `/path/to/hypercouch/dev.sh` without installing to make dev work easier for when you start submitting bug reports and patches. (This avoids the constant `sudo python setup.py install` running when you change `hypercouch` sources.)

Using HyperCouch
----------------

To use `hypercouch` all you need to do is add a JavaScript function to your `_design/doc`'s in the `ft_index` member. This function has two special JavaScript functions you can call to add indexing info for your document.

1. `index(data)` - adds `data` to the full text index
1. `property(name, value)` - adds properties to the document for use in sorting and limiting results


Example `_design/document`:

    {
        "_id": "_design/foo",
        "_rev": "32498230012",
        "ft_index": "function(doc) {if(doc.body) index(doc.body); if(doc.foo) property("foo", doc.foo);}"
    }

Example URL's:

    $ curl http://127.0.0.1:5984/db_name/_fti?q=term1+term2
    $ curl http://127.0.0.1:5984/db_name/_fti?q=term1+AND+term2

Caveat:

It may take a few seconds before the indexed results become available. There's no guarantee that a document has been indexed as soon as you commit it to the database.

Supports
--------

1. `q` - Requests with arbitrary AND/OR type of boolean logic.
1. `limit` and `skip` parameters - For paging type stuff (Beware when not using a specified sort)
1. `matching` - Specify a HyperEstraier parsing method
1. `order` - Order results by an arbitrary propert. Syntax: `prop_name [STRA|STRD|NUMA|NUMD]`
1. `highlight` - Retrieve a highlighted snipped. Currently only supports an html format via `highlight=html`
1. Other attribute limiting via `attr_name=METHOD param` See [Search Conditions][hypersearching] for specifics.

[couchdb]:http://couchdb.apache.org "CouchDB"
[hyper]:http://hyperestraier.sourceforge.net/ "Hyper Estraier"
[spider]:http://www.mozilla.org/js/spidermonkey/ "Spidermonkey"
[hypy]:http://www.goonmill.org/hypy/ "Hypy"
[hypy-download]:http://hypy-source.goonmill.org/archive/tip.tar.gz "Download Hypy"
[pyspider]:http://github.com/davisp/python-spidermonkey/tree/master "Python Spidermonkey"
[hypercouch]:http://github.com/davisp/python-spidermonkey/tree/master "HyperCouch"
[hypersearching]:http://hyperestraier.sourceforge.net/uguide-en.html#searchcond "Hyper Estraier Searching"
