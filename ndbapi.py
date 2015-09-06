from collections import namedtuple, OrderedDict
from itertools import groupby
import datetime
import io
import os.path
import pprint
import re
import sys

import lxml.html
import pandas as pd
import requests
import yaml

Category = namedtuple("Category", "key,prefix")

class Element(object):
    def __init__(self, category, e, cfn):
        self._category = category
        self._key = ".".join([category.key, e["key"]])
        self._id = e["id"]
        self._type = e["type"]
        self._is_global = e.get("global", False)
        self._has_bitop = e.get("has_bitop", True)
        # only relevant to mchoice
        self._clause_bitop = e.get("clause_bitop")

        rid = self._id if self._is_global else "{}_{}".format(self._category.prefix, self._id)
        if self._type in ("choice", "mchoice"):
            self._choices = cfn("q_{}".format(rid))
        elif self._type == "relative_frequency":
            self._choices = cfn("q_{}_int".format(rid))
        else:
            self._choices = None

    def __repr__(self):
        return "<Element t={} k={}>".format(self._type, self._key)

    def options(self, opt):
        if opt == "bitop":
            return ("AND", "OR")
        elif opt == "value":
            if self._type == "radio":
                return ("Ignore", "Y", "N")
            elif self._type == "radio_na":
                return ("EITHER", "DNA", "RNA")
            else:
                return
        elif opt in ("maximum", "minimum", "cutoff"):
            return
        elif opt in ("choice", "choices"):
            return tuple(self._choices.keys())

    @property
    def parameters(self):
        rid = self._id if self._is_global else "{}_{}".format(self._category.prefix, self._id)
        o = {}
        def add(k, v):
            o["{}.{}".format(self._key, k)] = v

        if self._has_bitop:
            bitop = self._clause_bitop or "AND"
            add("bitop", bitop)

        if self._type == "radio":
            add("value", "Ignore")
        elif self._type == "radio_na":
            add("value", "EITHER")
        elif self._type == "text":
            add("value", "")
        elif self._type == "relative_frequency":
            add("cutoff", "0.1")
            add("nop", "gtEq")
            add("choice", self._choices.default)
        elif self._type == "nop":
            add("value", "")
            add("nop", "eq")
        elif self._type == "minmax":
            add("minimum", "")
            add("maximum", "")
        elif self._type == "choice":
            add("choice", self._choices.default)
        elif self._type == "mchoice":
            add("choices", [self._choices.default])
        else:
            raise ValueError("There is an error in the YAML schema. Either it was edited, or this is a programming error and you should contact the developer.")
        return o

    def _transform_relative_frequency(self, sp):
        o = {}
        o["c_{}_count".format(self._id)] = sp["bitop"]
        o["q_{}_int".format(self._id)] = self._choices[sp["choice"]]
        o["q_{}_op".format(self._id)] = sp["nop"]
        o["q_{}_count".format(self._id)] = str(sp["cutoff"])
        return o

    def _transform_nop(self, sp):
        assert sp["bitop"] in ("AND", "OR")
        assert sp["nop"] in ("gtEq", "ltEq", "eq")
        o = {}
        o["c_{}_{}n{}".format(self._category.prefix, self._id[0], self._id[1])] = sp["bitop"]
        o["q_{}_v{}".format(self._category.prefix, self._id)] = str(sp["value"])
        o["q_{}_o{}".format(self._category.prefix, self._id)] = sp["nop"]
        return o

    def _transform_choice(self, sp):
        o = {}
        rid = self._id if self._is_global else "{}_{}".format(self._category.prefix, self._id)
        o["q_{}".format(rid)] = self._choices[sp["choice"]] #if sp["choice"] != "" else next(iter(self._choices.values()))
        o["c_{}".format(rid)] = sp["bitop"]
        return o

    def _transform_mchoice(self, sp):
        o = {}
        rid = self._id if self._is_global else "{}_{}".format(self._category.prefix, self._id)
        i_choices = sp["choices"]
        assert isinstance(i_choices, list)
        o_choices = [self._choices[c] for c in sp["choices"]]
        if (len(o_choices) == 1) and (o_choices[0] == ""):
            o_choices = ""
        o["q_{}".format(rid)] = o_choices
        o["i_{}".format(rid)] = sp["bitop"]
        return o
        
    def validate(self, sp):
        for k,v in sp.items():
            opts = self.options(k)
            if opts is None:
                assert isinstance(v, str)
            elif (k == "choices") and self._type == "mchoice":
                assert type(v) in (str, list)
                if isinstance(v, list):
                    for vv in v:
                        assert vv in opts
                else:
                    assert v in opts
            else:
                assert v in opts

    def transform(self, params):
        """
        Transform the user-facing parameters into POST parameters for the NDB website.
        Also validate the parameters (any of them may have been edited by the user).
        """
        sp = dict([(k.split(".")[-1],v) for k,v in params.items()])
        self.validate(sp)

        if self._type == "relative_frequency":
            return self._transform_relative_frequency(sp)
        elif self._type == "nop":
            return self._transform_nop(sp)
        elif self._type == "choice":
            return self._transform_choice(sp)
        elif self._type == "mchoice":
            return self._transform_mchoice(sp)

        o = {}
        rid = self._id if self._is_global else "{}_{}".format(self._category.prefix, self._id)

        if "bitop" in sp:
            v = sp["bitop"]
            o["c_{}".format(rid)] = v

        if self._type in ("radio", "radio_na"):
            v = sp["value"]
            o["q_{}".format(rid)] = v
        elif self._type == "text":
            o["q_{}".format(rid)] = str(sp["value"])

        return o


