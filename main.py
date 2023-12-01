import json
import openai
import os
import re
import time

# local imports
from modules.openfile import *
from modules.search import *
from modules.utils import *


listModels = []
strDefaultModel = ""


#################################################
############## BEGIN CONFIGURATION ##############
#################################################


fileConfig = open("config.txt", "r")
fileConfiguration = (fileConfig.read()).split("\n")
fileConfig.close()
initConfig(fileConfiguration)

openai.api_base = configuration["ADDRESS"]
openai.api_key = OPENAI_API_KEY = configuration["KEY"]
os.environ["OPENAI_API_KEY"] = configuration["KEY"]

intMaxSources = int(configuration["MAX_SOURCES"])
intMaxSentences = int(configuration["MAX_SENTENCES"])
folderModels = configuration["MODELS_PATH"]
strModelChat = configuration["CHAT_MODEL"]
strModelCompletion = configuration["COMPLETION_MODEL"]
strIgnoredModels = configuration["IGNORED_MODELS"]
shouldUseFunctions = (configuration["ENABLE_FUNCTIONS"] == "True")

strModelStableDiffusion = configuration["STABLE_DIFFUSION_MODEL"]
strImageSize = configuration["IMAGE_SIZE"]

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


def generateImage(prompt):
    return getImageResponse(prompt)


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
    },
    {
        "name": "generateImage",
        "description": "Generate an image.",
        "parameters": {
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "The prompt given by the user."
                },
            },
            "required": ["prompt"],
        },
    },
]


functionMap = {
    "searchWeb": searchWeb,
    "generateImage": generateImage,
}


##################################################
################# BEGIN KEYWORDS #################
##################################################


def keyword_search(promptIn):
    keywords = getTopic(promptIn)
    return searchWeb(promptIn, keywords)


def keyword_generate(promptIn):
    return generateImage(promptIn)

keywordsMap = {
    keyword_search: [
        "search for ",
        "search ",
    ],
    keyword_generate: [
        "generate image ",
        "generate picture ",
        "generate image of ",
        "generate picture of ",
        "generate an image of ",
        "generate a picture of ",
        "make image ",
        "make picture ",
        "make image of ",
        "make picture of ",
        "make an image of ",
        "make a picture of ",
    ],
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
    filePath = (re.findall(r"'(.*?)'", promptIn, re.DOTALL))[0]
    newPrompt = promptIn.replace("'" + filePath + "'", "")
    strFileContents = getFileContents(filePath)
    return getAnswer(newPrompt, strFileContents)


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
    printGeneric("chatmodel")
    printGeneric("compmodel")
    printGeneric("exit/quit")


def modelCommand(mode, currentModel):
    printInfo("Available models: " + str(listModels))
    model = printInput("Select model for " + mode + " (leave empty for current '" + currentModel + "'): ")
    if len(model) == 0:
        model = currentModel
    printSuccess(mode + " model set to: " + model)
    return model


def sdModelCommand(mode, currentModel):
    model = printInput("Select model for " + mode + " (leave empty for current '" + currentModel + "'): ")
    if len(model) == 0:
        model = currentModel
    printSuccess(mode + " model set to: " + model)
    return model

#################################################
############### BEGIN COMPLETIONS ###############
#################################################


def chatPrompt(promptIn):
    response = ""
    action = "none"
    for key in triggers:
        for value in triggers[key]:
            if value in promptIn:
                action = key
    if action == "none":
        response = getResponse(promptIn)
    else:
        functionCall = triggerFunctionMap[action]
        response = functionCall(promptIn)
    return response


def getResponse(promptIn):
    if not shouldUseFunctions:
        printInfo("Using keywords...")
        for key, value in keywordsMap.items():
            for trigger in value:
                if promptIn.startswith(trigger):
                    functionCall = key
                    return functionCall(promptIn.replace(trigger, ""))
        printInfo("No keywords detected, generating chat output...")
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
    printDebug("Prompt (after templating):\nSYSTEM:" + strSystem + "\nUSER:" + strUser + "\nASSISTANT:" + strAssistant)
    try:
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
    except:
        printError("Failed to connect to LocalAI! (Check your connection?)")
        return ""


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


def getImageResponse(promptIn):
    printInfo("Generating image with prompt: " + promptIn)
    completion = openai.Image.create(
        model = strModelStableDiffusion,
        prompt = promptIn,
        size = strImageSize,
    )
    theURL = completion.data[0].url
    split = theURL.split("/")
    filename = split[len(split) - 1]
    urllib.request.urlretrieve(theURL, filename)
    openLocalFile(filename)
    return "Your image is available at:\n\n" + completion.data[0].url


def detectModelsNew():
    modelList = openai.Model.list()
    for model in modelList["data"]:
        modelName = model["id"]
        if modelName not in strIgnoredModels:
            listModels.append(modelName)


##################################################
################### BEGIN CHAT ###################
##################################################


detectModelsNew()
if len(strModelChat) == 0:
    strModelChat = listModels[0]
if len(strModelCompletion) == 0:
    strModelCompletion = listModels[0]
printInfo("Chat model ('chatmodel' to change): " + strModelChat)
printInfo("Comp model ('compmodel' to change): " + strModelCompletion)
printInfo("SD model ('sdmodel' to change): " + strModelStableDiffusion)
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
    elif strPrompt == "sdmodel":
        strModelStableDiffusion = sdModelCommand("Stable Diffusion", strModelStableDiffusion)
    else:
        strResponse = ""
        printInfo("Generating response...")
        tic = time.perf_counter()
        strResponse = chatPrompt(strPrompt)
        toc = time.perf_counter()
        printSeparator()
        printResponse(strResponse)
        printDebug(f"\n\n{toc - tic:0.3f} seconds")
