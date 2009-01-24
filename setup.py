import ez_setup
ez_setup.use_setuptools()
from setuptools import setup, find_packages

setup(
    name = "hypercouch",
    version = "0.1",
    license = "MIT",
    author = "Paul J. Davis",
    author_email = "paul.joseph.davis@gmail.com",
    description = "Full Text Indexing for CouchDB",
    url = "http://github.com/davisp/hypercouch",
    zip_safe = True,

    classifiers = [
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Topic :: Database :: Front-Ends',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'Topic :: Internet :: WWW/HTTP :: Indexing/Search',
    ],

    packages = find_packages(),

    setup_requires = [
        'setuptools>=0.6c8'
    ],

    install_requires = [
        'couchdb', 
        'Hypy',
        'spidermonkey',
    ],
)
