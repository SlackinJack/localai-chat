import re
import requests
import time

from duckduckgo_search import DDGS
from readability import Document
from youtube_transcript_api import YouTubeTranscriptApi

from modules.utils import *


##################################################
################## BEGIN SEARCH ##################
##################################################


def getSearchResponse(keywords, maxSources, maxSentences):
    printDebug("Search term(s):\n" + keywords)
    searchResults = {} #href, text
    sources = searchDDG(keywords, maxSources)
    printDebug("Target links:")
    for href in sources:
        printDebug("   - " + href)
    for href in sources:
        websiteText = getInfoFromWebsite(href, False, maxSentences)
        if len(websiteText) > 0:
            searchResults[href] = websiteText
    if len(searchResults) == 0:
        printError("No sources were compiled!")
    return searchResults


def searchDDG(keywords, maxSources):
    hrefs = []
    tries = 0
    while True:
        try:
            for result in DDGS().text(keywords, max_results=maxSources):
                hrefs.append(result.get("href"))
            break
        except:
            if tries >= 2:
                printError("Couldn't load DuckDuckGo after 3 tries! Aborting search.")
                return ""
            else:
                printError("Exception thrown while searching DuckDuckGo, trying again in 10 seconds...")
                time.sleep(10)
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
        "Access forbidden",
        "Please contact the site",
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
    printDump(websiteText)
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


def getYouTubeCaptions(videoIdIn):
    try:
        captionStringBuilder = ""
        defaultLanguageCode = "en"
        printDebug("Video ID: " + videoIdIn)
        srt = YouTubeTranscriptApi.get_transcript(videoIdIn, languages=[defaultLanguageCode])
        if YouTubeTranscriptApi.list_transcripts(videoIdIn).find_transcript([defaultLanguageCode]).is_generated:
            printInfo("Heads up! It seems like this transcript is auto-generated - it may not be 100% correct!")
        for s in srt:
            for key, value in s.items():
                if key == "text":
                    captionStringBuilder += value + " "
        printDump("Video captions: " + captionStringBuilder)
        return captionStringBuilder
    except Exception as e:
        disabledText = "Subtitles are disabled for this video"
        if disabledText in str(e):
            printError(disabledText + "!")
            return disabledText + "!"
        else:
            printError(str(e))
            return "An error occured while obtaining the captions for this video!"

