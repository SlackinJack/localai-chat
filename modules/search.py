import re
import requests

from duckduckgo_search import DDGS
from readability import Document

from modules.utils import *

##################################################
################## BEGIN SEARCH ##################
##################################################

def searchDDG(keywords, maxSources):
    hrefs = dict()
    index = 0
    while True:
        try:
            for result in DDGS().text(keywords, max_results=maxSources):
                hrefs[index] = result.get("href")
                index += 1
            break
        except:
            printDebug("Exception thrown while searching DuckDuckGo, trying again in 5 seconds...")
            time.sleep(5)
    return hrefs


# returns:
# str = website text
# None = failed to load website
def getInfoFromWebsite(websiteIn, bypassLength, maxSentences=0):
    website = requests.get(websiteIn)
    reader = Document(website.content)
    websiteText = reader.summary()
    websiteText = re.sub('<[^<]+?>', '', websiteText)
    websiteText = cleanupString(websiteText)
    # TODO: test this
    strJS = ["JavaScript", "JS", "browser", "enable"]
    matches = 0
    for s in strJS:
        if s in websiteText:
            matches += 1
    if matches >= 3:
        return None
    if not bypassLength:
        websiteText = splitBySentenceLength(websiteText, maxSentences)[0]
    return websiteText
