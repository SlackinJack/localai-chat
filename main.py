import openai
import os
import re
import requests
import time
from bs4 import BeautifulSoup
from duckduckgo_search import DDGS
from PyPDF2 import PdfReader
from termcolor import colored


# TODO
# determine topic, research topic, formulate educated answer based on topic
# add conversation contex
# config file
# speedup and cleanup
# set separate models for chat and completion
# apply models correctly


# default vars
openai.api_base = "http://localhost:8080/v1"
openai.api_key = "sx-xxx"
OPENAI_API_KEY = "sx-xxx"
os.environ["OPENAI_API_KEY"] = OPENAI_API_KEY

folderModels = "../models/"
strDefaultModel = ""
strModelChat = ""
strModelCompletion = ""
strModels = ""
# triggers should be used to do specific functions
triggers = {
    "browse": [
    "http:",
    "https:"
    ],
    "open": [
    "'/"
    ]
}
# actions should be used to influence the output response
actions = {
    "search": [
    "news",
    "biography",
    "facts",
    "products",
    "economics",
    "trends"
    ],
    "generate": [
    "sarcasm",
    "experiences",
    "opinions",
    "advice",
    "greetings",
    "philosophies",
    "ideologies",
    "ideas",
    "feelings",
    "common knowledge",
    "conventional wisdom",
    "creative works"
    ]
}

# https://pypi.org/project/termcolor/


def printInput(string):
    strInput = input(colored(string, "white", attrs=["bold"]))
    return strInput


def printInfo(string):
    print(colored(string, "yellow"))


def printResponse(string):
    print(colored(string, "green"))


def printGeneric(string):
    print(colored(string, "light_grey"))


def printWarning(string):
    print(colored(string, "red"))


def printSuccess(string):
    print(colored(string, "green"))


def printDebug(string):
    print(colored(string, "light_grey"))


def printSeparator():
    printGeneric("-------------------------------------------------------------")


def detectModels():
    modelsList = []
    modelsBuilder = ""
    for fileName in os.listdir(folderModels):
        if fileName.endswith(".yaml"):
            strModelName = fileName.split(".")
            modelsList.append(strModelName[0])
    i = 0
    while i < len(modelsList):
        if i + 1 == len(modelsList):
            modelsBuilder = modelsBuilder + modelsList[i]
        else:
            modelsBuilder = modelsBuilder + modelsList[i] + ", "
        i += 1
    return modelsBuilder


def helpCommand():
    printInfo("Available commands: ")
    printGeneric("model")
    printGeneric("exit/quit")


def modelCommand(mode, currentModel):
    printInfo("Available models: " + strModels)
    model = printInput("Select model for " + mode + " (leave empty for current '" + currentModel + "'): ")
    if len(model) == 0:
        model = currentModel
    printSuccess(mode + " model set to: " + model)
    return model


def chatPrompt(chatModelIn, compModelIn, promptIn):
    action = determineCourseOfAction(compModelIn, promptIn)
    printDebug("Action determined: " + action)
    if action == "search":
        return doSearchResponse(chatModelIn, compModelIn, promptIn)
    elif action == "generate":
        return getChatCompletion(chatModelIn, promptIn)
    elif action == "browse":
        return doBrowseReponse(chatModelIn, promptIn)
    elif action == "open":
        return doOpenResponse(chatModelIn, compModelIn, promptIn)
    else:
        return getChatCompletion(chatModelIn, promptIn)


def determineCourseOfAction(compModelIn, promptIn):
    for key in triggers:
        values = triggers[key]
        for v in values:
            if v in promptIn:
                return key
    for key in actions:
        keytags = ""
        for tag in actions[key]:
            if len(keytags) == 0:
                keytags = tag
            else:
                keytags = keytags + ", " + tag
        completion = getContainsYesOrNo(compModelIn, promptIn, keytags)
        printDebug(completion)
        if "Yes" in completion:
            return key
    printWarning("Couldn't find an appropriate action to do!")
    return "default_generate"


#################################################
################# BEGIN WEBSITE #################
#################################################


