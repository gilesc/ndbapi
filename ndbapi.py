# notes
# - released-since needs to updated with months
# - can scrape choices
# - remember relative_frequency has default 0.1
# - mchoice bitop is different

import enum
from collections import namedtuple, OrderedDict
from itertools import groupby

import yaml
import pandas as pd
import lxml.html
import requests

# enums

class BOp(enum.Enum):
    AND = "AND"
    OR = "OR"

class Choice(enum.Enum):
    Y = "Y"
    N = "N"
    IGNORE = "Ignore"

class NOp(enum.Enum):
    EQ = "eq"
    GTEQ = "gtEq"
    LTEQ = "ltEq"

# input types

class Input(object):
    pass

####################
# Structural content
####################

"biocn_dna"
"biocn_rna"
"biocn_hyb" # Hybrid
"biocn_pro"
"biocn_lig" # Ligand

# Structural content - ligand
"biocn_lid" # Ligand ID - text
"biocn_lnm" # Ligand Name - text
"biocn_drg" # text
"biocn_dbt" # Binding Type - multichoice - radio is i_biocn_dbt (not 'c')

##########################
# Experimental information
##########################

"etype_cry" # Structure was determined by crystallography
"etype_sfc" # Structure factors are deposited in NDB
"etype_nmr" # Structure was determined by NMR
"etype_nra" # NMR restraints are deposited in NDB

######################
# Experimental details
######################

"detal_group" # Space group - choice
"detal_*aa" # alpha - operator

"""
q = {
        "structural_content.DNA.bitop": AND,
        "structural_content.DNA.value": Y,
        "experimental_details.alpha.value": 1.5,
        "experimental_details.alpha.b_op": AND,
        "experimental_details.alpha.n_op": GTEQ
    }
"""
#"repType": "csv"

def search(**kwargs):
    pass

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
        self._clause_bitop = e.get("clause_bitop", True)

        self._cfn = cfn

    def __repr__(self):
        return "<Element t={} k={}>".format(self._type, self._key)

    @property
    def parameters(self):
        rid = self._id if self._is_global else "{}_{}".format(self._category.prefix, self._id)
        o = {}
        def add(k, v):
            o["{}.{}".format(self._key, k)] = v

        if self._has_bitop:
            add("bitop", "AND")

        if self._type == "radio":
            add("value", "Ignore")
        elif self._type == "radio_na":
            add("value", "EITHER")
        elif self._type == "text":
            add("value", "")
        elif self._type == "relative_frequency":
            add("cutoff", "0.1")
            add("nop", "gtEq")
            add("choice", "")
        elif self._type == "nop":
            add("value", "")
            add("nop", "eq")
        elif self._type == "minmax":
            add("minimum", "")
            add("maximum", "")
        elif self._type == "choice":
            add("choice", "")
        elif self._type == "mchoice":
            add("choices", [""])
        else:
            raise ValueError("There is an error in the YAML schema. Either it was edited, or this is a programming error and you should contact the developer.")
        return o

    def _transform_relative_frequency(self, sp):
        o = {}
        assert sp["bitop"] in ("AND", "OR")
        assert sp["nop"] in ("gtEq", "ltEq", "eq")
        o["c_{}_count".format(self._id)] = sp["bitop"]
        o["q_{}_int".format(self._id)] = sp["choice"]
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
        rid = self._id if self._is_global else "{}_{}".format(self._category.prefix, self._id)
        choices = self._cfn("q_{}".format(rid))
        print(rid)
        print(choices)
        assert sp["choice"] in choices
        o = {}
        o["q_{}".format(rid)] = choices[sp["choice"]]
        o["c_{}".format(rid)] = sp["bitop"]
        return o

    def transform(self, params):
        """
        Transform the user-facing parameters into POST parameters for the NDB website.
        Also validate the parameters (any of them may have been edited by the user).
        """
        sp = dict([(k.split(".")[-1],v) for k,v in params.items()])

        if self._type == "relative_frequency":
            return self._transform_relative_frequency(sp)
        elif self._type == "nop":
            return self._transform_nop(sp)
        elif self._type == "choice":
            return self._transform_choice(sp)

        o = {}
        rid = self._id if self._is_global else "{}_{}".format(self._category.prefix, self._id)

        if "bitop" in sp:
            v = sp["bitop"]
            assert v in ("AND", "OR")
            o["c_{}".format(rid)] = v

        if self._type in ("radio", "radio_na"):
            v = sp["value"]
            if self._type == "radio":
                assert v in ("Y", "N", "Ignore")
            else:
                assert v in ("RNA", "DNA", "EITHER")
            o["q_{}".format(rid)] = v
        elif self._type == "text":
            o["q_{}".format(rid)] = str(sp["value"])

        return o


from pprint import pprint

class NDBAPI(object):
    URL = "http://ndbserver.rutgers.edu/ndbmodule/search/integrated.html"

    def __init__(self):
        self._elements = {}
        self._defaults = OrderedDict()

        with open("schema.yml") as h:
            tree = yaml.load(h)
            order = tree["metadata"]["order"]
            for category_key in order:
                category_data = tree[category_key]
                category = Category(category_key, category_data["prefix"])
                for edata in category_data["elements"]:
                    e = Element(category, edata, self._get_choices)
                    self._elements[e._key] = e
                    self._defaults.update(e.parameters)

        page = requests.get(self.URL)
        self._ptree = lxml.html.fromstring(page.text)

    def _get_choices(self, id):
        names = self._ptree.xpath("//select[@name='{}']/option/text()".format(id))
        values = self._ptree.xpath("//select[@name='{}']/option/@value".format(id))
        print(names)
        if len(values) > 1:
            return OrderedDict(zip(names, values))
        else:
            return OrderedDict([("","")] + list(zip(names[1:], names[1:])))

    def query(self, params):
        assert isinstance(params, dict)

        for k in params:
            if not k in self._defaults:
                raise ValueError("Invalid key provided: '{}'".format(k))
        np = self._defaults.copy()
        np.update(params)
        params = np

        for ek, keys in groupby(params.keys(), lambda k: ".".join(k.split(".")[:-1])):
            e = self._elements[ek]
            lparams = dict([(k,params[k]) for k in keys])
            print(e.transform(lparams))
            #print(ek, lparams)

if __name__ == "__main__":
    api = NDBAPI()
    #print(api._get_choices("q_citat_rel"))
    rs = api.query({})
    #print(rs)
    #print(rs)