class Result(object):
    def __init__(self, params, data):
        self.params = params
        self.data = data
        self._date = datetime.datetime.now()

    def __len__(self):
        return self.data.shape[0]

    def save(self, path, sep="\t"):
        with open(path, "wt") as h:
            h.write("# date: {}\n".format(self._date))
            for k,v in self.params.items():
                h.write("## {}: {}\n".format(k, repr(v)))
            self.data.to_csv(h, sep=sep, index=False)

class Client(object):
    URL = "http://ndbserver.rutgers.edu/ndbmodule/search/integrated.html"
    POST_URL = "http://ndbserver.rutgers.edu/service/ndb/search/integrated"

    def __init__(self):
        self._elements = {}
        self._defaults = OrderedDict()

        page = requests.get(self.URL)
        self._ptree = lxml.html.fromstring(page.text)

        schema_path = os.path.join(os.path.dirname(__file__), "schema.yml")
        with open(schema_path) as h:
            tree = yaml.load(h)
            order = tree["metadata"]["order"]
            for category_key in order:
                category_data = tree[category_key]
                category = Category(category_key, category_data["prefix"])
                for edata in category_data["elements"]:
                    e = Element(category, edata, self._get_choices)
                    self._elements[e._key] = e
                    self._defaults.update(e.parameters)

    def _get_choices(self, id):
        names = []
        values = []
        default = None

        for opt in self._ptree.xpath("//select[@name='{}']/option".format(id)):
            n = opt.text or ""
            v = opt.attrib.get("value")
            v = n if v is None else v
            names.append(n)
            values.append(v)
            if opt.attrib.get("selected") is not None:
                default = n

        o = OrderedDict(zip(names, values))
        o.default = default
        return o

    def _transform_parameters(self, params):
        assert isinstance(params, dict)

        for k in params:
            if not k in self._defaults:
                raise ValueError("Invalid key provided: '{}'".format(k))
        np = self._defaults.copy()
        np.update(params)
        params = np
        
        oparams = {"repType": "csv", "submit": "Search"}
        for ek, keys in groupby(params.keys(), lambda k: ".".join(k.split(".")[:-1])):
            e = self._elements[ek]
            lparams = dict([(k,params[k]) for k in keys])
            oparams.update(e.transform(lparams))
        pprint.pprint(oparams)
        return oparams

    def _parse_result(self, handle):
        """
        Parse a file-like object containing the "CSV" data returned by the web service.

        Unfortunately this is not real CSV; internal commas aren't escaped. So to parse
        it correctly, some heuristics are used here.
        """
        while True:
            line = next(handle)
            if line.startswith("NDB ID"):
                columns = line.rstrip("\n").split(",")
                break

        rows = []
        for line in handle:
            ndb_id, pdb_id, rest = line.rstrip("\n").split(",", 2)
            middle, deposition_date, release_date = rest.rsplit(",", 2)
            authors = [a[0] for a in re.findall("([A-Z][a-z]+, [A-Z]\.([A-Z]\.)?)", middle)]
            if len(authors) == 0:
                title, authors = middle.split(",", 1)
            else:
                ix = middle.find(authors[0])
                title = middle[:(ix-1)]
                authors = middle[ix:]
                #authors = ", ".join(authors)
            row = [ndb_id, pdb_id, title, authors, deposition_date, release_date]
            rows.append(row)
        return pd.DataFrame(rows, columns=columns)

    def options(self, key):
        """
        Return a list of valid values for an option.

        Returns None if any string is accepted, or KeyError if the provided option
        does not exist.
        """
        if not key in self._defaults:
            raise KeyError("Not a valid option: '{}'".format(key))
        key, option = key.rsplit(".", 1)
        e = self._elements[key]
        return e.options(option)

    def print_options(self, handle=sys.stdout):
        o = OrderedDict()
        for key in self._defaults.keys():
            o[key] = self.options(key)

        printer = pprint.PrettyPrinter(stream=handle)
        printer.pprint(o)

    def query(self, params):
        oparams = self._transform_parameters(params)
        rq = requests.post(self.POST_URL, params=oparams)

        with io.StringIO(rq.text) as h:
            data = self._parse_result(h)
            return Result(params, data)

TESTS = [
        {"citation_information.PDB_ID.value": "4WLS"}
]

def test():
    api = Client()
    #api.print_options()
    #for opt in api._defaults.keys():
    #    print(opt, api.options(opt))
    #with open("/home/gilesc/dsRNAxray4sept2015.txt") as h:
    #    rs = api._parse_result(h)
    #    print(rs.loc[:,["Title", "Authors"]].head())

    #print(api._get_choices("q_citat_rel"))
    rs = api.query(TESTS[0])

if __name__ == "__main__":
    test()
