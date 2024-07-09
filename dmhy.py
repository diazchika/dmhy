#VERSION: 1.00

import re
from enum import Enum
from html.parser import HTMLParser
from helpers import (
    # download_file,
    retrieve_url,
)
from novaprinter import prettyPrinter

ENGINE_BASEURL = 'http://dmhy.org'
MAGNET_PATTERN = r'magnet:\?xt=urn:btih:[a-zA-Z0-9]*'


class TableHeader(Enum):
    Title = 3
    Maglink = 4
    Size = 5
    Seeder = 6
    Leech = 7


class dmhy(object):
    """
    `url`, `name`, `supported_categories` should be static variables of the engine_name class,
     otherwise qbt won't install the plugin.

    `url`: The URL of the search engine.
    `name`: The name of the search engine, spaces and special characters are allowed here.
    `supported_categories`: What categories are supported by the search engine and their
    corresponding id, possible categories are ('all', 'anime', 'books', 'games', 'movies',
    'music', 'pictures', 'software', 'tv').
    """
    url = ENGINE_BASEURL
    name = 'dmhy'
    supported_categories = {
        'all': '0',
    }

    class DmhyParser(HTMLParser):

        def __init__(self, outer_class):
            super().__init__()
            self.outer_class = outer_class
            self.in_table = False
            self.in_tbody = False
            self.in_row = False
            self.in_cell_num = 0
            self.in_cell = False
            self.result_dict = {}

        def handle_starttag(self, tag, attrs):

            # Find the table that contains the search results
            # The table has an id of "topic_list"
            if tag == 'table':
                for attr in attrs:
                    if attr[0] == 'id' and attr[1] == "topic_list":
                        self.in_table = True
                        return

            if tag == 'tbody' and self.in_table:
                self.in_tbody = True
                return

            # Find the rows in the table and initialize the result_dict
            if tag == 'tr' and self.in_tbody:
                self.in_row = True
                self.in_cell_num = 0
                self.result_dict = {
                    "link": "-1",
                    "name": "",
                    "size": "-1",
                    "seeds": "-1",
                    "leech": "-1",
                    "engine_url": ENGINE_BASEURL,
                    "desc_link": "-1",
                }
                return

            # Find the cells in the row. Keep track of the cell number
            if tag == 'td' and self.in_row:
                self.in_cell_num += 1
                self.in_cell = True
                return

            # The anchor tag in the third cell contains the page url.
            # Save page url into the dictionary, and retrieve the page to get the magnet link
            # Also save the magnet link into the dictionary
            if tag == 'a' and self.in_cell_num == TableHeader.Title.value:
                for attr in attrs:
                    if attr[0] == 'href':
                        self.result_dict["desc_link"] = ENGINE_BASEURL + attr[1]
                        return

            # Only the first (of two) anchor tag in the fourth cell contains the magnet link
            # So a regular expression check is performed to make sure it is a magnet link
            if tag == 'a' and self.in_cell_num == TableHeader.Maglink.value:
                for attr in attrs:
                    if attr[0] == 'href' and re.match(MAGNET_PATTERN, attr[1]):
                        self.result_dict["link"] = attr[1]

        def handle_data(self, data):
            # The third cell contains the name of the torrent,
            # but it may be split into multiple parts. Concatenate them.
            if self.in_cell and self.in_cell_num == TableHeader.Title.value:
                self.result_dict["name"] += re.sub(r"[\t\n]", "", data)
                return

            # The fourth cell contains the size of the torrent
            # Safe to use as is.
            if self.in_cell and self.in_cell_num == TableHeader.Size.value:
                self.result_dict["size"] = data
                return

            # The sixth cell contains the number of seeders
            # This data is not always available, so check for a dash
            if self.in_cell and self.in_cell_num == TableHeader.Seeder.value and data != '-':
                self.result_dict["seeds"] = data
                return

            # The seventh cell contains the number of leech
            # Same as the seeders, check for a dash
            if self.in_cell and self.in_cell_num == TableHeader.Leech.value and data != '-':
                self.result_dict["leech"] = data
                return

        def handle_endtag(self, tag):
            # Reset the cell flag when the cell ends
            if tag == 'td' and self.in_cell:
                self.in_cell = False
                return

            # Reset the row and cell flags when the row ends
            if tag == 'tr' and self.in_row:
                self.in_row = False
                self.in_cell_num = 0

                # It may happen that a magnet link is not directly available from the table
                # In that case, th description page is retrieved to get the magnet link
                if self.result_dict["link"] == "-1":
                    page = retrieve_url(self.result_dict["desc_link"])
                    magnet_links = re.findall(MAGNET_PATTERN, page)
                    self.result_dict["link"] = magnet_links[0]

                self.outer_class.result_dicts.append(self.result_dict)
                return

            # Reset the tbody flag when the tbody ends
            if tag == 'tbody' and self.in_tbody:
                self.in_tbody = False
                return

            # Reset the table flag when the table ends
            if tag == 'table' and self.in_table:
                self.in_table = False
                return

    def __init__(self):
        """
        Some initialization
        """
        self.result_dicts = []

    # def download_torrent(self, info):
    #     """
    #     Providing this function is optional.
    #     It can however be interesting to provide your own torrent download
    #     implementation in case the search engine in question does not allow
    #     traditional downloads (for example, cookie-based download).
    #     """
    #     print(download_file(info))

    # DO NOT CHANGE the name and parameters of this function
    # This function will be the one called by nova2.py
    def search(self, what, cat='all'):
        """
        Here you can do what you want to get the result from the search engine website.
        Everytime you parse a result line, store it in a dictionary
        and call the prettyPrint(your_dict) function.

        `what` is a string with the search tokens, already escaped (e.g. "Ubuntu+Linux")
        `cat` is the name of a search category in ('all', 'anime', 'books', 'games',
        'movies', 'music', 'pictures', 'software', 'tv')
        """

        # Loop through all the pages of the search results
        search_url = f"http://dmhy.org/topics/list?keyword={what}"
        while True:
            # Retrieve the page and feed it to the parser.
            result_page = retrieve_url(search_url)
            parser = self.DmhyParser(outer_class=self)
            parser.feed(result_page)

            # Use regular expression to find out if there is a next page
            # If there is, update the search_url and continue the loop
            # If there is no next page, break the loop
            pattern = fr'<a\s+href="/topics/list/page/(\d+)\?keyword={re.escape(what)}">下一頁</a>'
            match = re.search(pattern, result_page)
            if match:
                search_url = f"http://dmhy.org/topics/list/page/{match.group(1)}?keyword={what}"
                continue
            else:
                break

        # Sort the results by the number# of seeds, and print them
        self.result_dicts.sort(key=lambda x: int(x["seeds"]), reverse=True)
        for result_dict in self.result_dicts:
            prettyPrinter(result_dict)
