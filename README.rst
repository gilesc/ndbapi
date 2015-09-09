===========================================================================
ndbapi - Python API for the Nucleic Acid DB (http://ndbserver.rutgers.edu/)
===========================================================================

`ndbapi` is a Python API for the advanced search interface of the Nucleic Acid
DB (http://ndbserver.rutgers.edu/ndbmodule/search/integrated.html).

Installation
============

ndbapi requires Python 2.6+ or any Python 3 (any version).

.. code-block:: bash

    $ pip install --user git+https://github.com/gilesc/ndbapi.git

Usage
=====

Overall, usage is simple: the user constructs a `ndbapi.Client` object, and
then calls `Client.query(params)`, where `params` is a dictionary of parameters
to be searched upon. There are many possible parameters, and any parameters not
supplied by the user will be left at their defaults. 

The query will return a `Result` object containing the search parameters and
results as if they had been exported to CSV. The main attribute of interest
will be the `Result.data` attribute, which contains a `pandas.DataFrame`
containing the result set. Alternatively, the result can be saved, which will
export the result set with some metadata. For example:

.. code-block:: python

    from ndbapi import Client

    api = Client()
    rs = api.query({"citation_information.PDB_ID.value": "4WLS"})

    # will print top 10 search results (in this case just one)
    print(rs.data.head())

    # saves results to TSV format with search parameters and search time as a header
    rs.save("results.tsv")

Most of the complexity from the API comes from the fact that there are many
options, each with different sets of possible values. To see the full list of
options and allowed values for each, use the `Client.print_options()` function.
The options will be printed in the same order as they appear on the NDB
Advanced Search page, top to bottom and left to right. Keys which have a `None`
as the allowed set of values accept any string (note, however, that these
fields often have a specific meaning, such as PDB ID or a numeric parameter,
constraining the set of strings that will in practice be useful).

Query keys come in the form of `"$category.$item.$attribute"`. A `category`
corresponds to one of the groupings of parameters on the Advanced Search page.
An `item` is one particular input parameter, which may actually have several
input fields, called an `attribute`. The type of attribute determines what
valid values will be allowed. Here are a few:

- `bitop` : the binary operation attached to most fields on the query form (accepts "AND" or "OR")
- `nop` : numeric operation : ("gtEq", "ltEq", "eq")
- `value` : the selected button of a radio button selection (e.g., "Y"/"N"/"Ignore", "EITHER"/"RNA"/"DNA") or a free-text field
- `choice` : the choice from a single-choice selection box
- `choices` : a list of choices from a multiple-choice selection box
- `minimum`, `maximum`, and `cutoff` - numeric fields (accepts strings or floats)

Bugs
====

Please use the Github issue tracker.

License
=======

AGPL3+
