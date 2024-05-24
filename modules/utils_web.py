import concurrent.futures
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
    searchResults = {} #href, text
    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = []
        printDebug("Search term(s):\n" + keywords)
        sources = searchDDG(keywords, maxSources)
        printDebug("Target links:")
        for href in sources:
            printDebug("   - " + href)
            futures.append(executor.submit(getInfoFromWebsite, websiteIn = href, bypassLength = False, maxSentences = maxSentences))
        for future in concurrent.futures.as_completed(futures):
            res = future.result()
            searchResults[res[0]] = res[1]
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
        except Exception as e:
            if tries >= 2:
                printError("Couldn't load DuckDuckGo after 3 tries! Aborting search.")
                printError("(" + str(e) + ")")
                return ""
            else:
                printError("Exception thrown while searching DuckDuckGo, trying again in 5 seconds...")
                printError("(" + str(e) + ")")
                time.sleep(5)
                tries += 1
    return hrefs


jsErrors = [
    "JavaScript",
    "JS",
    "is not supported",
    "another browser",
    "supported browser",
]

blockedErrors = [
    "Access Denied",
    "Access forbidden",
    "Please contact the site",
    "You don't have permission to access",
    "403 - Forbidden",
    "403 Forbidden",
    "Access to this page is forbidden",
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
        return [websiteIn, ""]
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
        return [websiteIn, ""]
    for e in blockedErrors:
        if e in websiteText:
            printError("Website failed error test!")
            return [websiteIn, ""]
    if not bypassLength and maxSentences > 0:
        return [websiteIn, trimTextBySentenceLength(websiteText, maxSentences)]
    else:
        return [websiteIn, websiteText]


def getYouTubeCaptions(videoIdIn):
    try:
        captionStringBuilder = ""
        defaultLanguageCode = "en"
        printDebug("Video ID: " + videoIdIn)
        srt = YouTubeTranscriptApi.get_transcript(videoIdIn, languages=[defaultLanguageCode])
        if YouTubeTranscriptApi.list_transcripts(videoIdIn).find_transcript([defaultLanguageCode]).is_generated:
            printInfo("This transcript is auto-generated - it may not be correct.")
        for s in srt:
            for key, value in s.items():
                if key == "text":
                    captionStringBuilder += value + " "
        captionStringBuilder = captionStringBuilder.replace("\xa0", "")
        printDump("Video captions: " + captionStringBuilder)
        return captionStringBuilder
    except Exception as e:
        disabledText = "Subtitles are disabled for this video"
        if disabledText in str(e):
            printError(disabledText + "!")
            return disabledText + "!"
        else:
            printError(str(e))
            return "An error occured while obtaining the captions for this video."

