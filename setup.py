from os.path import dirname, join as pjoin, exists as pexists
from pip.req import parse_requirements
from pip.download import PipSession
from setuptools import setup, find_packages

requirements = pjoin(dirname(__file__), "requirements.txt")
assert pexists(requirements)
requirements = [str(r.req) for r in parse_requirements(requirements, session=PipSession())]

setup(
    name="ndbapi",
    version="0.1",
    description="API for Rutgers Nucleic Acid Database",
    author="Cory Giles",
    author_email="mail@corygil.es",
    include_package_data=True,
    packages=find_packages(),
    url="http://github.com/gilesc/ndbapi.git",
    install_requires=requirements
)
