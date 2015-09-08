import ndbapi

TESTS = [
        (1, {"citation_information.PDB_ID.value": "4WLS"}),
        (48, {
            "structural_content.RNA.value": "Y",
            "structural_content.DNA.value": "N",
            "structural_content.hybrid.value": "N",
            "structural_content.protein.value": "N",
            "structural_content.ligand.value": "N",
            "experimental_information.determined_by_crystallography.value": "Y",
            "experimental_information.determined_by_nmr.value": "N",
            "structural_conformation_type.strand_description.choices": ["Double Helix"],
            "structural_conformation_type.conformation_type.choice": "A"
        })
]

def test():
    api = ndbapi.Client()
    for n, q in TESTS:
        rs = api.query(q)
        assert len(rs) == n

if __name__ == "__main__":
    test()
