from __future__ import print_function

import collections
import subprocess
import logging
import imp
import csv
import re

import table2latex.rounding as rounding

# Fix Python 2.x.
try:
    UNICODE_EXISTS = bool(type(unicode))
except NameError:
    unicode = lambda s: str(s)

LATEX_ESCAPE_RULES = {r"&": r"\&", r"%": r"\%", r"$": r"\$", r"#": r"\#",
                      r"_": r"\_", r"^": r"\^{}", r"{": r"\{", r"}": r"\}",
                      r"~": r"\textasciitilde{}", "\\": r"\textbackslash{}",
                      r"<": r"\ensuremath{<}", r">": r"\ensuremath{>}"}

# setup logging
log = logging.getLogger('latextable-cli')

def escape_latex(text):
    """
        :param text: a plain text message
        :return: the message escaped to appear correctly in LaTeX
    """
    conv = {
        '&': r'\&',
        '%': r'\%',
        '$': r'\$',
        '#': r'\#',
        '_': r'\_',
        '{': r'\{',
        '}': r'\}',
        '~': r'\textasciitilde{}',
        '^': r'\^{}',
        '\\': r'\textbackslash{}',
        '<': r'\textless',
        '>': r'\textgreater',
    }
    regex = re.compile('|'.join(re.escape(unicode(key)) for key in sorted(conv.keys(), key = lambda item: - len(item))))
    return regex.sub(lambda match: conv[match.group()], text)

class TexTableConfig(object):
    def __init__(self):
        self._table_cols = []
        self._group_order = []
        self._header_relacement_maps = []
        self._col_width_map = {}
        self._col_separator_map = {}
        self._col_func_map = {}
        self._col_merge_map = {}
        self._col_raw_list = []
        self._packages  = []
        self._replacements = TexReplacements()
    def add_package(self, package):
        self._packages.append(package)
    def add_header_line(self, line_dict):
        self._header_relacement_maps.append(line_dict)
    def add_group_order(self, group_list):
        self._group_order = group_list
    def add_column_keys(self, key_list):
        self._table_cols = key_list
    def add_column_widths(self, width_dict):
        self._col_width_map = width_dict
    def add_global_replacement(self, string, replacement):
        self._replacements.add_global_replacement(string, replacement)
    def add_row_replacement(self, string, replacement, colkey):
        self._replacements.add_row_replacement(string, replacement, colkey)
    def add_column_separator(self, separator, colkey):
        self._col_separator_map[colkey] = separator
    def add_column_func(self, func, colkey):
        self._col_func_map[colkey] = func
    def add_raw_flag(self, colkey):
        self._col_raw_list.append(colkey)
    def add_column_merge_list(self, merge_list, colkey):
        self._col_merge_map[colkey] = merge_list


