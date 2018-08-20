# -*- coding: utf-8 -*-
"""
Created on Sat May 07 01:44:32 2016

@author: Long Nguyen
"""

import os
import sys
import datetime
from optparse import OptionParser

sys.path.insert(0, '%s/../' % os.path.dirname(__file__))

from common import dump

import ebaysdk
from ebaysdk.exception import ConnectionError
from ebaysdk.trading import Connection as Trading
from finding import Connection as finding
from trading import Connection as sandbox_trading
from bs4 import BeautifulSoup

import lxml.html
import re
from lxml.html.clean import Cleaner
from PIL import Image
import io
import urllib
import pickle
import boto3
from contextlib import closing
from selenium.webdriver import Firefox
import amazonproduct
import re

# Use amazon api to scrape product using ASIN, extract product data, store in db

config = {
    'access_key': 'AKIAID432MWIQIL4ZEXA',
    'secret_key': '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',
    'associate_tag': 'longngu06-20',
    'locale': 'us'
}

api = amazonproduct.API(cfg=config)

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
    parser.add_option("-p", "--devid",
                      dest="devid", default=None,
                      help="Specifies the eBay developer id to use.")
    parser.add_option("-c", "--certid",
                      dest="certid", default=None,
                      help="Specifies the eBay cert id to use.")

    (opts, args) = parser.parse_args()
    return opts, args


def CreateEbayTable(table_name):
    
    dynamodb = boto3.resource('dynamodb', region_name='us-west-2', endpoint_url="http://localhost:8000")
    
    ebaytable = dynamodb.create_table(
    TableName = table_name,
    KeySchema=[
        {
            'AttributeName': 'ReferenceID',
            'KeyType': 'HASH'  #Partition key
        },
        {
            'AttributeName': 'Title',
            'KeyType': 'RANGE'  #Sort key
        }
    ],
    AttributeDefinitions=[
        {
            'AttributeName': 'ReferenceID',
            'AttributeType': 'N'
        },
        {
            'AttributeName': 'Title',
            'AttributeType': 'S'
        }

    ],
    ProvisionedThroughput={
        'ReadCapacityUnits': 10,
        'WriteCapacityUnits': 10
    }
    )

    print("Table status:", ebaytable.table_status)
    
    
def MakeEmptyFolder(item):

    name = FixTitle(item["Title"])
    newpath = ((r'C:\Users\Long Nguyen\Desktop\Amazon\EbayToolListing\lonestarsales2016\%s') % (name)) 
    if not os.path.exists(newpath): 
        os.makedirs(newpath)
        

def FixTitle(title): 
    
    title = re.sub("[^\A-Za-z0-9\']", ' ', title)
    title = re.sub( '\s+', ' ', title).strip()
    title = title.replace(" ", "_")
    return title
    

def MakeItemTitle(title):
    
    title = re.sub("[^\A-Za-z0-9\.\']", ' ', title)
    title = re.sub( '\s+', ' ', title).strip()
    return title
        
    
def ExtractHTML(item):
    
    html = lxml.html.fromstring(item)
    #for item in item_list:
    #e = tree.xpath('.//a[text()="System Requirements:"]')

    cleaner = Cleaner(kill_tags = '<a>')
                      
    new_html = cleaner.clean_html(html)
    
    start_idx = lxml.html.tostring(new_html).find('<table align="center" border="0" width="800">')
    body = lxml.html.tostring(new_html)[start_idx:]
    
    end_idx = body.find('<hr id="Terms" align="center" noshade size="1" width="800">')
    body = body[:end_idx - 1]
    
    body = '<![CDATA[' + body.replace(' color="#0000FF"','') + ']]>'

    return body

        
def ExtractProductID(response, productID):
    
    for i in range(len(response["searchResult"]["item"])):
        product = response["searchResult"]["item"][i]
        title = product["title"]
        if "productId" in product.keys():
            productID[title] = product["productId"]["value"]
        else:
            productID[title] = ""  
    
    return productID
    

def RemoveExif(image_in, image_out):
    
    image = Image.open(image_in)
    
    # 3 lines strip exif
    data = list(image.getdata())
    image_without_exif = Image.new(image.mode, image.size)
    image_without_exif.putdata(data)
    
    image_without_exif.save(image_out)    
    

def GetPictureFile(item, idx):
    
    folder_name = FixTitle(item["Title"])
    picture_name = FixTitle(item["Title"]) + "_" + str(idx) +  ".png"
    newpath = ((r'C:\Users\Long Nguyen\Desktop\Amazon\EbayToolListing\lonestarsales2016\%s\%s') % (folder_name, picture_name))

    return newpath, picture_name       

 