def browse(weblinkIn):
    site = requests.get(weblinkIn)
    soup = BeautifulSoup(site.text, "html.parser")
    return cleanupString(soup.text)


def doBrowseReponse(chatModelIn, promptIn):
    strings = promptIn.split(" ")
    for s in strings:
        if s.startswith("http"):
            newPrompt = promptIn.replace(s, "")
            return getAnswer(chatModelIn, browse(s), newPrompt)


##################################################
################### BEGIN FILE ###################
##################################################


def openFile(compModelIn, filePath):
    strFile = ""
    if filePath.endswith(".pdf"):
        # TODO
        # speedup reading (read 2 pages at once?)
        printWarning("PDF support is very primative!")
        pdfFile = PdfReader(filePath)
        pdfPages = len(pdfFile.pages)
        pdfPageSummaries = []
        i = 0
        while i < pdfPages:
            printDebug("Reading page: " + str(i))
            pdfPageSummaries.append(getSummary(compModelIn, (pdfFile.pages[i]).extract_text()))
            i += 1
        if i <= 1:
            return str(pdfPageSummaries)
        else:
            return getSummary(compModelIn, str(pdfPageSummaries))
    else:
        # open as text-based file as default
        f = open(filePath, "r")
        strFile = f.read()
        f.close()
    return cleanupString(strFile)


def doOpenResponse(chatModelIn, compModelIn, promptIn):
    filePath = (re.findall(r"'(.*?)'", promptIn, re.DOTALL))[0]
    promptIn = promptIn.replace("'" + filePath + "'", "")
    strFileContents = openFile(compModelIn, filePath)
    return getAnswer(chatModelIn, strFileContents, promptIn)


##################################################
################## BEGIN SEARCH ##################
##################################################


def doSearchResponse(chatModelIn, compModelIn, promptIn):
    response = ""
    while len(response) == 0:
        printDebug("Searching online for this prompt...")
        forceSearchOnline = shouldSearchOnline = False
        searchTerms = generateSearchTerms(compModelIn, promptIn)
        printDebug("All search terms and queries: " + searchTerms)
        sources = dict()
        terms = searchTerms.split("; ")
        index = 0
        for term in terms:
            sources[index] = searchFromSearchTerms(term)
            # prevent spamming
            time.sleep(3)
            index += 1
        compiledSources = ""
        printDebug("Gathered information on the prompt: " + str(sources))
        for key in sources:
            compiledSources = compiledSources + "[(Source: " + (sources[key])[0] + "), (Answer:" + (sources[key])[1] + ")]"
        printDebug("Formulating response from information...")
        response = getAnswer(chatModelIn, compiledSources, promptIn)
        response += "\n\n\nSources considered:\n"
        for key in sources:
            response += "[" + str(key + 1) + "] '" + (sources[key])[2] + "\n"
        return response


def generateSearchTerms(compModelIn, promptIn):
    completion = getSearchTerms(compModelIn, promptIn)
    printDebug(completion)
    lines = completion.split("\n")
    searchTerms = ""
    i = 1
    for line in lines:
        if line.startswith(str(i)):
            term = line.split(str(i) + ". ")[1]
            if len(searchTerms) == 0:
                searchTerms = term
            else:
                searchTerms = searchTerms + "; " + term
            i += 1
        elif line.startswith("Query: "):
            query = line.split(": ")[1]
            if len(searchTerms) == 0:
                searchTerms = query
            else:
                searchTerms = searchTerms + "; " + query
    return searchTerms


