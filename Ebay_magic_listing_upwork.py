# -*- coding: utf-8 -*-
"""
Created on Sat May 07 01:44:32 2016

@author: Long Nguyen
"""

import os
import sys
from optparse import OptionParser

sys.path.insert(0, '%s/../' % os.path.dirname(__file__))

import MySQLdb

import ebaysdk
from finding import Connection as finding
from bs4 import BeautifulSoup

import time
import requests

import pickle
 

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

    
def TestUpwork(opts, category_id):
    
    # Get items specific details within a time frame

    api = finding(debug=opts.debug, appid=opts.appid, config_file=opts.yaml, warnings=True)
              
    callData = {'categoryId': [str(category_id)], 'outputSelector': 'CategoryHistogram'}

    response = api.execute('findItemsByCategory', callData).dict()
                  
    return response

  
if __name__ == "__main__":
    (opts, args) = init_options()
    
    # Get the service resource.

    print("Trading API Samples for version %s" % ebaysdk.get_version())
    
    result_list = []
    url_set = set()
    category_dict = {}
    error_log = []
    
    url = "http://pages.ebay.com/sellerinformation/news/categorychanges.html"
    
    response = requests.get(url)
    soup = BeautifulSoup(response.text)
    div_left = soup.findAll("div",{"class":"listleft"})
    li = div_left[1].findAll("li")
    for tag in li:
        a = tag.find("a")
        url_set.add(a['href'])
        
    div_right = soup.findAll("div",{"class":"listright"})
    li = div_right[1].findAll("li")
    for tag in li:
        a = tag.find("a")
        url_set.add(a['href'])
        
    url_list = list(url_set)
    for link in url_list:
        response = requests.get(link)
        soup = BeautifulSoup(response.text)
        try:
            table = soup.findAll("table",{"class":"catdata"})[1]
            tr = table.findAll("tr")
            td = tr[1].findAll("td")
            name = td[1].text
            cat_id = td[2].text
            category_dict[name] = cat_id
        except:
            error_log.append(link)
            continue
        time.sleep(2)
    
    for c in category_dict.keys():
        
        category_id = category_dict[c]
        response = TestUpwork(opts, category_id)
        count = response['categoryHistogramContainer']['categoryHistogram'][0]['count']
        temp = [c,category_id,count]
        result_list.append(temp)
        time.sleep(2)
  
    with open('result_list.pkl','wb') as out_file:
        pickle.dump(result_list, out_file)     
        
    mydb = MySQLdb.connect(host = 'upwork.crceifxif8gc.us-east-1.rds.amazonaws.com',
    port = 3306,
    user = "long",
    passwd = 'l0ngnguy3n',
    db = 'scraper'
    )
    
    cursor = mydb.cursor()
            
#    cursor.execute("TRUNCATE TABLE ebay_scrape")
#    mydb.commit()

    for result in result_list:
        inject = 'INSERT INTO ebay_scrape (category_id,category_name,count) VALUES (%s,"%s",%s)' % (result[1], result[0], result[2])
        cursor.execute(inject)
    
    mydb.commit()
    mydb.close()