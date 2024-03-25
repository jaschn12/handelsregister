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
import logging
import copy

class DownloadedFile:
    def __init__(self, filename : str = "", content : bytes = None) -> None:
        self.filename = filename
        self.content = content 
    def __str__(self) -> str:
        return f"{len(self.content) : 10} Byte -> {self.filename}"
    def save_file(self, company_name : str):
        pass

class SearchResult:
    def __init__(self, name:str="", court:str="", city:str="", status:str="") -> None:
        self.name = name 
        self.court = court
        self.city = city
        self.status = status
        self.history : list[dict] = [] # {'name' : ... , 'location' : ...}
        self.documents : list[DownloadedFile] = []
    
    def __str__(self) -> str:
        history_strings = []
        for d in self.history:
            history_strings.append(f"{d['name']} @ {d['location']}")
        return f"""
        name: {self.name}
        court: {self.court}
        city: {self.city}
        status: {self.status}
        history: {(chr(10)+"           ").join([s for s in history_strings])}
        documents: {(chr(10)+"           ").join([str(d) for d in self.documents])}
        """.strip()
    
    def toDict(self) -> dict:
        "convert to dict for export"
        d = {
            'name' : self.name,
            'court' : self.court,
            'city' : self.city,
            'status' : self.status,
            'history' : self.history,
            'documents' : [
                {
                    'filename' : d.filename,
                    'length' : len(d.content)
                }
                for d in self.documents
            ]
        }
        return d


# Dictionaries to map arguments to values
schlagwortOptionen = {
    "all": 1,
    "min": 2,
    "exact": 3
}