def ProcessPicture(picture_url, item):
    
    # Download listing picutres and save it locally with no metadata
    
    for j in range(len(picture_url)): 
        picture_file,_ = GetPictureFile(item, j) 
        f = open(picture_file, 'wb')
        while True:
            try:
                source = urllib.urlopen(picture_url[j]).read()
                break
            except IOError:
                pass
        f.write(source)
        f.close()
        RemoveExif(picture_file, picture_file)
        

def UploadPictures(opts, image_file, image_name):

    try:
        api = Trading(debug=opts.debug, config_file=opts.yaml, appid=opts.appid,
                                  certid=opts.certid, devid=opts.devid, warnings=False)
        
        try:
            with Image.open(image_file) as im:
                # scale the image to a suitable size
                # use thumbnail to scale to the bounding box
                # use resize if you want to calculate the dims 
                im.thumbnail((1600,1600))
                with io.BytesIO() as fp:
                    im.save(fp, "JPEG")
            
                    files = {'file': ('EbayImage', fp.getvalue())}
                    pictureData = {
                        "WarningLevel": "High",
                        "PictureSet":'Supersize',
                        "PictureName": image_name
                    }
                    response = api.execute('UploadSiteHostedPictures', pictureData, files=files)
                    url = response.reply.SiteHostedPictureDetails.FullURL  
                    
                    return url
            
            dump(api)
        except:
            pass
            
    except ConnectionError as e:
        print(e)
        print(e.response.dict())


def OpenPage(url):
    
     # use firefox to get page with javascript generated content
     with closing(Firefox()) as browser:
         
         browser.get(url) 
         browser.find_element_by_class_name("tve_p_lb_close").click()
         search = browser.find_element_by_id("searchTextBox")
         search.send_keys("Danish Dough Hand Whisk")
         browser.find_element_by_id("searchButton").click() 
         
         browser.find_element_by_id("exportedTitle")
         page_source = browser.page_source
         
     return str(page_source.encode('ascii','ignore'))


def SmartTitle(title):

    # In development...must do later    
    
    search_string = ''    
    for w in title.split():
        if "(" not in w:
            search_string += w
        

    from bs4 import BeautifulSoup    
    
    url = "http://title-builder.com/title-builder/"
    page = OpenPage(url)
    soup = BeautifulSoup(page)
    optimized_title = soup.find('div',{'id':'exportedTitle'}).get_text()
    " ".join(w.capitalize() for w in optimized_title.split())
    
    return optimized_title

        
def GetSellerListIn30Days(opts, user):
    
    # Get items specific details within a time frame
    
    now = datetime.datetime.now()
    result_list = []
    i = 0
    has_more_item = "true"
    while has_more_item == "true":
        try:
            i += 1
            api = Trading(debug=opts.debug, config_file=opts.yaml, appid=opts.appid,
                          certid=opts.certid, devid=opts.devid, warnings=True, timeout=20, siteid=101)
    
            callData = {
                'DetailLevel': 'ItemReturnDescription',
                'UserID': user,
                'Pagination': {
                    'entriesPerPage': 200,
                    'pageNumber': i},
                'StartTimeFrom': now - datetime.timedelta(days=90),
                'StartTimeTo': now,
                'ErrorLanguage': 'en_US'
            }
    
            response = api.execute('GetSellerList', callData).dict()
            dump(api, full=False)
    
            result = response['ItemArray']['Item']
            result_list = result_list + result
            has_more_item = response["HasMoreItems"]
            
        except ConnectionError as e:
            print(e)
            print(e.response.dict())
        
    return result_list


def FindUserActiveListing(opts, user):
    
    # Find brief active lisitng of a user
    
    i = 0
    product_id_dict = {}
    num_item = 0
    
    try:
        i += 1
        api = finding(debug=opts.debug, appid=opts.appid,
                      config_file=opts.yaml, warnings=True)

        api_request = {
            #'keywords': u'niño',
            'itemFilter': [
                {'name': 'Seller',
                 'value': user}
            ],
            'paginationInput': {
                'entriesPerPage': 200,
                'pageNumber': i}
        }

        response = api.execute('findItemsAdvanced', api_request).dict()

        dump(api)
        
        product_id_dict = ExtractProductID(response, product_id_dict)
        num_item = num_item + int(response["searchResult"]["_count"])
        expected_num_item = int(response["paginationOutput"]["totalEntries"])
            
    except ConnectionError as e:
        print(e)
        print(e.response.dict())
        
    while (num_item < expected_num_item) and (i < 100):
        try:
            i += 1
            api = finding(debug=opts.debug, appid=opts.appid,
                          config_file=opts.yaml, warnings=True)
    
            api_request = {
                #'keywords': u'niño',
                'itemFilter': [
                    {'name': 'Seller',
                     'value': user}
                ],
                'affiliate': {'trackingId': 1},
                'paginationInput': {
                    'entriesPerPage': 200,
                    'pageNumber': i}
            }
    
            response = api.execute('findItemsAdvanced', api_request).dict()
    
            dump(api)
            
            product_id_dict = ExtractProductID(response, product_id_dict)
            num_item = num_item + int(response["searchResult"]["_count"])
            
        except ConnectionError as e:
            print(e)
            print(e.response.dict())
        
    return product_id_dict
    
