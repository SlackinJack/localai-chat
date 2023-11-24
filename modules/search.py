import re
import requests
import time

from duckduckgo_search import DDGS
from readability import Document

from modules.utils import *

##################################################
################## BEGIN SEARCH ##################
##################################################

def getSearchResponse(keywords, maxSources):
    responseText = ""
    responseSources = ""
    printDebug("Generated serach term(s): " + keywords)
    sources = searchDDG(keywords, maxSources)
    websiteTexts = ""
    printDebug("Target links: " + str(sources))
    for key in sources:
        websiteText = getInfoFromWebsite(sources[key], False, maxSources)
        printDebug("[" + str(key + 1) + "] " + websiteText)
        websiteTexts += "[" + websiteText + "]"
    printDebug("Generating response with sources...")
    if len(websiteTexts) < 1:
        printWarning("No sources compiled - the reply will be completely generated!")
    responseText = websiteTexts
    if len(websiteTexts) >= 1:
        responseSources += "Sources considered:\n"
        for key in sources:
            responseSources += "[" + str(key + 1) + "] '" + sources[key] + "\n"
    return [responseText, responseSources]

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
            printWarning("Exception thrown while searching DuckDuckGo, trying again in 5 seconds...")
            time.sleep(5)
    return hrefs


# returns:
# str = website text
# None = failed to load website
def getInfoFromWebsite(websiteIn, bypassLength, maxSentences=0):
    printDebug("Getting text from: " + websiteIn)
    websiteText = ""
    try:
        website = requests.get(websiteIn)
        reader = Document(website.content)
        websiteText = reader.summary()
        websiteText = re.sub('<[^<]+?>', '', websiteText)
        websiteText = cleanupString(websiteText)
    except:
        printWarning("Failed to load the website!")
        return None
    # TODO: test this
    strJS = ["JavaScript", "JS", "browser", "enable"]
    matchJS = 0
    for s in strJS:
        if s in websiteText:
            matchJS += 1
    if matchJS >= 3:
        printWarning("Website failed JS test!")
        return None
    # TODO: test this
    errors = ["Access Denied", "You don't have permission to access", "403 - Forbidden", "Access to this page is forbidden", "Why have I been blocked?", "This website is using a security service to protect itself from online attacks."]
    for e in errors:
        if e in websiteText:
            printWarning("Website failed error test!")
            return None
    if not bypassLength:
        websiteText = splitBySentenceLength(websiteText, maxSentences)[0]
    return websiteText
