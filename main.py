import json
import openai
import os
import re
import time

# local imports
from modules.openfile import *
from modules.search import *
from modules.utils import *


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


strCurrentPrompt = ""


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


#################################################
################ BEGIN FUNCTIONS ################
#################################################


def searchWeb(keywords):
    response = ""
    printDebug("Generated serach term(s): " + keywords)
    sources = searchDDG(keywords, intMaxSources)
    compiledSources = ""
    printDebug("Target links: " + str(sources))
    for key in sources:
        websiteText = getInfoFromWebsite(sources[key], False, intMaxSentences)
        printDebug("[" + str(key + 1) + "] " + websiteText)
        compiledSources += "[" + websiteText + "]"
    printDebug("Generating response with sources...")
    if len(compiledSources) < 1:
        printWarning("No sources compiled - the reply will be completely generated!")
    response = getAnswer(strCurrentPrompt, compiledSources)
    if len(compiledSources) >= 1:
        response += "\n\n\nSources considered:\n"
        for key in sources:
            response += "[" + str(key + 1) + "] '" + sources[key] + "\n"
    return response


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


##################################################
################# BEGIN TRIGGERS #################
##################################################


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
    completion = openai.ChatCompletion.create(
        model = strModelCompletion,
        messages = promptIn,
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


strModels = detectModels(folderModels)
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