def searchFromSearchTerms(searchTerm):
    printDebug("Searching online... [" + searchTerm + "]")
    webTitle = webBody = webRef = ""

    while len(webTitle) == len(webBody) == len(webRef) == 0:
        # ddg answers
        while True:
            try:
                for result in DDGS().answers(searchTerm):
                    webTitle = result.get("title")
                    webBody = result.get("body")
                    webRef = result.get("href")
                    break
                break
            except:
                printDebug("Exception thrown while looking up ddg answers, trying again in 5 seconds...")
                time.sleep(3)
        # ddg suggestions
        printDebug("Answers were empty, trying suggestion search instead...")
        time.sleep(3)
        while True:
            try:
                for result in DDGS().suggestions(searchTerm):
                    webTitle = result.get("title")
                    webBody = result.get("body")
                    webRef = result.get("href")
                    break
                break
            except:
                printDebug("Exception thrown while looking up ddg suggestions, trying again in 5 seconds...")
                time.sleep(3)
        # ddg texts
        printDebug("Suggestions were empty, trying text search instead...")
        time.sleep(3)
        while True:
            try:
                for result in DDGS().text(searchTerm, max_results=1):
                    webTitle = result.get("title")
                    webBody = result.get("body")
                    webRef = result.get("href")
                    break
                break
            except:
                printDebug("Exception thrown while looking up ddg texts, trying again in 5 seconds...")
                time.sleep(3)
        break
    return [webTitle, webBody, webRef]


#################################################
############### BEGIN COMPLETIONS ###############
#################################################


# used for generates
def getChatCompletion(chatModelIn, promptIn):
    completion = openai.ChatCompletion.create(
        model=chatModelIn,
        messages=[{"role": "user", "content": promptIn}]
    )
    return completion.choices[0].message.content


# any model
def getCompletion(modelIn, promptIn):
    completion = openai.Completion.create(
        model=modelIn,
        prompt=promptIn
    )
    return completion.choices[0].text


# chat model
def getAnswer(chatModelIn, sourcesIn, questionIn):
    return getCompletion(chatModelIn, "Using: " + sourcesIn + ", answer the following in an appropriate format: '" + questionIn + "'.")


# comp model
def getSummary(compModelIn, textIn):
    return getCompletion(compModelIn, "Summarize this: " + textIn)


# comp model
def getContainsYesOrNo(compModelIn, promptIn, targetIn):
    return getCompletion(compModelIn, "Answering exclusively with 'yes' or 'no', does '" + promptIn + "' discuss any of the following: " + targetIn + "? Give your response in one word only.")


# comp model
def getSearchTerms(compModelIn, promptIn):
    return getCompletion(compModelIn, "Determine the topic, then generate a list of three search terms regarding the topic that will be used to search for the following: " + promptIn)


#################################################
################## BEGIN UTILS ##################
#################################################


def cleanupString(stringIn):
    out = stringIn.replace("\n", " ").replace("\r", "") # remove all newlines
    out = ' '.join(stringIn.split()) # remove all redundant spaces
    out = re.sub(r'[^ \w+]', '', out) # remove all non-standard characters
    return out


##################################################
################### BEGIN CHAT ###################
##################################################


strModels = detectModels()
strDefaultModel = strModels.split(",")[0]
if len(strModelChat) == 0:
    strModelChat = strDefaultModel
if len(strModelCompletion) == 0:
    strModelCompletion = strDefaultModel
printInfo("Chat model ('chatmodel' to change): " + strModelChat)
printInfo("Comp model ('compmodel' to change): " + strModelCompletion)
shouldRun = True
while shouldRun:
    printSeparator()
    strPrompt = printInput("Enter a prompt ('help' for list of commands): ")
    printSeparator()

    if len(strPrompt) == 0 or strPrompt.isspace() or strPrompt == "help":
        helpCommand()
    elif strPrompt == "exit" or strPrompt == "quit":
        shouldRun = False
    elif strPrompt == "compmodel":
        strModelCompletion = modelCommand("Completion", strModelCompletion)
    elif strPrompt == "chatmodel":
        strModelChat = modelCommand("Chat", strModelChat)
    else:
        strResponse = ""
        printInfo("Generating response...")
        tic = time.perf_counter()
        strResponse = chatPrompt(strModelChat, strModelCompletion, strPrompt)
        toc = time.perf_counter()
        printSeparator()
        printResponse(strResponse)
        printDebug(f"\n\n{toc - tic:0.3f} seconds")
printInput("Press enter to exit...")