class TexTable(object):
    ''' Table object to create table from list of row objects '''
    def __init__( self,
                  row_list=[],
                  table_cols=[], # a list of column keys with all keys included in
                              # the tabsle
                  sortkey = None, # column key used to sort table / group
                  groupkey=None, # key used to group rows
                  group_func=None, # callback function to create group field based on row
                  hide_group = True, # Flag to control if grouping column should
                                      # be visible in the table
                  packages = [], #list of packgaes to include
                  tablestyle = "tabular", # latex style used for table object
                  default_col_separator = "|",
                  row_group_separator = "\hline", # separator added between group
                  col_separator_map = {}, # map for left hand side separator for
                                          # each column with separator different
                                          # from default_col_separator
                  col_func_map = {}, # map of functions to alter input value for col
                  col_merge_map = {}, # map of colkeys to list of colkeys to mere
                                     # in single col
                  col_raw_list = [], # List of cols which should be displayed raw
                  chunksize = 1e9, # Number of entries before the table is
                                   # splitted in subtables
                  landscape = False, # Flag for landscape mode
                  out = "outtable.tex", # output file
                  config = None, # path to python cofig file
                  significant_digits = 3,
                  **kwargs):
        # settings
        self.chunksize = chunksize
        self.landscape = landscape
        self.sortkey = sortkey
        self.groupkey = groupkey
        self.group_func = group_func
        self.hide_group = hide_group
        self.tablestyle = tablestyle
        self.packages = packages
        self.out = out
        self.row_group_separator = row_group_separator
        self.default_col_separator = default_col_separator
        self.significant_digits = significant_digits
        # fields
        self.tex = ""

        self._table_cols = table_cols
        self._header_relacement_maps = []
        self._col_width_map = {}
        self._col_separator_map = {}
        self._col_func_map = col_func_map
        self._col_merge_map = col_merge_map
        self._col_raw_list = col_raw_list
        self._group_order =  []
        self._col_func_map = {}
        self._replacements = TexReplacements()
        if config:
            self.read_config(config)

        # caching for dynamic fields
        self._group_row_dict = None
        self._table_chunks = None
        self._table_header = None
        # init code
        self.rows = self.sort_rows( row_list )

    def read_config(self, config):
        ''' Read config file objext (TexTableConfig) from file'''
        if isinstance(config, str):
            config_file = imp.load_source("pycfg", config )
            config = config_file.config
        private_attrs = ["table_cols",
                         "group_order",
                         "header_relacement_maps",
                         "col_width_map",
                         "col_separator_map",
                         "col_func_map",
                         "col_merge_map",
                         "col_raw_list",
                         "replacements",
                        ]
        for at in private_attrs:
            self._add_private(at, config)
        self.packages = config._packages
        for attr in config.__dict__:
            if attr.startswith("_"):
                continue
            setattr(self, attr, getattr(config, attr))

    def _add_private(self, attr_name, config):
        ''' private function to add private fields from config if set '''
        attr_name = "_" + attr_name
        if getattr(config, attr_name):
            setattr(self, attr_name, getattr(config, attr_name))

    def sort_rows(self, row_list):
        ''' Sort rows based on tables sort key '''
        if not self.sortkey:
            return row_list
        return sorted( row_list,
                       key=lambda x: getattr( x, self.sortkey ),
                       reverse=True )
    @property
    def group_order(self):
        ''' property for ordered group values in list '''
        #check which group values are present in group order list
        #existing keys
        group_vals = set([row.group for row in self.rows])
        if not self._group_order:
            return list(group_vals)
        unordered_groups = [group for group in group_vals if not group in self._group_order]
        return self._group_order + unordered_groups

    def get_col_width(self, colkey):
        ''' Get the column width for a given column key'''
        if colkey in self._col_width_map:
            return self._col_width_map[colkey]
        else:
            return None

    def get_col_separator(self, colkey):
        ''' Get the column seperarator for a given column key'''
        if colkey in self._col_separator_map:
            return self._col_separator_map[colkey]
        return self.default_col_separator

    def get_group_order_index( self, group ):
        ''' Get index of group entry in group ordering '''
        if group in self.group_order:
            return self.group_order.index( group )
        else:
            return len(self.group_order)

    @property
    def group_row_dict(self):
        ''' Property for dict of rows sorted by group attribute.'''
        if not self._group_row_dict:
            self._group_row_dict = collections.OrderedDict()
            for row in self.rows:
                group = row.group
                if not group in self._group_row_dict:
                    self._group_row_dict[ group ] = []
                self._group_row_dict[ group ].append( row )
            self._group_row_dict = collections.OrderedDict(
                 sorted( self._group_row_dict.items(),
                    key=lambda t: self.get_group_order_index(t[0])
                    ))
        return self._group_row_dict

    def get_table_chunks(self):
        ''' Split table into chunks bases on given chunksize'''
        table_chunks = []
        chunk = []
        for group, row_list in self.group_row_dict.items():
            for i,row in enumerate(row_list):
                row.first_in_group = not bool(i)
                if len(chunk) == self.chunksize:
                    table_chunks.append( chunk[:] )
                    chunk = []
                chunk.append( row )
        table_chunks.append( chunk )
        return table_chunks

    def get_tex_table_chunks(self):
        ''' Return tex output for table chunks '''
        tex = ''
        for chunk in self.get_table_chunks():
            tex += self.table_header
            for row in chunk:
                tex += row.table_line + '\n'
        return tex

    def get_tex_table(self):
        ''' Create the actual latex code for this table object'''
        tex = self.get_tex_table_chunks()
        tex = self.apply_table_definition(tex)
        if self.landscape:
            tex = self.apply_landscape(tex)
        return tex

    def apply_document_definition(self, tex):
        ''' Add document latex definition around given tex string '''
        newtex = '\\documentclass{article}\n'
        newtex += '\\usepackage[a4paper, total={8in, 9in}]{geometry}'
        if self.landscape:
            newtex += '\\usepackage{lscape}\n'
        for package in self.packages:
            newtex += "\\usepackage{%s}\n" % package
        newtex +='\\begin{document}\n'
        newtex += tex
        newtex += '\\end{document}\n'
        return newtex

    def apply_table_definition(self, tex):
        ''' Soround table body with latex definition '''
        new_tex =  ''
        new_tex +=  '\\begin{' + self.tablestyle +'}'
        def col_definition_tex(colkey):
            if colkey == 'group':
                colkey = self.groupkey
            width = self.get_col_width(colkey)
            width_tex = 'p{%.3f cm}' % width if width else "l"
            return self.get_col_separator(colkey) + width_tex
        col_definition_list = [col_definition_tex(col) for col in self.table_cols ]
        new_tex += '{' + " ".join(col_definition_list) + self.default_col_separator + '}\n'
        new_tex += tex
        new_tex += '\\end{'  + self.tablestyle +'}\n'
        return new_tex

    def apply_landscape(self, tex):
        ''' Add landscape latex definition around given tex string '''
        new_tex  = '\\setlength\\tabcolsep{2pt}\n'
        new_tex += '\\small\n'
        new_tex += '\\begin{center}\n'
        new_tex += '\\begin{landscape}\n'
        new_tex += tex
        new_tex += '\\end{landscape}\n'
        new_tex += '\\end{center}\n'
        return new_tex

    def write_tex_file(self):
        ''' write table as document to pdf file '''
        with open( self.out, "w") as tex_file:
            tex_file.write(self.get_tex_table())

    def write_tex_document_file(self, path):
        ''' write table as document to pdf file '''
        doctex = self.apply_document_definition(self.get_tex_table())
        with open( path, "w") as tex_file:
            tex_file.write(doctex)

    def write_pdf_file(self):
        ''' write table as document to pdf file '''
        path = self.out.replace('.tex','doc.tex')
        self.write_tex_document_file(path)
        p = subprocess.Popen("pdflatex %s" % path,
                      stdout=subprocess.PIPE,
                      stderr=subprocess.PIPE,
                      shell=True)
        (string_out,string_err) = p.communicate()
        if p.returncode != 0:
            raise RuntimeError("Failed to run pdflatex for created document %s" %self.out )

    def read_csv(self, filename):
        ''' Read samples from csv input'''
        row_list = []
        with open( filename, 'r') as csv_file:
            reader = csv.reader( csv_file )
            headerdict = {}
            for i,row in enumerate(reader):
                if i == 0 :
                    headerdict = { j : key for j, key in enumerate( row ) }
                    self.default_cols = headerdict.values()
                    continue
                rowdict = { headerdict[j]:val for j,val in enumerate(row)}
                row = TexRow(self.table_cols,
                             rowdict,
                             groupkey=self.groupkey,
                             group_func=self.group_func,
                             hide_group=self.hide_group,
                             replacements=self._replacements,
                             row_group_separator=self.row_group_separator,
                             col_func_map = self._col_func_map,
                             col_merge_map = self._col_merge_map,
                             col_raw_list = self._col_raw_list,
                             significant_digits=self.significant_digits)

                row_list.append( row )

        # Use all columns if non were specified
        #if not self.table_cols:
        #    self.table_cols = self.default_cols
        self.rows = self.sort_rows( row_list )

    def add_row(self, tex_row):
        ''' Add a single TexRow object to the table '''
        self.rows = self.sort_rows( self.rows + [tex_row] )

    def add_row_dict(self, row_dict):
        row = TexRow(self.table_cols,
                     row_dict,
                     groupkey=self.groupkey,
                     group_func=self.group_func,
                     hide_group=self.hide_group,
                     replacements=self._replacements,
                     row_group_separator=self.row_group_separator,
                     col_func_map = self._col_func_map,
                     col_merge_map = self._col_merge_map,
                     col_raw_list = self._col_raw_list,
                     significant_digits=self.significant_digits)
        self.add_row(row)


    def add_header_line(self, linedict):
        ''' Add a single line for the header lines.
            The header might consist of several rows for each
            column, e.g. unit in next row or multi column text.
            linedict needs to contain pairs of columnkeys : tex_string
            where tex_string contains the header tex replacement for
            this line
        '''
        self._header_relacement_maps.append(linedict)

    @property
    def header_replacement_maps(self):
        ''' Property for list of validated maps of header line
            replacements maps. Return default entries with raw key as value if
            tablecol key does not exist in any replacement dicts
        '''
        #Add raw key to first line if a table column key is missing from all lines
        if not self._header_relacement_maps:
            self._header_relacement_maps.append({})

        for i,line in enumerate(self._header_relacement_maps):
            if self.groupkey in line:
                line['group'] = line[self.groupkey]
            self._header_relacement_maps[i] = line
        for col in self.table_cols:
            # add empty line if no line was added yet
            if not any([any([col == key for key in line]) for line in self._header_relacement_maps]):
                self._header_relacement_maps[0][col] = escape_latex(col)
        return self._header_relacement_maps

    @property
    def table_cols(self):
        ''' Property for all table columns '''
        # add empty dict if no columns
        if not self._table_cols:
            self._table_cols = self.default_cols
        if self.groupkey in self._table_cols:
            self._table_cols.remove(self.groupkey)
        log.info(self._table_cols)
        if self.hide_group:
            return self._table_cols
        else:
            return ['group'] + self._table_cols

    @property
    def table_header(self):
        ''' Property for table header tex '''
        if not self._table_header:
            ''' Get the (multiline) table header '''
            # inline function to fill line
            def fill_line(table_cols, header_map):
                col_list = []
                for col in table_cols:
                    if col in header_map:
                        val = header_map[ col ]
                    else:
                        val = ""
                    col_list.append( val )
                return " & ".join( col_list )

            # add text and replacements for all header lines
            self._table_header = ""
            for line in self.header_replacement_maps:
                self._table_header += fill_line( self.table_cols, line)
                self._table_header += '\\\\\n'

        return self._table_header

