import datetime
import json
import openai
import os
import re
import time

from pathlib import Path

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
strModelChat = configuration["CHAT_MODEL"]
strModelCompletion = configuration["COMPLETION_MODEL"]
strIgnoredModels = configuration["IGNORED_MODELS"]
shouldUseFunctions = (configuration["ENABLE_FUNCTIONS"] == "True")
shouldAutomaticallyOpenFiles = (configuration["AUTO_OPEN_FILES"] == "True")
enableStreamText = (configuration["ENABLE_TEXT_STREAMING"] == "True")

strModelStableDiffusion = configuration["STABLE_DIFFUSION_MODEL"]
strImageSize = configuration["IMAGE_SIZE"]


#################################################
############## BEGIN CONVERSATIONS ##############
#################################################


strConvoTimestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
strConvoName = strConvoTimestamp


def setConversation(filename):
    global strConvoName
    testpath = Path("conversations/" + filename + ".convo")
    if testpath.is_file() is not True:
        open("conversations/" + filename + ".convo", "w").close()
    strConvoName = filename


def writeConversation(strIn):
    fileConvo = open("conversations/" + strConvoName + ".convo", "a")
    fileConvo.write(strIn + "\n")
    fileConvo.close()


def getConversation():
    fileConvo = open("conversations/" + strConvoName + ".convo", "r")
    fileConversation = (fileConvo.read()).split("\n")
    fileConvo.close()
    return fileConversation


setConversation(strConvoTimestamp)


#################################################
################ BEGIN TEMPLATES ################
#################################################


strAnswerTemplate = ""
with open("templates/answer-template.tmpl", "r") as f:
    for l in f.readlines():
        strAnswerTemplate += l + "\n"


strTopicTemplate = ""
with open("templates/topic-template.tmpl", "r") as f:
    for l in f.readlines():
        strTopicTemplate += l + "\n"


strReplyTemplate = ""
with open("templates/reply-template.tmpl", "r") as f:
    for l in f.readlines():
        strReplyTemplate += l + "\n"


#################################################
################ BEGIN FUNCTIONS ################
#################################################


def searchWeb(args):
    arg1 = args["prompt"]
    arg2 = args["keywords"]
    response = getSearchResponse(arg2, intMaxSources)
    textResponse = response[0]
    sourceResponse = response[1]
    if len(textResponse) < 1 and len(sourceResponse) < 1:
        return getReply(arg1)
    else:
        writeConversation("SYSTEM: " + textResponse)
        return getAnswer(arg1, infoIn=textResponse, sourcesIn=sourceResponse, isOutput=True)


def generateImage(args):
    arg1 = args["prompt"]
    return getImageResponse(arg1)


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
    return searchWeb(
        {
            "prompt": promptIn,
            "keywords": getTopic(promptIn),
        }
    )


def keyword_generate(promptIn):
    return generateImage(
        {
            "prompt": promptIn,
        }
    )


