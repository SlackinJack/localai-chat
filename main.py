import json
import openai
import os
import re
import requests
import time
from bs4 import BeautifulSoup
from duckduckgo_search import DDGS
from PyPDF2 import PdfReader
from readability import Document
from termcolor import colored


# TODO
# determine topic, research topic, formulate educated answer based on topic
# add conversation context


fileConfig = open("config.txt", "r")
fileConfiguration = (fileConfig.read()).split("\n")
fileConfig.close()
CONFIG = dict()
for line in fileConfiguration:
    if len(line) > 0 and not line.startswith("#"):
        key = line.split("=")[0]
        value = line.split("=")[1]
        CONFIG[key] = value


openai.api_base = CONFIG["ADDRESS"]
openai.api_key = OPENAI_API_KEY = CONFIG["KEY"]
os.environ["OPENAI_API_KEY"] = CONFIG["KEY"]


intMaxSources = int(CONFIG["MAX_SOURCES"])
intMaxSentences = int(CONFIG["MAX_SENTENCES"])
folderModels = CONFIG["MODELS_PATH"]
strDefaultModel = ""
strModelChat = CONFIG["CHAT_MODEL"]
strModelCompletion = CONFIG["COMPLETION_MODEL"]
strModels = ""


strAnswerTemplate = ""
with open("answer-template.tmpl", "r") as f:
    for l in f.readlines():
        strAnswerTemplate += l + "\n"


strChatTemplate = ""
with open("chat-template.tmpl", "r") as f:
    for l in f.readlines():
        strChatTemplate += l + "\n"


strCompletionTemplate = ""
with open("completion-template.tmpl", "r") as f:
    for l in f.readlines():
        strCompletionTemplate += l + "\n"


strSummaryTemplate = ""
with open("summary-template.tmpl", "r") as f:
    for l in f.readlines():
        strSummaryTemplate += l + "\n"


strCurrentPrompt = ""


#################################################
################## BEGIN UTILS ##################
#################################################


def getInfoFromWebsite(websiteIn, bypassLength):
    # if "JavaScript" in websiteText and "cookies" in websiteText:
    # source.remove(key)
    # continue
    website = requests.get(websiteIn)
    reader = Document(website.content)
    websiteText = reader.summary()
    websiteText = re.sub('<[^<]+?>', '', websiteText)
    websiteText = cleanupString(websiteText)
    if not bypassLength:
        i = 0 # chars
        j = 0 # sentences
        k = 0 # chars since last sentence
        global intMaxSentences
        for char in websiteText:
            i += 1
            k += 1
            if "." == char or "!" == char or "?" == char:
                j += 1
                if k < 32:
                    # sentence is too short to be considered as complete
                    j -= 1
                if j == intMaxSentences:
                    break
                k = 0
        websiteText = websiteText[0:i]
    return websiteText


def searchWeb(keywords):
    response = ""
    sources = dict()
    global intMaxSources
    printDebug("Generated serach term: " + keywords)
    index = 0
    while True:
        try:
            # TODO: add website blacklist filters
            # TODO: filter websites that ask for js/cookies
            for result in DDGS().text(keywords, max_results=intMaxSources):
                sources[index] = result.get("href")
                index += 1
            break
        except:
            printDebug("Exception thrown while looking up ddg texts, trying again in 5 seconds...")
            time.sleep(5)
    compiledSources = ""
    printDebug("Target links: " + str(sources))
    for key in sources:
        websiteText = getInfoFromWebsite(sources[key], False)
        
        printDebug("[" + str(key + 1) + "] " + websiteText)
        compiledSources += "[" + websiteText + "]"
    printDebug("Generating response with sources...")
    global strModelChat
    global strCurrentPrompt
    if len(compiledSources) < 1:
        printWarning("No sources compiled - the reply will be completely generated!")
    response = getAnswer(strCurrentPrompt, compiledSources)
    if len(compiledSources) > 1:
        response += "\n\n\nSources considered:\n"
        for key in sources:
            response += "[" + str(key + 1) + "] '" + sources[key] + "\n"
    return response


def browse(promptIn):
    strings = promptIn.split(" ")
    for s in strings:
        if s.startswith("http"):
            newPrompt = promptIn.replace(s, "")
            return getAnswer(newPrompt, getInfoFromWebsite(s, True))