# This is not necessary
#def CompareWithMyListing(opts, other_listing_id, my_user_name):
#    
#    my_listing_id = FindUserActiveListing(opts, my_user_name)
#    new_listing_id = {}    
#    
#    for other_seller_title in other_listing_id.keys():
#        # Calculate accuracy score
#        score = 0
#        for my_title in my_listing_id.keys():
#            for other_word in other_seller_title.split():
#                for my_word in my_title.split():
#                    if other_word == my_word:
#                        score += 1
#        if other_listing_id[item] not in my_listing_id.values():
#            new_listing_id[item] = other_listing_id[item]
#            
#    return new_listing_id
    

def AddListingToEbay(result, product_id_dict, use_seller_image = True, drop_ship_from = "Amazon"): 
    
    for i in range(512,len(result)):
        original_title = result[i]["Title"]
        #description = ExtractHTML(result[i]['Description'])
        if original_title in product_id_dict.keys():
            description = result[i]['Description'] 
            soup = BeautifulSoup(description)
            main = str(soup.find('div',{'id':'l_mainimage'}))
            features = str(soup.find('div',{'class':'content'}))
            body = '<![CDATA[' + main + '<div class="contentSectionHG">&nbsp;</div>' + features + ']]>'
            if body != '''<![CDATA[]]>''':
                
                title = MakeItemTitle(result[i]["Title"])
                picture_url_list = []
                if type(result[i]['PictureDetails']['PictureURL']) != list:
                    picture_url_list.append(result[i]['PictureDetails']['PictureURL'])
                else:
                    picture_url_list = result[i]['PictureDetails']['PictureURL']
                
                regex = re.compile(r'(?=(.))(?:new|free shipping|free ship|f s)', flags=re.IGNORECASE)
                am_title = regex.sub('',title)

                MakeEmptyFolder(result[i])
                    
                # This one should be included in a separate scraper for Amazon
                # This is just a scraper for ebay
                if drop_ship_from == "Amazon":
                    try:
                        results = api.item_search('All', Keywords = am_title, Availability = 'Available', Condition = 'New', ResponseGroup = 'Images, Offers, ItemAttributes')
                        j = 0    
                        for item in results:
#                            picture_url_list = []
                            if j < 1:
                                amazon_asin = item.ASIN.text