def keyword_reply(promptIn):
    return getReply(promptIn)


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
    keyword_reply: [
        "reply ",
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
                writeConversation("SYSTEM: " + websiteText)
                return getAnswer(newPrompt, infoIn=websiteText, isOutput=True)
            else:
                return ""


def openFile(promptIn):
    filePath = (re.findall(r"'(.*?)'", promptIn, re.DOTALL))[0]
    newPrompt = promptIn.replace("'" + filePath + "'", "")
    strFileContents = getFileContents(filePath)
    writeConversation("SYSTEM: " + strFileContents)
    return getAnswer(newPrompt, infoIn=strFileContents, isOutput=True)


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
    printGeneric("Available commands: ")
    printGeneric("convo(s)/conversations")
    printGeneric("chatmodel")
    printGeneric("compmodel")
    printGeneric("sdmodel")
    printGeneric("exit/quit")


def convoCommand():
    convoList = []
    for conversation in os.listdir("conversations"):
        if conversation.endswith(".convo"):
            convoList.append(conversation.replace(".convo", ""))
    printInfo("Conversations available: ")
    for convo in convoList:
        printInfo(convo)
    convoName = printInput("Select a conversation to use, or create a new one by using an unique name: ")
    setConversation(convoName)
    printSuccess("Conversation set to: " + convoName)
    return


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
    triggerAction = "none"
    for key in triggers:
        for value in triggers[key]:
            if value in promptIn:
                triggerAction = key
    if triggerAction == "none":
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
        return getReply(promptIn)
    else:
        completion = getChatFunctionCompletion(promptIn)
        if completion is not None:
            functionName = completion.choices[0].message.function_call.name
            printDebug("Calling function: " + functionName)
            functionCall = functionMap[functionName]
            functionArgs = json.loads(completion.choices[0].message.function_call.arguments)
            functionOutput = functionCall(functionArgs)
            return functionOutput
        else:
            printDebug("No functions for prompt - the response will be completely generated!")
            return getReply(promptIn)


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


def getChatCompletion(templateMode, promptIn, shouldStreamText=False, infoIn=None, sources=None):
    canStreamText = False
    if shouldStreamText and enableStreamText:
        canStreamText = True
        printDebug("Streaming text for this completion!")
    global strAnswerTemplate               #1 - comp model
    global strTopicTemplate                #2 - comp model
    global strReplyTemplate                #3 - chat model
    strTemplatedPrompt = ""
    strModelToUse = strModelCompletion
    match templateMode:
        case 1:
            strTemplatedPrompt = strAnswerTemplate.replace("{{.Input}}", promptIn).replace("{{.Input2}}", infoIn)
        case 2:
            strTemplatedPrompt = strTopicTemplate.replace("{{.Input}}", promptIn)
        case 3:
            strTemplatedPrompt = strReplyTemplate.replace("{{.Input}}", promptIn)
            strModelToUse = strModelChat
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
    if templateMode == 3:
        prevConvo = ""
        for line in infoIn:
            prevConvo = prevConvo + line + "\n"
        printDebug("Prompt (after templating):\n" + prevConvo + "\nSYSTEM:" + strSystem + "\nUSER:" + strUser + "\nASSISTANT:" + strAssistant)
        strSystem = prevConvo + "\n" + strSystem
    else:
        printDebug("Prompt (after templating):\nSYSTEM:" + strSystem + "\nUSER:" + strUser + "\nASSISTANT:" + strAssistant)
    try:
        completion = openai.ChatCompletion.create(
            model = strModelToUse,
            stream = canStreamText,
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
        if canStreamText:
            printSeparator()
            strOutput = ""
            for chunk in completion:
                if chunk.choices[0].delta.content is not None:
                    printResponse(chunk.choices[0].delta.content, "")
                    time.sleep(0.025)
                    sys.stdout.flush()
                    strOutput = strOutput + chunk.choices[0].delta.content
            writeConversation("ASSISTANT: " + strOutput)
            if sources is not None:
                printResponse("\n\n\n" + sources)
            return ""
        else:
            if sources is not None:
                return completion.choices[0].message.content + "\n\n\n" + sources
            else:
                return completion.choices[0].message.content
    except:
        printError("Failed to connect to LocalAI! (Check your connection?)")
        return ""


def getAnswer(promptIn, infoIn, sourcesIn=None, isOutput=False):
    return getChatCompletion(1, promptIn, isOutput, infoIn, sourcesIn)


def getTopic(promptIn):
    return getChatCompletion(2, promptIn)


def getReply(promptIn):
    return getChatCompletion(3, promptIn, True, getConversation())


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
    if shouldAutomaticallyOpenFiles:
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
    printDebug("Current conversation file: " + strConvoName + ".convo")
    printSeparator()
    strPrompt = printInput("Enter a prompt ('help' for list of commands): ")
    printSeparator()
    if len(strPrompt) == 0 or strPrompt.isspace() or strPrompt == "help":
        helpCommand()
    elif strPrompt == "exit" or strPrompt == "quit":
        shouldRun = False
    elif strPrompt == "convo" or strPrompt == "convos" or strPrompt == "conversations":
        convoCommand()
    elif strPrompt == "compmodel":
        strModelCompletion = modelCommand("Completion", strModelCompletion)
    elif strPrompt == "chatmodel":
        strModelChat = modelCommand("Chat", strModelChat)
    elif strPrompt == "sdmodel":
        strModelStableDiffusion = sdModelCommand("Stable Diffusion", strModelStableDiffusion)
    else:
        strResponse = ""
        printInfo("Generating response...")
        writeConversation("USER: " + strPrompt)
        tic = time.perf_counter()
        strResponse = chatPrompt(strPrompt)
        toc = time.perf_counter()
        if len(strResponse) > 0:
            printSeparator()
            printResponse(strResponse)
        printDebug(f"\n\n{toc - tic:0.3f} seconds")
