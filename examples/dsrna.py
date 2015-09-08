import ndbapi

c = ndbapi.Client()
q = {
        "structural_content.RNA.value": "Y",
        "structural_content.DNA.value": "N",
        "structural_content.hybrid.value": "N",
        "structural_content.protein.value": "N",
        "structural_content.ligand.value": "N",
        "experimental_information.determined_by_crystallography.value": "Y",
        "experimental_information.determined_by_nmr.value": "N",
        "structural_conformation_type.strand_description.choices": ["Double Helix"],
        "structural_conformation_type.conformation_type.choice": "A"
    }
rs = c.query(q)

# get results as a pandas.DataFrame to manipulate in code
data = rs.data
print(data.head())

# export results to TSV (I use TSV instead of CSV because some fields have embedded commas, you can change delimiter with "sep" parameter)
rs.save("results.tsv")