def openFile(promptIn):
    # TODO: url path to files
    filePath = (re.findall(r"'(.*?)'", promptIn, re.DOTALL))[0]
    newPrompt = promptIn.replace("'" + filePath + "'", "")
    strFileContents = ""
    if filePath.endswith(".pdf")
        # TODO: add option to read entire pdf at once
        printWarning("PDF support is very primative!")
        pdfFile = PdfReader(filePath)
        pdfPages = len(pdfFile.pages)
        pdfPageSummaries = []
        i = 0
        if pdfPages >= 2:
            # get 2 pages of text each cycle
            while i < pdfPages:
                printDebug("Reading page: " + str(i))
                p = pdfFile.pages[i].extract_text()
                p2 = ""
                i1 = i + 1
                if i1 <= pdfPages:
                    printDebug("Reading page: " + str(i1))
                    p2 = pdfFile.pages[i1].extract_text()
                pdfPageSummaries.append(getSummary(p + "\n" + p2))
                i = i + 2
            return getAnswer(newPrompt, pdfPageSummaries)
        else:
            # single page pdf
            printDebug("Reading page: " + str(i))
            p = pdfFile.pages[i].extract_text()
            return getAnswer(newPrompt, p)
    else:
        # open as text-based file as default
        f = open(filePath, "r")
        strFile = f.read()
        f.close()
    strFileContents = cleanupString(strFileContents)
    return getAnswer(promptIn, strFileContents)


# functions
availableFunctions = [
    {
        "name": "searchWeb",
        "description": "Search for uncommon information. Searchable topics: news, people, locations, products and services.",
        "parameters": {
            "type": "object",
            "properties": {
                "keywords": {
                    "type": "string",
                    "description": "The topic or subject of the prompt.",
                },
            },
            "required": ["keywords"],
        },
    }
]


functionMap = {
    "searchWeb": searchWeb,
}


# triggers should be used to do specific functions
triggers = {
    "browse": [
    "http:",
    "https:"
    ],
    "openFile": [
    "'/"
    ]
}


triggerFunctionMap = {
    "browse": browse,
    "openFile": openFile,
}


def cleanupString(stringIn):
    out = stringIn.replace("\n", " ").replace("\r", "")          # remove all newlines
    out = ' '.join(out.split())                                  # remove all redundant spaces
    out = (out.encode("ascii", errors="ignore")).decode()        # drop all non-ascii chars
    return out


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


def getActionFromPrompt(promptIn):
    for key in triggers:
        for value in triggers[key]:
            if value in promptIn:
                return key
    return "default"


def chatPrompt(promptIn):
    global strCurrentPrompt
    strCurrentPrompt = promptIn
    action = getActionFromPrompt(promptIn)
    response = ""
    if action == "default":
        response = getResponse(promptIn)
    else:
        functionCall = triggerFunctionMap[action]
        response = functionCall(promptIn)
    strCurrentPrompt = ""
    return response

#################################################
############### BEGIN COMPLETIONS ###############
#################################################


def getChatCompletion(templateMode, input1, input2=None):
    global strModelChat
    global strModelCompletion
    global strChatTemplate                 #0
    global strCompletionTemplate           #1
    global strAnswerTemplate               #2
    global strSummaryTemplate              #3
    strTemplatedPrompt = ""
    strModelToUse = ""
    match templateMode:
        case 1:
            strTemplatedPrompt = strCompletionTemplate.replace("{{.Input}}", input1)
            strModelToUse = strModelCompletion
        case 2:
            strTemplatedPrompt = strAnswerTemplate.replace("{{.Input}}", input1).replace("{{.Input2}}", input2)
            strModelToUse = strModelCompletion
        case 3:
            strTemplatedPrompt = strSummaryTemplate.replace("{{.Input}}", input1)
            strModelToUse = strModelCompletion
        case _: # and case 0:
            strTemplatedPrompt = strChatTemplate.replace("{{.Input}}", input1)
            strModelToUse = strModelChat
    completion = openai.ChatCompletion.create(
        model = strModelToUse,
        messages = [
            {
                "role": "user",
                "content": strTemplatedPrompt
            }
        ]
    )
    return completion.choices[0].message.content


def getChatFunctionCompletion(promptIn):
    global strModelCompletion
    completion = openai.ChatCompletion.create(
        model = strModelCompletion,
        messages = promptIn,
        functions = availableFunctions,
        function_call = "auto",
    )
    if (completion.choices[0].message.function_call):
        if(completion.choices[0].message.function_call.name):
            return completion
    return None


def getResponse(promptIn):
    thePrompt = [{"role": "user", "content": promptIn}]
    completion = getChatFunctionCompletion(thePrompt)
    
    if completion is not None:
        functionName = completion.choices[0].message.function_call.name
        printDebug("Calling function: " + functionName)
        functionCall = functionMap[functionName]
        functionArgs = json.loads(completion.choices[0].message.function_call.arguments)
        functionOutput = functionCall(
            keywords = functionArgs.get("keywords"),
        )

        return functionOutput
    else:
        printDebug("No functions for prompt - the response will be completely generated!")
        return getChat(promptIn)


def getChat(promptIn):
    return getChatCompletion(0, promptIn)


def getCompletion(promptIn):
    return getChatCompletion(1, promptIn)


def getAnswer(promptIn, infoIn):
    return getChatCompletion(2, promptIn, infoIn)


def getSummary(promptIn):
    return getChatCompletion(3, promptIn)


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
        strResponse = chatPrompt(strPrompt)
        toc = time.perf_counter()
        printSeparator()
        printResponse(strResponse)
        printDebug(f"\n\n{toc - tic:0.3f} seconds")
printInput("Press enter to exit...")
