import re
import requests
import signal
import time

from duckduckgo_search import DDGS
from readability import Document

from modules.utils import *


##################################################
################## BEGIN SEARCH ##################
##################################################


def getSearchResponse(keywords, maxSources):
    printDebug("Search term(s):\n" + keywords)
    responseText = ""
    responseSources = ""
    sources = searchDDG(keywords, maxSources)
    printDebug("Target links:\n" + str(sources))
    sourceMap = {}
    # index = [href, webtext]
    for key in sources:
        websiteText = getInfoFromWebsite(sources[key], False, maxSources)
        sourceMap[key] = [sources[key], websiteText]
        if websiteText is not None:
            printDebug("[" + str(key) + "] " + websiteText)
            responseText += "[" + websiteText + "]"
    printDebug("Generating response with sources...")
    websiteTextsAvailable = len(sourceMap)
    for entry, value in sourceMap.items():
        if value[1] is None:
            websiteTextsAvailable -= 1
        else:
            responseText += value[1]
    if websiteTextsAvailable < 1:
        printInfo("No sources compiled - the reply will be completely generated!")
    else:
        responseSources += "Sources considered:\n"
        for key, value in sourceMap.items():
            if value[1] is not None:
                responseSources += "[" + str(key + 1) + "] '" + value[0] + "\n"
    return [responseText, responseSources]


def searchDDG(keywords, maxSources):
    hrefs = dict()
    index = 0
    tries = 0
    while True:
        try:
            for result in DDGS().text(keywords, max_results=maxSources):
                hrefs[index] = result.get("href")
                index += 1
            break
        except:
            if tries >= 5:
                printError("Couldn't load DuckDuckGo after 5 tries! Aborting search.")
                return ""
            else:
                printError("Exception thrown while searching DuckDuckGo, trying again in 5 seconds...")
                time.sleep(5)
                tries += 1
    return hrefs


jsErrors = [
        "JavaScript",
        "JS",
        "browser",
        "enable",
]

blockedErrors = [
        "Access Denied",
        "You don't have permission to access",
        "403 - Forbidden", "Access to this page is forbidden",
        "Why have I been blocked?",
        "This website is using a security service to protect itself from online attacks.",
]

def getInfoFromWebsite(websiteIn, bypassLength, maxSentences=0):
    printDebug("Getting text from: " + websiteIn)
    websiteText = ""
    try:
        website = requests.get(websiteIn, timeout=15)
        if website.status_code != 200:
            raise Exception("Status code is not 200.")
    except:
        printError("Failed to load the website!")
        return ""
    reader = Document(website.content)
    websiteText = reader.summary()
    websiteText = re.sub('<[^<]+?>', '', websiteText)
    websiteText = cleanupString(websiteText)
    matchJS = 0
    for s in jsErrors:
        if s in websiteText:
            matchJS += 1
    if matchJS >= 3:
        printError("Website failed JS test!")
        return ""
    for e in blockedErrors:
        if e in websiteText:
            printError("Website failed error test!")
            return ""
    if not bypassLength and maxSentences > 0:
        return trimTextBySentenceLength(websiteText, maxSentences)
    else:
        return websiteText
