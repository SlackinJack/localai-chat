import json
import openai
import os
import re
import time

# local imports
from modules.openfile import *
from modules.search import *
from modules.utils import *


strModels = ""
strDefaultModel = ""


#################################################
############## BEGIN CONFIGURATION ##############
#################################################


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
strModelChat = CONFIG["CHAT_MODEL"]
strModelCompletion = CONFIG["COMPLETION_MODEL"]
strIgnoredModels = CONFIG["IGNORED_MODELS"]
shouldUseFunctions = (CONFIG["ENABLE_FUNCTIONS"] == "True")


#################################################
################ BEGIN TEMPLATES ################
#################################################


strAnswerTemplate = ""
with open("templates/answer-template.tmpl", "r") as f:
    for l in f.readlines():
        strAnswerTemplate += l + "\n"


strChatTemplate = ""
with open("templates/chat-template.tmpl", "r") as f:
    for l in f.readlines():
        strChatTemplate += l + "\n"


strCompletionTemplate = ""
with open("templates/completion-template.tmpl", "r") as f:
    for l in f.readlines():
        strCompletionTemplate += l + "\n"


strSummaryTemplate = ""
with open("templates/summary-template.tmpl", "r") as f:
    for l in f.readlines():
        strSummaryTemplate += l + "\n"


strTopicTemplate = ""
with open("templates/topic-template.tmpl", "r") as f:
    for l in f.readlines():
        strTopicTemplate += l + "\n"


#################################################
################ BEGIN FUNCTIONS ################
#################################################


def searchWeb(prompt, keywords):
    response = getSearchResponse(keywords, intMaxSources)
    textResponse = response[0]
    sourceResponse = response[1]
    if len(response) < 1:
        return getChat(prompt)
    else:
        return getAnswer(prompt, textResponse, sourceResponse)


availableFunctions = [
    {
        "name": "searchWeb",
        "description": "Search exclusively for these topics: news, people, locations, products and services.",
        "parameters": {
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "The prompt given by the user."
                },
                "keywords": {
                    "type": "string",
                    "description": "The topic or subject of the prompt.",
                },
            },
            "required": ["prompt", "keywords"],
        },
    }
]


functionMap = {
    "searchWeb": searchWeb,
}


##################################################
################# BEGIN KEYWORDS #################
##################################################


def search(promptIn):
    keywords = getTopic(promptIn)
    response = getSearchResponse(keywords, intMaxSources)
    textResponse = response[0]
    sourceResponse = response[1]
    if len(response) < 1:
        return getChat(promptIn)
    else:
        return getAnswer(promptIn, textResponse, sourceResponse)


keywordsMap = {
    "search": search,
}


##################################################
################# BEGIN TRIGGERS #################
##################################################


def browse(promptIn):
    strings = promptIn.split(" ")
    for s in strings:
        if s.startswith("http"):
            newPrompt = promptIn.replace(s, "")
            websiteText = getInfoFromWebsite(s, True)
            if websiteText is not None:
                return getAnswer(newPrompt, websiteText)
            else:
                return ""


def openFile(promptIn):
    # TODO: url path to files
    filePath = (re.findall(r"'(.*?)'", promptIn, re.DOTALL))[0]
    newPrompt = promptIn.replace("'" + filePath + "'", "")
    strFileContents = ""
    if filePath.endswith(".pdf"):
        pdfText = getPDFText(filePath)
        # TODO: split and parse by sentence length like websites
    else:
        strFileContents = getFileText(filePath)
    strFileContents = cleanupString(strFileContents)
    return getAnswer(promptIn, strFileContents)


# triggers should be used to do specific functions
triggers = {
    "browse": [
    "http://",
    "https://"
    ],
    "openFile": [
    "'/"
    ]
}


triggerFunctionMap = {
    "browse": browse,
    "openFile": openFile,
}


##################################################
################# BEGIN COMMANDS #################
##################################################


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


#################################################
############### BEGIN COMPLETIONS ###############
#################################################


def chatPrompt(promptIn):
    action = getActionFromPrompt(promptIn)
    response = ""
    if action == "none":
        response = getResponse(promptIn)
    else:
        functionCall = triggerFunctionMap[action]
        response = functionCall(promptIn)
    return response


