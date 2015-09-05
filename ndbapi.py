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
    def __init__(self, category, e):
        self._category = category
        self._key = ".".join([category.key, e["key"]])
        self._id = e["id"]
        self._type = e["type"]
        self._is_global = e.get("global", False)
        self._has_bitop = e.get("has_bitop", True)
        # only relevant to mchoice
        self._clause_bitop = e.get("clause_bitop", True)

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
        pass

    def transform(self, params):
        """
        Transform the user-facing parameters into POST parameters for the NDB website.
        Also validate the parameters (any of them may have been edited by the user).
        """
        sp = dict([(k.split(".")[-1],v) for k,v in params.items()])
        if self._type == "relative_frequency":
            return self._transform_relative_frequency(sp)

        o = {}
        rid = self._id if self._is_global else "{}_{}".format(self.category.prefix, self._id)

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
        elif self._type in ("text", "nop"):
            o["q_{}".format(rid)] = str(sp["value"])


from pprint import pprint

class NDBAPI(object):
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
                    e = Element(category, edata)
                    self._elements[e._key] = e
                    self._defaults.update(e.parameters)

    def query(self, params):
        assert isinstance(params, dict)

        for k in params:
            if not k in self._defaults:
                raise ValueError("Invalid key provided: '{}'".format(k))
        np = self._defaults.copy()
        np.update(params)
        params = np

        for ek, keys in groupby(params.keys(), lambda k: ".".join(k.split(".")[:-1])):
            lparams = dict([(k,params[k]) for k in keys])
            print(ek, lparams)

if __name__ == "__main__":
    api = NDBAPI()
    rs = api.query({})
    print(rs)