class TexRow(object):
    ''' Class representing a single row in a latex table '''
    def __init__( self,
                  rowkeys,
                  rowdict,
                  group_func=None,
                  groupkey = None,
                  hide_group = False,
                  first_in_group = False,
                  row_group_separator = "\hline",
                  col_func_map = {},
                  col_merge_map = {},
                  col_raw_list = [],
                  replacements=None,
                  significant_digits=2 ):
        #settings
        self.rowkeys = rowkeys
        self.rowdict = rowdict
        self.first_in_group = first_in_group
        self.hide_group = hide_group
        self.row_group_separator = row_group_separator
        self._col_func_map = col_func_map
        self._col_merge_map = col_merge_map
        self._col_raw_list = col_raw_list
        self.rounding = rounding.rounding(sigdigits=significant_digits, negdigits=3, posdigits=2)
        self._group_func = group_func
        if replacements:
            self._replacements = replacements
        else:
            self._replacements = TexReplacements()
        self.groupkey = groupkey
        self.tex_replacement_map = {}
        for key,val in rowdict.items():
            if not hasattr(self, key):
                try:
                    val = float(val)
                    valint = int(val)
                    if valint - val == 0:
                        val = valint
                except:
                    pass
                setattr(self, key, val)
            else:
                print("Warning: key % used twice" % key)
    @property
    def group( self ):
        ''' Property for row group '''
        # use callback function if passed
        if self._group_func is not None:
            return self._group_func(self)
        if self.groupkey:
            return getattr(self, self.groupkey)
        return None

    def _merge_col(self, value, colkey):
        ''' internal function to merge columns '''
        merge_values = [value]
        for key in self._col_merge_map[colkey]:
            value = self.col_value(key)
            merge_values.append(value)
        return " ".join(merge_values)

    def col_value(self, colkey):
        ''' Return value for a column in the row with replacements applied '''
        altered = False

        # check if values should be altered by func map
        if colkey in self._col_func_map:
            value = self._col_func_map[colkey](self)
            altered = True
        else:
            value = getattr(self, colkey)
        # apply rounding for numbers
        if type(value) == float or type(value) == int:
            value = self.rounding.latex( value )
            altered = True
        else:
            # apply replacements for texts
            if not altered:
                replacement = self._replacements.apply_replacement(value, colkey)
            else:
                replacement = value
            if colkey in self._col_raw_list:
                value
            elif value == replacement and not altered:
                value = escape_latex(value)
            else:
                value = replacement
        # merge multiple columns in this column
        if colkey in self._col_merge_map:
            value = self._merge_col(value, colkey)
        return value

    @property
    def table_line( self ):
        ''' Get a single table line '''
        tex = ''
        if self.groupkey:
            if not self.hide_group:
                if self.first_in_group:
                    if self.row_group_separator == "newline":
                        tex =  '&'.join(["" for f in self.rowkeys]) + "\\\\"
                    else:
                        tex = self.row_group_separator + "\n"
                    if self.groupkey in self._col_raw_list:
                        tex+= '%s &' % self.group
                    else:
                        tex+= '%s &' % self._replacements.apply_replacement( self.group,
                                                                             self.groupkey)
                else:
                    tex = '& '
        row_list = []
        for key in self.rowkeys:
            # groupkey is already handled
            if key == self.groupkey or key =="group":
                continue
            value = self.col_value(key)
            row_list.append( value )
        return tex + " & ".join( row_list ) + '\\\\'


