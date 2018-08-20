# -*- coding: utf-8 -*-
'''
© 2012-2013 eBay Software Foundation
Authored by: Tim Keefer
Licensed under CDDL 1.0
'''

import os
import sys
from optparse import OptionParser
from pprint import pprint

sys.path.insert(0, '%s/../' % os.path.dirname(__file__))

from common import dump

import ebaysdk
from ebaysdk.finding import Connection as finding
from ebaysdk.trading import Connection as trading
from ebaysdk.exception import ConnectionError

def init_options():
    usage = "usage: %prog [options]"
    parser = OptionParser(usage=usage)

    parser.add_option("-d", "--debug",
                      action="store_true", dest="debug", default=False,
                      help="Enabled debugging [default: %default]")
    parser.add_option("-y", "--yaml",
                      dest="yaml", default='ebay.yaml',
                      help="Specifies the name of the YAML defaults file. [default: %default]")
    parser.add_option("-a", "--appid",
                      dest="appid", default=None,
                      help="Specifies the eBay application id to use.")

    (opts, args) = parser.parse_args()
    return opts, args


def run(opts):

    try:
        api = finding(debug=opts.debug, appid=opts.appid,
                      config_file=opts.yaml, warnings=True)

        api_request = {
            #'keywords': u'niño',
            'keywords': u'GRAMMY Foundation®',
            'itemFilter': [
                {'name': 'Condition',
                 'value': 'Used'},
                {'name': 'LocatedIn',
                 'value': 'GB'},
            ],
            'affiliate': {'trackingId': 1},
            'sortOrder': 'CountryDescending',
        }

        response = api.execute('findItemsAdvanced', api_request)

        dump(api)
    except ConnectionError as e:
        print(e)
        print(e.response.dict())


def run_unicode(opts):

    try:
        api = finding(debug=opts.debug, appid=opts.appid,
                      config_file=opts.yaml, warnings=True)

        api_request = {
            'keywords': u'Kościół',
        }

        response = api.execute('findItemsAdvanced', api_request)
        for i in response.reply.searchResult.item:
            if i.title.find(u'ś') >= 0:
                print("Matched: %s" % i.title)
                break

        dump(api)

    except ConnectionError as e:
        print(e)
        print(e.response.dict())



def run2(opts):
    try:
        api = finding(debug=opts.debug, appid=opts.appid, config_file=opts.yaml)
        
        response = api.execute('findItemsByProduct', 
          '<productId type="ReferenceID">53039031</productId><paginationInput><entriesPerPage>1</entriesPerPage></paginationInput>')
        
        dump(api)
        return response.dict()

    except ConnectionError as e:
        print(e)
        print(e.response.dict())


def run_motors(opts):
    api = finding(siteid='EBAY-MOTOR', debug=opts.debug, appid=opts.appid, config_file=opts.yaml,
                  warnings=True)

    api.execute('findItemsAdvanced', {
        'keywords': 'tesla',
    })

    if api.error():
        raise Exception(api.error())

    if api.response_content():
        print("Call Success: %s in length" % len(api.response_content()))

    print("Response code: %s" % api.response_code())
    print("Response DOM: %s" % api.response_dom())

    dictstr = "%s" % api.response_dict()
    print("Response dictionary: %s..." % dictstr[:250])
    
    
def find_user_listing(opts):

    try:
        api = finding(debug=opts.debug, appid=opts.appid,
                      config_file=opts.yaml, warnings=True)

        api_request = {
            #'keywords': u'niño',
            'itemFilter': [
                {'name': 'Seller',
                 'value': 'socal.alldayeveryday'}
            ],
            'affiliate': {'trackingId': 1},
            'paginationInput': {'entriesPerPage': 200}
        }

        response = api.execute('findItemsAdvanced', api_request)

        dump(api)
        
        return response.dict()
        
    except ConnectionError as e:
        print(e)
        print(e.response.dict())
    
    
def find_specific_listing(opts):

    try:
        api = finding(debug=opts.debug, appid=opts.appid,
                      config_file=opts.yaml, warnings=True)
                      
        # Include a function to exclude all special characters here
        api_request = {
            #'keywords': u'niño',
            'keywords': u'rice ball mold',
            'paginationInput': {'entriesPerPage': 200}
        }


        response = api.execute('findItemsAdvanced', api_request)

        dump(api)
        
        return response.dict()
        
    except ConnectionError as e:
        print(e)
        print(e.response.dict())    
    

def GetCategory(opts):
    # Toys : 220

    try:
        api = trading(debug=opts.debug, appid=opts.appid,
                      config_file=opts.yaml, warnings=True)
                      
        # Include a function to exclude all special characters here
        api_request = {
            'CategoryParent': 220,
            'LevelLimit': 4,
            'ViewAllNodes': 'False',
            'DetailLevel': 'ReturnAll'
        }


        response = api.execute('GetCategories', api_request)

        dump(api)
        
        return response.dict()
        
    except ConnectionError as e:
        print(e)
        print(e.response.dict())    
    
    
    
if __name__ == "__main__":
    print("Finding samples for SDK version %s" % ebaysdk.get_version())
    (opts, args) = init_options()
    
    #user_data = find_user_listing(opts)
    listing = find_specific_listing(opts)
    #category = GetCategory(opts)
#    for i in category['CategoryArray']['Category']:
#        if i['CategoryName'] == "Contemporary Manufacture":
#            desired_category = i['CategoryID']