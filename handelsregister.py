#!/usr/bin/env python3
"""
bundesAPI/handelsregister is the command-line interface for for the shared register of companies portal for the German federal states.
You can query, download, automate and much more, without using a web browser.
"""

import argparse
import mechanize
import re
import pathlib
import sys
import urllib.parse
from bs4 import BeautifulSoup

# Dictionaries to map arguments to values
schlagwortOptionen = {
    "all": 1,
    "min": 2,
    "exact": 3
}

class HandelsRegister:
    def __init__(self, args):
        self.args = args
        self.browser = mechanize.Browser()

        self.browser.set_debug_http(args.debug)
        self.browser.set_debug_responses(args.debug)
        # self.browser.set_debug_redirects(True)

        self.browser.set_handle_robots(False)
        self.browser.set_handle_equiv(True)
        self.browser.set_handle_gzip(True)
        self.browser.set_handle_refresh(False)
        self.browser.set_handle_redirect(True)
        self.browser.set_handle_referer(True)

        self.addheaders = [
            (
                "User-Agent",
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.5 Safari/605.1.15",
            ),
            (   "Accept-Language", "en-GB,en;q=0.9"   ),
            (   "Accept-Encoding", "gzip, deflate, br"    ),
            (
                "Accept",
                "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            ),
            (   "Connection", "keep-alive"    ),
        ]
        self.browser.addheaders = self.addheaders
        
        self.cachedir = pathlib.Path("cache")
        self.cachedir.mkdir(parents=True, exist_ok=True)

    def open_startpage(self):
        self.browser.open("https://www.handelsregister.de", timeout=10)

    def companyname2cachename(self, companyname):
        # map a companyname to a filename, that caches the downloaded HTML, so re-running this script touches the
        # webserver less often.
        return self.cachedir / companyname

    def search_company(self):
        print(f"{self.browser.cookiejar[0].value = }")
        self.addheaders.append(
            (   self.browser.cookiejar[0].name, self.browser.cookiejar[0].value)
        )
        self.browser.addheaders = self.addheaders

        cachename = self.companyname2cachename(self.args.schlagwoerter)
        if self.args.force==False and cachename.exists():
            with open(cachename, "r") as f:
                html = f.read()
                print("return cached content for %s" % self.args.schlagwoerter)
                return get_companies_in_searchresults(html)
            
        # TODO implement token bucket to abide by rate limit
        # Use an atomic counter: https://gist.github.com/benhoyt/8c8a8d62debe8e5aa5340373f9c509c7
        response_search = self.browser.follow_link(text="Advanced search")

        if self.args.debug == True:
            print(self.browser.title())

        self.browser.select_form(name="form")

        self.browser["form:schlagwoerter"] = self.args.schlagwoerter
        so_id = schlagwortOptionen.get(self.args.schlagwortOptionen)

        self.browser["form:schlagwortOptionen"] = [str(so_id)]

        response_result = self.browser.submit()
        print(f"{self.browser.cookiejar[0].value = }")

        if self.args.debug == True:
            print(self.browser.title())

        html = response_result.read().decode("utf-8")
        with open(cachename, "w") as f:
            f.write(html)

        # TODO catch the situation if there's more than one company?
        # TODO get all documents attached to the exact company
        
        if self.args.currentHardCopy:
            print('# trying to download AD')
            print(f"{self.browser.geturl() = }")
            # get sec ip for GET parameter
            sec_ip = re.search(r'sec_ip=([.0-9]+)"', html).group(1)
            url = f"https://www.handelsregister.de/rp_web/ergebnisse.xhtml?sec_ip={sec_ip}"
            # get identifier number for post
            id_nr = re.findall(r'selectedSuchErgebnisFormTable:0:j_idt(\d+):0:fade', html)[0]
            self.browser.select_form(name="ergebnissForm")
            select_str = f"ergebnissForm:selectedSuchErgebnisFormTable:0:j_idt{id_nr}:0:fade"
            req_data = self.browser.form.click_request_data()
            # req_data = req_data[:1] + ( req_data[1] + "&" + urllib.parse.quote(select_str),) + req_data[2:]
            req = mechanize.Request(url=req_data[0],
                                    data=req_data[1] + "&" + urllib.parse.quote(select_str))
            ad_response = self.browser.open(req)
            filepath = self.companyname2cachename(self.args.schlagwoerter + " AD.pdf")
            with open(filepath, "wb") as f:
                f.write(ad_response.read())
            print(f"{ad_response.geturl() = }")
            print(f"{self.browser.geturl() = }")
            self.browser.back()

        if self.args.chronologicalHardCopy:
            print('# trying to download CD')
            print(f"{self.browser.geturl() = }")
            # get identifier number for post
            id_nr = re.findall(r'selectedSuchErgebnisFormTable:0:j_idt(\d+):1:fade', html)[0]
            self.browser.select_form(name="ergebnissForm")
            select_str = f"ergebnissForm:selectedSuchErgebnisFormTable:0:j_idt{id_nr}:1:fade"
            # retrieve the data that would be sent if "click()"
            req_data = self.browser.form.click_request_data()
            # modify the request data: add the selection data
            # this data point is not included in the forms and seems to be JS magic
            # req_data = req_data[:1] + ( req_data[1] + "&" + urllib.parse.quote(select_str),) + req_data[2:]
            req = mechanize.Request(url=req_data[0],
                                    data=req_data[1] + "&" + urllib.parse.quote(select_str))
            ad_response = self.browser.open(req)
            filepath = self.companyname2cachename(self.args.schlagwoerter + " CD.pdf")
            with open(filepath, "wb") as f:
                f.write(ad_response.read())
            self.browser.back()

        if self.args.structuredContent:
            print('# trying to download HD')
            # get identifier number for post
            id_nr = re.findall(r'selectedSuchErgebnisFormTable:0:j_idt(\d+):2:fade', html)[0]
            self.browser.select_form(name="ergebnissForm")
            select_str = f"ergebnissForm:selectedSuchErgebnisFormTable:0:j_idt{id_nr}:2:fade"
            # retrieve the data that would be sent if "click()"
            req_data = self.browser.form.click_request_data()
            # modify the request data: add the selection data
            req = mechanize.Request(url=req_data[0],
                                    data=req_data[1] + "&" + urllib.parse.quote(select_str))
            ad_response = self.browser.open(req)
            filepath = self.companyname2cachename(self.args.schlagwoerter + " HD.pdf")
            with open(filepath, "wb") as f:
                f.write(ad_response.read())
            self.browser.back()
            
        if self.args.structuredContent:
            print('# trying to download SI')
            # get identifier number for post
            id_nr = re.findall(r'selectedSuchErgebnisFormTable:0:j_idt(\d+):6:fade', html)[0]
            self.browser.select_form(name="ergebnissForm")
            select_str = f"ergebnissForm:selectedSuchErgebnisFormTable:0:j_idt{id_nr}:6:fade"
            # retrieve the data that would be sent if "click()"
            req_data = self.browser.form.click_request_data()
            # modify the request data: add the selection data
            req = mechanize.Request(url=req_data[0],
                                    data=req_data[1] + "&" + urllib.parse.quote(select_str))
            ad_response = self.browser.open(req)
            filepath = self.companyname2cachename(self.args.schlagwoerter + " SI.xml")
            with open(filepath, "wb") as f:
                f.write(ad_response.read())
            self.browser.back()


        if self.args.downloadAllDocuments:
            print('# trying to download all files')



        # TODO parse useful information out of the PDFs
        search_results = get_companies_in_searchresults(html)

        return search_results


def parse_result(result):
    cells = []
    for cellnum, cell in enumerate(result.find_all('td')):
        #print('[%d]: %s [%s]' % (cellnum, cell.text, cell))
        cells.append(cell.text.strip())
    #assert cells[7] == 'History'
    d = {}
    d['court'] = cells[1]
    d['name'] = cells[2]
    d['state'] = cells[3]
    d['status'] = cells[4]
    d['documents'] = cells[5] # todo: get the document links    

    d['history'] = []
    hist_start = 8
    hist_cnt = (len(cells)-hist_start)/3
    for i in range(hist_start, len(cells), 3):
        d['history'].append((cells[i], cells[i+1])) # (name, location)
    #print('d:',d)
    return d

def pr_company_info(c):
    # for tag in ('name', 'court', 'state', 'status'):
    for tag in ('name', 'court'):
        print('%s: %s' % (tag, c.get(tag, '-')))
    print('history:')
    for name, loc in c.get('history'):
        print(name, loc)

def get_companies_in_searchresults(html):
    soup = BeautifulSoup(html, 'html.parser')
    grid = soup.find('table', role='grid')
    #print('grid: %s', grid)
  
    results = []
    for result in grid.find_all('tr'):
        a = result.get('data-ri')
        if a is not None:
            index = int(a)
            #print('r[%d] %s' % (index, result))
            d = parse_result(result)
            results.append(d)
    return results

def parse_args():
# Parse arguments
    parser = argparse.ArgumentParser(description='A handelsregister CLI')
    parser.add_argument(
                          "-d",
                          "--debug",
                          help="Enable debug mode and activate logging",
                          action="store_true"
                        )
    parser.add_argument(
                          "-f",
                          "--force",
                          help="Force a fresh pull and skip the cache",
                          action="store_true"
                        )
    parser.add_argument(
                          "-s",
                          "--schlagwoerter",
                          help="Search for the provided keywords",
                          required=True,
                          default="Gasag AG" # TODO replace default with a generic search term
                        )
    parser.add_argument(
                          "-so",
                          "--schlagwortOptionen",
                          help="Keyword options: all=contain all keywords; min=contain at least one keyword; exact=contain the exact company name.",
                          choices=["all", "min", "exact"],
                          default="all"
                        )
    parser.add_argument(
                          "-ad",
                          "--currentHardCopy",
                          help="Download the 'Aktueller Abdruck'.",
                          action="store_true"
                        )
    parser.add_argument(
                          "-cd",
                          "--chronologicalHardCopy",
                          help="Download the 'Chronologischer Abdruck'.",
                          action="store_true"
                        )
    parser.add_argument(
                          "-hd",
                          "--historicalHardCopy",
                          help="Download the 'Historischer Abdruck'.",
                          action="store_true"
                        )
    parser.add_argument(
                          "-si",
                          "--structuredContent",
                          help="Download the structured content as XML file.",
                          action="store_true"
                        )
    parser.add_argument(
                          "-docs",
                          "--downloadAllDocuments",
                          help="Download all documents in the documents view.",
                          action="store_true"
                        )
    # args = parser.parse_args()
    # manually set args for enabling interactive mode
    args = parser.parse_args(['-s', 'hotel st georg knerr', '-so', 'all', '-ad', '-cd', '-si', '-f', '-d'])

    # Enable debugging if wanted
    if args.debug == True:
        import logging
        logger = logging.getLogger("mechanize")
        logger.addHandler(logging.StreamHandler(sys.stdout))
        logger.setLevel(logging.DEBUG)

    return args

if __name__ == "__main__":
    args = parse_args()
    print(f"{args = }")
    h = HandelsRegister(args)
    h.open_startpage()
    self = h # for Interactive Mode 
    companies = h.search_company()
    if companies is not None:
        for c in companies:
            pr_company_info(c)