def getActionFromPrompt(promptIn):
    for key in triggers:
        for value in triggers[key]:
            if value in promptIn:
                return key
    return "none"


def getResponse(promptIn):
    if not shouldUseFunctions:
        printDebug("Using keywords...")
        if promptIn.startswith("search ") or promptIn.startswith("search for "):
            printDebug("Searching for prompt...")
            keywords = getTopic(promptIn.replace("search for ", "").replace("search ", ""))
            printDebug("Generated keywords: " + keywords)
            return searchWeb(promptIn, keywords)
        else:
            printDebug("No keywords detected, generating chat output...")
            return getChat(promptIn)
    else:
        completion = getChatFunctionCompletion(promptIn)
        if completion is not None:
            functionName = completion.choices[0].message.function_call.name
            printDebug("Calling function: " + functionName)
            functionCall = functionMap[functionName]
            functionArgs = json.loads(completion.choices[0].message.function_call.arguments)
            functionOutput = functionCall(
                prompt = functionArgs.get("prompt"),
                keywords = functionArgs.get("keywords"),
            )
            return functionOutput
        else:
            printDebug("No functions for prompt - the response will be completely generated!")
            return getChat(promptIn)


def getChatFunctionCompletion(promptIn):
    completion = openai.ChatCompletion.create(
        model = strModelCompletion,
        messages = [{"role": "system", "content": promptIn}],
        functions = availableFunctions,
        function_call = "auto",
    )
    try:
        if (completion.choices[0].message.function_call):
            if(completion.choices[0].message.function_call.name):
                return completion
    except:
        return None
    return None


def getChatCompletion(templateMode, promptIn, infoIn=None, sources=None):
    global strChatTemplate                 #0 - chat
    global strCompletionTemplate           #1 - completion
    global strAnswerTemplate               #2 - completion
    global strSummaryTemplate              #3 - completion
    global strTopicTemplate                #4 - completion
    strTemplatedPrompt = ""
    strModelToUse = strModelCompletion
    match templateMode:
        case 0:
            strTemplatedPrompt = strChatTemplate.replace("{{.Input}}", promptIn)
            strModelToUse = strModelChat
        case 1:
            strTemplatedPrompt = strCompletionTemplate.replace("{{.Input}}", promptIn)
        case 2:
            strTemplatedPrompt = strAnswerTemplate.replace("{{.Input}}", promptIn).replace("{{.Input2}}", infoIn)
        case 3:
            strTemplatedPrompt = strSummaryTemplate.replace("{{.Input}}", promptIn)
        case 4:
            strTemplatedPrompt = strTopicTemplate.replace("{{.Input}}", promptIn)
        case _:
            strTemplatedPrompt = strChatTemplate.replace("{{.Input}}", promptIn)
            strModelToUse = strModelChat
    strSystem = ""
    strUser = ""
    strAssistant = ""
    for line in strTemplatedPrompt.split("\n"):
        if line.startswith("SYSTEM:"):
            strSystem = line.replace("SYSTEM:", "")
        elif line.startswith("USER:"):
            strUser = line.replace("USER:", "")
        elif line.startswith("ASSISTANT:"):
            strAssistant = line.replace("ASSISTANT:", "")
    completion = openai.ChatCompletion.create(
        model = strModelToUse,
        messages = [
            {
                "role": "system",
                "content": strSystem,
            },
            {
                "role": "user",
                "content": strUser,
            },
            {
                "role": "assistant",
                "content": strAssistant,
            },
        ],
    )
    if sources is not None:
        return completion.choices[0].message.content + "\n\n\n" + sources
    else:
        return completion.choices[0].message.content


def getChat(promptIn):
    return getChatCompletion(0, promptIn)


def getCompletion(promptIn):
    return getChatCompletion(1, promptIn)


def getAnswer(promptIn, infoIn, sourcesIn=None):
    return getChatCompletion(2, promptIn, infoIn, sourcesIn)


def getSummary(promptIn):
    return getChatCompletion(3, promptIn)


def getTopic(promptIn):
    return getChatCompletion(4, promptIn)


##################################################
################### BEGIN CHAT ###################
##################################################


strModels = detectModels(folderModels, strIgnoredModels)
strDefaultModel = strModels.split(", ")[0]
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
