#!/bin/env python
import sys
import argparse
import logging

cur_version = sys.version_info

from table2latex.textable import TexTable

# setup logging
log = logging.getLogger('latextable-cli')

def setupLogging( loglevel ):
    #setup logging
    format = '%(levelname)s: %(message)s'

    if cur_version[0] < 3:
        pyloglevel = logging._levelNames[ loglevel ]
    else:
        pyloglevel = getattr(logging, loglevel)
    logging.basicConfig( level=pyloglevel, format=format)
    formatter = logging.Formatter( format )

def commandline_parsing():
    parser = argparse.ArgumentParser( formatter_class=argparse.RawTextHelpFormatter,
        description='Create latex input files with tables from database' )
    parser.add_argument( '--debug', metavar='LEVEL', default='INFO',
        choices=[ 'ERROR', 'WARNING', 'INFO', 'DEBUG' ],
        help='Set the debug level. default: %(default)s' )
    parser.add_argument('-c', '--config', help='Config file')
    parser.add_argument('csv', help='input csv file')
    args = parser.parse_args()
    return args

def main():

    args = commandline_parsing()
    setupLogging( args.debug )
    #table_cols = ["car"]
    table = TexTable(config=args.config)#, table_cols=table_cols)
    # read in csv file from database dump
    table.read_csv(args.csv)
    table.write_tex_file()
    table.write_pdf_file()

if __name__=='__main__':
    main()
