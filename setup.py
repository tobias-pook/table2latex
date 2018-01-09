from setuptools import setup

setup(name='table2latex',
      version='0.1',
      description='A python tool to create latex tables in code or from csv',
      url='http://github.com/tobias-pook/table2latex',
      author='Tobias Pook',
      author_email='info@pvalues.de',
      license='MIT',
      packages=['table2latex'],
      scripts=['bin/csv2tex.py'],
      long_description="""
      This package can be used to create latex tables from csv or programatically.
      specific functions like table chunking, global or per column string replacements.
      It contains common table features like grouping or sorting and latex replacements.
      """,
      zip_safe=True)