class TexReplacements(object):
    ''' Class to manage tex replacemnts set in config files '''
    def __init__(self):
        self._global_replacements = {}
        self._row_replacements = {}

    def add_global_replacement(self, string, replacement):
        ''' Add on global replacements used if no other replacement matches first '''
        self._global_replacements[string] = replacement

    def add_row_replacement(self, string, replacement, colkey):
        ''' Add one replacment used for all field in one column'''
        if not colkey in self._row_replacements:
            self._row_replacements[colkey] = {}
        self._header_replacements[colkey][string] = replacement

    def apply_replacement(self, input_string, colkey=None):
        ''' Apply all string replacements on a given input string'''
        applied_row_replacements = []
        real_replacement_map = {}
        if colkey and colkey in self._row_replacements:
            for string in self._row_replacements[colkey]:
                if string in input_string:
                    replacement = self._row_replacements[colkey][string]
                    temp_string = "REPLACE%d" % len(real_replacement_map)
                    real_replacement_map[temp_string] = replacement
                    input_string = input_string.replace(string, temp_string)
                    applied_row_replacements.append(string)

        for string in self._global_replacements:
            # check if the string was replaced in previous step and skip replacement
            # in this case to avoid unintentional double replacements
            if string in applied_row_replacements:
                continue
            if string in input_string:
                temp_string = "REPLACE%d" % len(real_replacement_map)
                replacement = self._global_replacements[string]
                real_replacement_map[temp_string] = replacement
                input_string = input_string.replace(string, temp_string)
        # We now replaced all strings which should be replaced with tempstrings
        # without any escapable characters. We can now replace the remaining text
        # and finish the real replacement
        input_string = escape_latex(input_string)
        for key,val in real_replacement_map.items():
            input_string = input_string.replace(key, val)

        return input_string

    def get_replacement(self, string, colkey=None):
        ''' Return string replacement from hierarchical search in available
            replacement maps
        '''
        if colkey and colkey in self._row_replacements:
            if string in self._header_replacements[colkey]:
                return self._header_replacements[colkey][string]
        if string in self._global_replacements:
            return self._global_replacements[string]
        return string