#                                for k in item.ImageSets.ImageSet:
#                                    picture_url = k.LargeImage.URL.text
#                                    picture_url_list.append(picture_url)
                            j += 1
                    except:
                        amazon_asin = "not found"
                else:
                    amazon_asin = "NA"
                    
                if use_seller_image == True:                
                    ProcessPicture(picture_url_list, result[i])
                
                # Extract item field
                # Only add item that can be dropshipped from Amazon or in store
                price = float(result[i]['StartPrice']['value']) # What the hell is this?
                print "i =", i, " price =", price 
                if (amazon_asin != "not found") and (price <= 25):
                    myitem = {
                        "Item": {
                            "Title": title,
                            "Description": body,
                            "BuyItNowPrice": "0.0",
                            "BuyerGuaranteePrice": "20000",
                            "BuyerProtection": result[i]['BuyerProtection'],
                            "ConditionDisplayName": "Brand New",
                            "Currency": "USD",
                            "CategoryBasedAttributesPrefill": "true",
                            "CategoryMappingAllowed": "true",
                            "Country": "US",
                            "ConditionID": result[i]['ConditionID'],
                            "Currency": "USD",
                            "DispatchTimeMax": result[i]['DispatchTimeMax'],
                            "eBayPlus": "false",
                            "eBayPlusEligible": "false",
                            "GiftIcon": "0",
                            "HideFromSearch": "false",
                            "HitCounter": "NoHitCounter",
                            "Location": "Austin, Texas",
                            "LocationDefaulted": "true",
                            "ListingDuration": "GTC",
                            "ListingType": "FixedPriceItem",
                            "PostCheckoutExperienceEnabled": "false",
                            "PrivateListing": "false",
                            "ProxyItem": "false",
                            "PaymentMethods": "PayPal",
                            "PayPalEmailAddress": "longnguyen.qeb@gmail.com",
                            "PictureDetails": {
                                'GalleryType': 'Gallery',
                                'PhotoDisplay': 'PicturePack',
                                'PictureURL': result[i]['PictureDetails']['PictureURL']
                                },
                            "PostalCode": "78726",
                            "PrimaryCategory": {"CategoryID": result[i]['PrimaryCategory']['CategoryID']},
                            "Quantity": "1",
                            "ReturnPolicy": {
                                "ReturnsAcceptedOption": "ReturnsAccepted",
                                "RefundOption": "MoneyBack",
                                "ReturnsWithinOption": "Days_30",
                                "ShippingCostPaidByOption": "Buyer"
                            },
                            "ShippingPackageDetails": {
                                "PackageDepth": "1",
                                "PackageLength": "9",
                                "PackageWidth": "6",
                                "ShippingIrregular": "false",
                                "ShippingPackage": "PackageThickEnvelope",
                                "WeightMajor": "0",
                                "WeightMinor": "6"
                                },
                            "ShipToLocations": result[i]["ShipToLocations"],
                            "StartPrice": str(price - 1.0), # And this?
                            "ShippingDetails": {
                                "ShippingType": "Flat",
                                "ApplyShippingDiscount": "false",
                                "CalculatedShippingRate": {
                                        "WeightMajor": "0",
                                        "WeightMinor": "0"
                                        },
                                "ShippingServiceOptions": {
                                    "ExpeditedService": "false",
                                    "ShippingServicePriority": "1",
                                    "FreeShipping": "true",
                                    "ShippingService": "USPSFirstClass",
                                    "ShippingServiceCost": "0.0",
                                    "ShippingTimeMax": "6",
                                    "ShippingTimeMin": "2"
                                    },
                                "InsuranceDetails": {
                                    "InsuranceOption": "NotOffered"
                                    },
                                "InsuranceFee": "0.0",
                                "InsuranceOption": "NotOffered",
                                "InternationalInsuranceDetails": {
                                    "InsuranceOption": "NotOffered"
                                    },
                                "InternationalShippingDiscountProfileID" :"0",
                                "InternationalShippingServiceOption": {
                                    "ShipToLocation": "CA",
                                    "ShippingService": "USPSFirstClassMailInternational",
                                    "ShippingServiceCost": "6.0",
                                    "ShippingServicePriority": "1"
                                    },
                                "SalesTax": result[i]["ShippingDetails"]["SalesTax"],
                                "SellerExcludeShipToLocationsPreference": result[i]["ShippingDetails"]["SellerExcludeShipToLocationsPreference"],
                                "ShippingDiscountProfileID": result[i]["ShippingDetails"]["ShippingDiscountProfileID"],
                                "ThirdPartyCheckout": "false"
                                },
                            "Site": "US",
                            "ShippingTermsInDescription": "true"
                        }
                    }  
                    
                    ebay_api = sandbox_trading(debug=opts.debug, config_file=opts.yaml, appid=opts.appid,
                                  certid=opts.certid, devid=opts.devid, warnings=False)
                                  
                    picture_url = []
                    if type(myitem['Item']['PictureDetails']['PictureURL']) == list:
                        for j in range(len(myitem['Item']['PictureDetails']['PictureURL'])):
                            picture_file, picture_name = GetPictureFile(myitem['Item'], j)
                            picture_url.append(UploadPictures(opts, picture_file, picture_name))
                    else:
                        picture_file, picture_name = GetPictureFile(myitem['Item'], 0)
                        picture_url.append(UploadPictures(opts, picture_file, picture_name))
                        
                    # Update item details with uploaded picture url
                    if type(picture_url) == list:     
                        myitem['Item']['PictureDetails']['PictureURL'] = picture_url
                        myitem['Item']['PictureDetails']['GalleryURL'] = picture_url[0]
                    else:
                        myitem['Item']['PictureDetails']['PictureURL'] = picture_url
                        myitem['Item']['PictureDetails']['PictureURL'] = picture_url
                    try:
                        print "Adding: ", original_title
                        ebay_api.execute('AddItem', myitem)
                        dump(ebay_api)
                        
                    except ConnectionError as e:
                        print(e)
                        print(e.response.dict())


