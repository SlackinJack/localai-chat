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


##################################################
################# BEGIN KEYWORDS #################
##################################################


def keyword_search(promptIn):
    response = getSearchResponse(getTopic(promptIn), intMaxSources)
    textResponse = response[0]
    sourceResponse = response[1]
    writeConversation("SYSTEM: " + textResponse)
    return getAnswer(promptIn, info=textResponse, stream=True, sourcesIn=sourceResponse)


def keyword_generate(promptIn):
    return getImageResponse(promptIn)


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


def trigger_browse(promptIn):
    for s in promptIn.split(" "):
        if s.startswith("http"):
            websiteText = getInfoFromWebsite(s, True)
            writeConversation("SYSTEM: " + websiteText)
            return getAnswer(promptIn.replace(s, ""), stream=True, info=websiteText)


def trigger_openFile(promptIn):
    filePath = getFilePathFromPrompt(promptIn)
    strFileContents = getFileContents(filePath)
    writeConversation("SYSTEM: " + strFileContents)
    return getAnswer(promptIn.replace("'" + filePath + "'", ""), info=strFileContents, stream=True)


triggerMap = {
    trigger_browse: [
    "http://",
    "https://"
    ],
    trigger_openFile: [
    "'/"
    ]
}


##################################################
################# BEGIN COMMANDS #################
##################################################


def command_help():
    printGeneric("Available commands: ")
    printGeneric("convo(s)/conversations")
    printGeneric("chatmodel")
    printGeneric("compmodel")
    printGeneric("sdmodel")
    printGeneric("exit/quit")


def command_convo():
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


def command_chat_model():
    global strModelChat
    printInfo("Available models: " + str(listModels))
    model = printInput("Select model for chat (leave empty for current '" + strModelChat + "'): ")
    if len(model) == 0:
        model = strModelChat
    strModelChat = model
    printSuccess("Chat model set to: " + model)
    return


def command_comp_model():
    global strModelCompletion
    printInfo("Available models: " + str(listModels))
    model = printInput("Select model for chat (leave empty for current '" + strModelCompletion + "'): ")
    if len(model) == 0:
        model = strModelCompletion
    strModelCompletion = model
    printSuccess("Completion model set to: " + model)
    return


def command_sd_model():
    global strModelStableDiffusion
    model = printInput("Select model for Stable Diffusion (leave empty for current '" + strModelStableDiffusion + "'): ")
    if len(model) == 0:
        model = strModelStableDiffusion
    strModelStableDiffusion = model
    printSuccess("Stable Diffusion model set to: " + model)
    return


commandMap = {
    command_help: [
        "",
        "help",
        "?",
    ],
    command_convo: [
        "convo",
        "convos",
        "conversations",
    ],
    command_chat_model: [
        "chatmodel",
    ],
    command_comp_model: [
        "compmodel",
    ],
    command_sd_model: [
        "sdmodel",
    ],
}


def getChatCompletion(promptIn, templateMode=0, shouldStreamText=False, infoIn=None, sources=None, shouldWriteToConversation=False):
    canStreamText = False
    if shouldStreamText and enableStreamText:
        canStreamText = True
        printDebug("Streaming text for this completion!")
    global strReplyTemplate                #0 - chat model
    global strAnswerTemplate               #1 - comp model
    global strTopicTemplate                #2 - comp model
    strTemplatedPrompt = ""
    strModelToUse = strModelCompletion
    match templateMode:
        case 1:
            strTemplatedPrompt = strAnswerTemplate.replace("{{.Input}}", promptIn).replace("{{.Input2}}", infoIn)
        case 2:
            strTemplatedPrompt = strTopicTemplate.replace("{{.Input}}", promptIn)
        case _:
            strTemplatedPrompt = strReplyTemplate.replace("{{.Input}}", promptIn)
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
    if templateMode != 1 and templateMode != 2:
        prevConvo = ""
        for i in infoIn:
            prevConvo = prevConvo + "\n" + i
        printDebug("Prompt (after templating):\n" + prevConvo + "\n\nSYSTEM:" + strSystem + "\nUSER:" + strUser + "\nASSISTANT:" + strAssistant)
        strSystem = prevConvo + "\n\n" + strSystem
    else:
        printDebug("Prompt (after templating):\nSYSTEM:" + strSystem + "\nUSER:" + strUser + "\nASSISTANT:" + strAssistant)
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
        if shouldWriteToConversation:
            writeConversation("USER: " + strUser + "\n" + "ASSISTANT: " + strOutput)
        if sources is not None:
            printResponse("\n\n\n" + sources)
        return [False, strOutput]
    else:
        strOutput = completion.choices[0].message.content
        if shouldWriteToConversation:
            writeConversation("USER: " + strUser + "\n" + "ASSISTANT: " + strOutput)
        if sources is not None:
            strOutput = strOutput + "\n\n\n" + sources
        return [True, strOutput]


def getReply(promptIn):
    return getChatCompletion(promptIn, 0, shouldStreamText=True, infoIn=getConversation(), shouldWriteToConversation=True)


def getAnswer(promptIn, info, stream=False, sourcesIn=None):
    return getChatCompletion(promptIn, 1, shouldStreamText=stream, infoIn=info, sources=sourcesIn, shouldWriteToConversation=True)


def getTopic(promptIn):
    return getChatCompletion(promptIn, 2)[1]


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


##################################################
################### BEGIN CHAT ###################
##################################################


def checkTriggers(promptIn):
    triggerAction = "none"
    for key, value in triggerMap.items():
        for v in value:
            if v in promptIn:
                return key(promptIn)
    printInfo("No triggers detected.")
    return checkKeywords(promptIn)


def checkKeywords(promptIn):
    for key, value in keywordsMap.items():
        for trigger in value:
            if promptIn.startswith(trigger):
                return key(promptIn.replace(trigger, ""))
    printInfo("No keywords detected.")
    return getResponse(promptIn)


def getResponse(promptIn):
    return getReply(promptIn)


def detectModelsNew():
    modelList = openai.Model.list()
    for model in modelList["data"]:
        modelName = model["id"]
        if modelName not in strIgnoredModels:
            listModels.append(modelName)


def processCommand(promptIn):
    for key, value in commandMap.items():
        for v in value:
            if strPrompt == v:
                key()
                return True
    return False


##################################################
################### BEGIN MAIN ###################
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
    if strPrompt == "exit" or strPrompt == "quit":
        shouldRun = False
    elif not processCommand(strPrompt):
        response = [False, None]
        printInfo("Generating response...")
        tic = time.perf_counter()
        response = checkTriggers(strPrompt)
        toc = time.perf_counter()
        if response[0] and response[1] is not None:
            printSeparator()
            printResponse(response[1])
        printDebug(f"\n\n{toc - tic:0.3f} seconds")