class HandelsRegister:
    "class for handling the web traffic"
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
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            ),
            (
                "Accept",
                "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            ),
            (
                "Cache-Control", "no-cache",
            ),
            (   "Accept-Language", "de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7"   ),
            (   "Accept-Encoding", "gzip, deflate, br, zstd"    ),
            (
                "Accept", "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            ),
            (   "Connection", "keep-alive"    ),
        ]
        self.browser.addheaders = self.addheaders
        
        self.downloaddir = pathlib.Path("downloads")
        self.downloaddir.mkdir(parents=True, exist_ok=True)
        self.cachedir = pathlib.Path("cache")
        self.cachedir.mkdir(parents=True, exist_ok=True)

    def open_startpage(self):
        # 3 retries
        for _ in range(3):
            try: 
                self.browser.open("https://www.handelsregister.de", timeout=30)
            except: 
                logging.info(f"could not open start page, retry")
                continue
            else:
                return
        logging.error(f"could not open start page, abort.")
        

    def companyname2cachename(self, companyname):
        # map a companyname to a filename, that caches the downloaded HTML, so re-running this script touches the
        # webserver less often.
        return self.cachedir / companyname 
    def companyname2downloadname(self, companyname, filename):
        (self.cachedir / companyname).mkdir(parents=True, exist_ok=True)
        return self.cachedir / companyname / filename
    
    def getDocumentFromSearchResult(self, type:str, id_nr : str, browser: mechanize.Browser, 
                                        row_index : int, company : SearchResult) -> None:
            "Append the given 'company' object with a document from the search result page"
            type2col = {
                "AD" : 0,
                "CD" : 1,
                "HD" : 2,
                "SI" : 6
            }
            if type not in type2col: 
                logging.error(f"getDocumentFromSearchResult: Wrong Document given. Got {type}, expected one of {type2col.keys()}")
                return None
            logging.info(f'# trying to download {type}')
            logging.info(f"{browser.geturl() = }")

            browser.select_form(name="ergebnissForm")
            select_str = f"ergebnissForm:selectedSuchErgebnisFormTable:{row_index}:j_idt{id_nr}:{type2col[type]}:fade"
            req_data = browser.form.click_request_data()
            # retrieve the data that would be sent if "click()"
            req = mechanize.Request(url=req_data[0],
                                    data=req_data[1] + "&" + urllib.parse.quote(select_str))
            response = browser.open(req)
            if response.code != 200: 
                return None
            re_finding = re.search(r'filename="(.*?)"', response.get('Content-Disposition', default="file"))
            if not re_finding: 
                return None
            filename = re_finding.group(1)
            # filepath = self.companyname2downloadname(' '.join((company.court, company.name)), filename)
            content = response.read()
            # with open(filepath, "wb") as f:
            #     f.write(content)
            company.documents.append(DownloadedFile(filename=filename, content=content))
            
            logging.info(f"{response.geturl() = }")
            browser.back()

    def getDocsFromDocsPage(self, browser: mechanize.Browser, id_nr : str, row_index : int, 
                                    company : SearchResult) -> int:
        """Download all the Documents from documents page
        Append the given searchResult object
        returns: number of documents downloaded"""
        logging.info('# trying to download all files')
        resp = browser.open("https://www.handelsregister.de/rp_web/ergebnisse.xhtml", timeout=30)
        if resp.code != 200: 
            logging.error(f"could not open {resp=}")
            return 0
        browser.select_form(name="ergebnissForm")
        select_str = f"ergebnissForm:selectedSuchErgebnisFormTable:{row_index}:j_idt{id_nr}:3:fade"
        # retrieve the data that would be sent if "click()"
        req_data = browser.form.click_request_data()
        # modify the request data: add the selection data
        req = mechanize.Request(url=req_data[0],
                                data=req_data[1] + "&" + urllib.parse.quote(select_str))
        docs_response = browser.open(req)
        if docs_response.code != 200: 
            logging.error(f"could not open {req=}")
            return 0
        html_docs = docs_response.read()
        
        logging.debug(f"{self.browser.geturl() = }")
        browser.select_form(name="dk_form")
        select = browser.form.click()
        # self.browser.back()
        # # url
        # ('https://www.handelsregister.de/rp_web/documents-dk.xhtml',
        # # data
        # 'dk_form=dk_form&
        # javax.faces.ViewState=-1141088860331291924%3A-1787642681138421298&
        # dk_form%3Adktree_selection=&
        # dk_form%3Adktree_scrollState=0%2C0',
        # # header
        # [('Content-Type', 'application/x-www-form-urlencoded')])
        
        re_finding = re.search(r'javax.faces.ViewState=(.*?)&', 
                               urllib.parse.unquote(str(select.get_data())))
        if not re_finding: 
            logging.error(f"could not find view state id in {select.get_data()=}")
            return 0
        view_state = re_finding.group(1)
        tree_ids = re.findall(r'<li id="dk_form:dktree:(.*?)"', html_docs.decode())
        names = re.findall(r'role="treeitem">(.*?)</span>', html_docs.decode())
        if len(tree_ids) != len(names):
            logging.error(f"{len(tree_ids)=} != {len(names)=}")
            return 0
        downloadable = { id : False for id in tree_ids}
        index = 1
        if len(tree_ids) <= index: 
            logging.error(f"getDocsFromDocsPage @ {self.browser.geturl() = }: len(tree_ids) <= index")
            return 0

        def create_request(view_state, instant_selection, tree_selection):
            return mechanize.Request(url="https://www.handelsregister.de/rp_web/documents-dk.xhtml", 
                                    data = {
                                        'javax.faces.partial.ajax': 'true',
                                        'javax.faces.source': 'dk_form:dktree',
                                        'javax.faces.partial.execute': 'dk_form:dktree',
                                        'javax.faces.partial.render': 'dk_form:detailsNodePanelGrid dk_form:dktree',
                                        'javax.faces.behavior.event': 'select',
                                        'javax.faces.partial.event': 'select',
                                        'dk_form:dktree_instantSelection': instant_selection,
                                        'dk_form': 'dk_form',
                                        'javax.faces.ViewState': view_state,
                                        'dk_form:dktree_selection': tree_selection,
                                        'dk_form:dktree_scrollState': '0,0'
                                    }
                                    # , headers=
                                    )
        
        while len(tree_ids) > index:
            # send a new response 
            instant_selection = tree_ids[index] # "0_0_0_0"
            tree_selection = tree_ids[index] # "0_0_0_0"
            req = create_request(view_state, instant_selection, tree_selection)
            resp = browser.open(req)
            if resp.code != 200: 
                return 0
            resp_data = resp.read()

            # get file name
            names = re.findall(r'role="treeitem">(.*?)</span>', resp_data.decode())
            if not names: 
                logging.error(f"could not find file name")
                return 0

            # check if folder
            download_disabled = resp_data.decode().find(
                'onclick="" type="submit" disabled="disabled">') != -1
            # downloadable.append(not download_disabled)
            downloadable.update({tree_ids[index] : not download_disabled})

            # update loop values
            tree_ids = re.findall(r'<li id="dk_form:dktree:(.*?)"', resp_data.decode())
            index += 1

        # result:
            # tree_ids = ['0', '0_0', ... ]
            # downloadable = ['Documents on legal entity', 'Documents on register number', ... ]
            # downloadable = {'0': False, '0_0': False, ... }

        to_download = [id for id in tree_ids if downloadable[id]]
        for id in to_download:
            req = create_request(view_state, id, id)
            resp = browser.open(req)
            if resp.code != 200: 
                continue
            resp_str = resp.read().decode()
            re_findings = re.findall(r'<button id="dk_form:j_idt(\d*?)" name="dk_form:j_idt(\d*?)" class="ui-button ui-widget ui-state-default ui-corner-all ui-button-text-only" onclick="" type="submit">',
                        resp_str)
            if re_findings == []: 
                logging.error(f"could not find j_id (e.g. 0_0_1) in {resp}")
                continue
            if re_findings[0] == []: 
                logging.error(f"could not find j_id (e.g. 0_0_1) in {resp}")
                continue
            j_id = re_findings[0][0]
            download_req = mechanize.Request(
                url = 'https://www.handelsregister.de/rp_web/documents-dk.xhtml',
                data= {
                    'dk_form': 'dk_form',
                    'javax.faces.ViewState': view_state,
                    'dk_form:dktree_selection': id,
                    'dk_form:dktree_scrollState': '0,0',
                    'dk_form:radio_dkbuttons': 'false', # true if download as zip
                    f'dk_form:j_idt{j_id}': ''
                }
            )
            download_resp = browser.open(download_req)
            if download_resp.code != 200: 
                continue
            if not "attachment;" in download_resp.get('Content-Disposition', default=""):
                logging.error(f"{j_id=}: could not find 'attachment;' in {download_resp}")
                continue
            re_findings = re.search(r'filename="(.*?)"', download_resp.get('Content-Disposition', default="file"))
            if not re_findings: 
                logging.error(f"{j_id=}:could not find filename in {download_resp}")
                continue
            filename = re_findings.group(1)
            download_data = download_resp.read()
            # filepath = self.companyname2cachename(' '.join(self.args.schlagwoerter), filename)
            company.documents.append(DownloadedFile(filename=filename, 
                                                    content=download_data))
        return len(to_download)


    def search_companies(self) -> list[SearchResult]:
        companies : list[SearchResult] = []
        if not self.browser.cookiejar:
            return []
        logging.debug(f"{self.browser.cookiejar[0].value = }")
        self.addheaders.append(
            (   self.browser.cookiejar[0].name, self.browser.cookiejar[0].value)
        )
        self.browser.addheaders = self.addheaders

        cachename = self.companyname2cachename(' '.join(self.args.schlagwoerter))
        # if self.args.force==False and cachename.exists():
        #     with open(cachename, "r") as f:
        #         html = f.read()
        #         print("return cached content for %s" % ' '.join(self.args.schlagwoerter))
        #         return get_companies_in_searchresults(html)
            
        # TODO implement token bucket to abide by rate limit
        # Use an atomic counter: https://gist.github.com/benhoyt/8c8a8d62debe8e5aa5340373f9c509c7
        response_search = self.browser.follow_link(text="Erweiterte Suche")
        search_page_html = response_search.read().decode("utf-8")

        if self.args.debug == True:
            logging.debug(self.browser.title())

        self.browser.select_form(name="form")

        self.browser["form:schlagwoerter"] = ' '.join(self.args.schlagwoerter)
        so_id = schlagwortOptionen.get(self.args.schlagwortOptionen)

        self.browser["form:schlagwortOptionen"] = [str(so_id)]

        if self.args.registerNummer:
            nr_str = "" 
            for substr in self.args.registerNummer:
                if substr.isnumeric(): nr_str = nr_str + substr
            logging.info(f"{nr_str=}")
            self.browser["form:registerNummer"] = nr_str
        if self.args.registerGericht:
            # optionen finden
            soup = BeautifulSoup(search_page_html, 'html.parser')
            gerichte_inputs = soup.find(id='form:registergericht_input')
            gericht2ID = {
                str(o.text).lower().strip() : o['value'] 
                for o in gerichte_inputs.select('option') if o.get('value')
            }
            gericht_str = (" ".join(self.args.registerGericht)).lower().strip()
            if gericht_str not in gericht2ID:
                raise ValueError(f"specified register court {self.args.registerGericht} is invalid")
            self.browser["form:registergericht_input"] = [gericht2ID[gericht_str]]

        response_result = self.browser.submit()
        logging.debug(f"{self.browser.cookiejar[0].value = }")

        if self.args.debug == True:
            logging.debug(self.browser.title())

        html = response_result.read().decode("utf-8")
        with open(cachename, "w") as f:
            f.write(html)

        # from get_companies_in_searchresults:
        soup = BeautifulSoup(html, 'html.parser')
        grid = soup.find('table', role='grid')
        #print('grid: %s', grid)

        id_nrs_found = re.findall(r'selectedSuchErgebnisFormTable:0:j_idt(\d+):0:fade', html)
        if not id_nrs_found: 
            logging.info(f"no id_nr found in {html}")
            return []
        id_nr = id_nrs_found[0]

        for table_row in grid.find_all('tr'):
            index_str = table_row.get('data-ri')
            if index_str is None: 
                continue
            #print('r[%s] %s' % (index_str, result))
            company = parse_result(table_row)
            if not company: 
                logging.info(f"could not create a search result object @ {index_str=}")
                continue
            
            companies.append(company)

        
            if self.args.currentHardCopy:
                self.getDocumentFromSearchResult(type="AD", id_nr=id_nr, browser=self.browser, row_index=len(companies)-1, company=company)
            if self.args.chronologicalHardCopy:
                self.getDocumentFromSearchResult(type="CD", id_nr=id_nr, browser=self.browser, row_index=len(companies)-1, company=company)
            if self.args.historicalHardCopy:
                self.getDocumentFromSearchResult(type="CD", id_nr=id_nr, browser=self.browser, row_index=len(companies)-1, company=company)
            if self.args.structuredContent:
                self.getDocumentFromSearchResult(type="SI", id_nr=id_nr, browser=self.browser, row_index=len(companies)-1, company=company)
            
            if self.args.downloadAllDocuments:
                # copy the browser object so that self.browser remains in the same state
                self.getDocsFromDocsPage(browser=copy.copy(self.browser), id_nr=id_nr, row_index=len(companies)-1, company=company)         

        return companies



def parse_result(html) -> SearchResult | None:
    cells = []
    for cellnum, cell in enumerate(html.find_all('td')):
        cells.append(cell.text.strip())
    #assert cells[7] == 'History'
    if len(cells) < 4:
        logging.error(f"found only {len(cells)} cells in search result html: {html[:200]} ...")
        return None
    search_result = SearchResult(
        court = cells[1],
        name = cells[2],
        city = cells[3],
        status = cells[4]
    )
    # d['documents'] = cells[5] # todo: get the document links    
    hist_start = 8
    hist_cnt = (len(cells)-hist_start)/3
    for i in range(hist_start, len(cells)-1, 3):
        search_result.history.append({'name' : cells[i], 
                                      'location' : cells[i+1]}) # (name, location)
    #print('d:',d)
    return search_result

def parse_args(args_string = None):
    # Parse arguments
    parser = argparse.ArgumentParser(description='A handelsregister CLI')
    parser.add_argument(
                          "-d",
                          "--debug",
                          help="Enable debug mode and activate logging",
                          action="store_true"
                        )
    parser.add_argument(
                          "-i",
                          "--info",
                          help="Enable info mode and activate logging",
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
                          nargs='+',
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
                          "-nr",
                          "--registerNummer",
                          help="Search for the provided register number",
                          nargs='+'
                        )
    parser.add_argument(
                          "-gericht",
                          "--registerGericht",
                          help="Search for the provided register court",
                          nargs='+'
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
    if args_string:
        args = parser.parse_args(re.split(r'\s+', args_string))
    else:
        args = parser.parse_args()
    # manually set args for enabling interactive mode

    # Enable debugging if wanted
    if args.debug == True:
        logger = logging.getLogger("mechanize")
        logger.addHandler(logging.StreamHandler(sys.stdout))
        logger.setLevel(logging.DEBUG)
        logging.basicConfig(level=logging.DEBUG)
    elif args.info == True:
        logger = logging.getLogger("mechanize")
        logger.addHandler(logging.StreamHandler(sys.stdout))
        logger.setLevel(logging.INFO)
        logging.basicConfig(level=logging.INFO)
    return args

if __name__ == "__main__":
    args = parse_args()
    #args = parse_args('-s fieldfisher -gericht Berlin (Charlottenburg) -nr HRB 248027 -d')
    logging.debug(f"{args = }")
    h = HandelsRegister(args)
    h.open_startpage()
    self = h # for Python Interactive Mode 
    companies = h.search_companies()
    if not companies: 
        print("No companies matching your search")
    else: 
        for company in companies:
            print(company, end='\n\n')