def ReadItemsNameFromDB():
    
    #dynamodb = boto3.resource('dynamodb', region_name='us-west-2', endpoint_url="http://localhost:8000")
    ebaytable = dynamodb.Table('EbayHomeGallery')
    
    pe = "Title"

    response = ebaytable.scan(
        ProjectionExpression=pe
        )
        
    for item in response['Items']:
        print item["Title"]
    
    while 'LastEvaluatedKey' in response:
        response = ebaytable.scan(
            ExclusiveStartKey=response['LastEvaluatedKey']
            )
    
    for item in response['Items']:
        print item["Title"]

    
def extract_item_for_testing(item_list, item_dict):
    
    with open("item_list.pkl", "w") as item_list_outfile:
        pickle.dump(item_list, item_list_outfile)
    with open("item_dict.pkl", "w") as item_dict_outfile:
        pickle.dump(item_dict, item_dict_outfile)    
        

def read_test_item():
    
    with open("item_list.pkl", "r") as item_list_file:
        item_list = pickle.load(item_list_file)
    with open("item_dict.pkl", "r") as item_dict_file:
        item_dict = pickle.load(item_dict_file)
        
    return item_list, item_dict
        
# Do later: scrape built-title.com to extract popular keywords
# Make ebay table a public object to pass into functions
 
def AddItem(opts):
    """http://www.utilities-online.info/xmltojson/#.UXli2it4avc
    """

    try:
        api = Trading(debug=opts.debug, config_file=opts.yaml, appid=opts.appid,
                      certid=opts.certid, devid=opts.devid, warnings=False)

        myitem = {
            "Item": {
                "Title": "Harry Potter and the Philosopher's Stone",
                "Description": "<![CDATA[HTML go here]]>",
                "PrimaryCategory": {"CategoryID": "377"},
                "StartPrice": "1.0",
                "CategoryMappingAllowed": "true",
                "Country": "US",
                "ConditionID": "3000",
                "Currency": "USD",
                "DispatchTimeMax": "3",
                "ListingDuration": "Days_7",
                "ListingType": "Chinese",
                "PaymentMethods": "PayPal",
                "PayPalEmailAddress": "long.nguyen@wolves.northern.edu",
                "PictureDetails": {
                    "PictureURL": "http://i.ebayimg.com/00/s/NzY4WDEwMjQ=/z/6S4AAOSw2x1XMFYY/$_12.JPG?set_id=880000500F"
                    },
                "PostalCode": "95125",
                "Quantity": "1",
                "ReturnPolicy": {
                    "ReturnsAcceptedOption": "ReturnsAccepted",
                    "RefundOption": "MoneyBack",
                    "ReturnsWithinOption": "Days_30",
                    "Description": "If you are not satisfied, return the book for refund.",
                    "ShippingCostPaidByOption": "Buyer"
                },
                "ShippingDetails": {
                    "ShippingType": "Flat",
                    "ShippingServiceOptions": {
                        "ShippingServicePriority": "1",
                        "ShippingService": "USPSMedia",
                        "ShippingServiceCost": "2.50"
                    }
                },
                "Site": "US"
            }
        }

        response = api.execute('AddItem', myitem)
        dump(api)
        
        return response.dict()

    except ConnectionError as e:
        print(e)
        print(e.response.dict())
        
        return e.response.dict()

  
if __name__ == "__main__":
    (opts, args) = init_options()
    
    # Get the service resource.

    print("Trading API Samples for version %s" % ebaysdk.get_version())
    
#    CreateEbayTable('EbayHomeGallery')
#    ebaytable = dynamodb.Table('EbayHomeGallery')
#    detailed_item_list, product_id_dict = read_test_item()
#    extract_item_for_testing(detailed_item_list, product_id_dict)
#    detailed_item_list = GetSellerListIn30Days(opts, 'lonestarsales*2016') # Items that are listed within a timeframe with details
#    product_id_dict = FindUserActiveListing(opts, 'lonestarsales*2016') # Product ID dictionary of items that are actively listed now
#    AddListingToEbay(detailed_item_list, product_id_dict)
#    for i in range(len(detailed_item_list)):
#        if detailed_item_list[i]['Title'] == "A&B Home Althea Hour Glass Stand, 6.2 X 12.5-Inch, White New":
#            test_item = detailed_item_list[i]
#    test_listing_id = {}
#    game_title = new_listing_id.keys()[:20]
#    for title in game_title:
#        test_listing_id[title] = new_listing_id[title] 
#    table = dynamodb.Table('EbayHomeGallery')
#    table.delete()
    
    # Later perform a call to get seller list of clickycatdeals to update shiptolocations

    