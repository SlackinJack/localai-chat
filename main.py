import datetime
import json
import openai
import os
import re
import time

from pathlib import Path

from modules.openfile import *
from modules.search import *
from modules.templates import *
from modules.utils import *

# TODO:
# add error-catch to completion requests

listModels = []


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
shouldLoopbackSearch = (configuration["SEARCH_LOOPBACK"] == "True")
shouldUseInternet = (configuration["ENABLE_INTERNET"] == "True")
shouldUwU = (configuration["UWU_IFY"] == "True")

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
    return


def writeConversation(strIn):
    fileConvo = open("conversations/" + strConvoName + ".convo", "a")
    fileConvo.write(strIn + "\n")
    fileConvo.close()
    return


def getConversation():
    fileConvo = open("conversations/" + strConvoName + ".convo", "r")
    fileConversation = (fileConvo.read()).split("\n")
    fileConvo.close()
    return fileConversation


setConversation(strConvoTimestamp)


##################################################
################# BEGIN TRIGGERS #################
##################################################


def trigger_browse(promptIn):
    for s in promptIn.split(" "):
        if s.startswith("http"):
            websiteText = getInfoFromWebsite(s, True)
            printDebug("Website text:\n" + websiteText)
            getChatCompletion(promptIn.replace(s, ""), strModelChat, additionalInfo = "Consider the following text in your response: " + websiteText)
    return


def trigger_openFile(promptIn):
    filePath = getFilePathFromPrompt(promptIn)
    fileContents = getFileContents(filePath)
    printDebug("File text:\n" + fileContents)
    getChatCompletion(promptIn.replace(filePath, ""), strModelChat, additionalInfo = "Consider the following text in your response: " + fileContents)
    # TODO: non-local files
    return


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
    printGeneric("convo")
    printGeneric("chatmodel")
    printGeneric("compmodel")
    printGeneric("sdmodel")
    printGeneric("exit/quit")
    return


def command_convo():
    convoList = []
    for conversation in os.listdir("conversations"):
        if conversation.endswith(".convo"):
            convoList.append(conversation.replace(".convo", ""))
    printGeneric("Conversations available: ")
    for convo in convoList:
        printGeneric(convo)
    convoName = printInput("Select a conversation to use, create a new one by using an unique name, or leave blank for auto-generated: ")
    if len(convoName) == 0:
        convoName = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    setConversation(convoName)
    printSuccess("Conversation set to: " + convoName)
    return


def command_chat_model():
    global strModelChat
    printGeneric("Available models: " + str(listModels))
    model = printInput("Select model for chat (leave empty for current '" + strModelChat + "'): ")
    if len(model) == 0:
        model = strModelChat
    strModelChat = model
    printSuccess("Chat model set to: " + model)
    return


def command_comp_model():
    global strModelCompletion
    printGeneric("Available models: " + str(listModels))
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


def command_offline():
    global shouldUseInternet
    shouldUseInternet = False
    printError("Set to offline mode!")
    return


def command_online():
    global shouldUseInternet
    shouldUseInternet = True
    printSuccess("Set to online mode!")
    return


commandMap = {
    command_help: [
        "",
        "help",
        "?",
    ],
    command_convo: [
        "convo",
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
    command_online: [
        "online",
    ],
    command_offline: [
        "offline",
    ],
}


def getChatCompletion(userPromptIn, modelIn, additionalInfo=""):
    if shouldUwU:
        systemPrompt = templateChatCompletionSystemUwU + additionalInfo
    else:
        systemPrompt = templateChatCompletionSystem + additionalInfo
    promptHistory = getPromptHistory()
    promptHistory.append(
        {
            "role": "system",
            "content": systemPrompt,
        }
    )
    promptHistory.append(
        {
            "role": "user",
            "content": userPromptIn,
        }
    )
    completion = openai.ChatCompletion.create(
        model = modelIn,
        stream = True,
        messages = promptHistory,
    )
    assistantResponse = ""
    for chunk in completion:
        if chunk.choices[0].delta.content is not None:
            printResponse(chunk.choices[0].delta.content, "", modifier = shouldUwU)
            time.sleep(0.025)
            sys.stdout.flush()
            assistantResponse = assistantResponse + chunk.choices[0].delta.content
    writeConversation("SYSTEM: " + systemPrompt)
    writeConversation("USER: " + userPromptIn)
    writeConversation("ASSISTANT: " + assistantResponse)
    return


availableFunctions = [
    {
        "name": "function_result",
        "description": "Determine the next appropriate action.",
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": [
                        "REPLY_TO_CONVERSATION",
                        "SEARCH_INTERNET_FOR_ADDITIONAL_INFORMATION",
                    ],
                },
                "search_terms": {
                    "type": "string",
                    "description": """
                        You will generate a keyword, or a short search term, for the topic or question that you are trying to answer.
                        It must be related to the needs or the inquiry from USER.
                        It must be short, precise and specific, while being adaquately descriptive.
                        You must consider the context of the current conversation when it is relevant.
                    """,
                },
            },
            "required": ["action", "search_terms"],
        },
    },
]


def function_result(action, search_terms):
    return


def getFunctionResponse(promptIn):
    searchedTerms = []
    additionalPrompts = "" 
    hrefs = []
    while True:
        promptHistory = getPromptHistory()
        promptHistory.append(
            {
                "role": "system",
                "content": templateFunctionResponseSystem + additionalPrompts,
            }
        )
        promptHistory.append(
            {
                "role": "user",
                "content": promptIn,
            }
        )
        completion = openai.ChatCompletion.create(
            model = strModelCompletion,
            messages = promptHistory,
            functions = availableFunctions,
            function_call = {
                "name": "function_result",
            },
        )
        arguments = json.loads(completion.choices[0].message.function_call.arguments)
        printInfo("Next determined action is: " + arguments.get("action"))
        match arguments.get("action"):
            case "REPLY_TO_CONVERSATION":
                break
            case "SEARCH_INTERNET_FOR_ADDITIONAL_INFORMATION":
                currentSearchString = arguments.get("search_terms")
                if currentSearchString in searchedTerms:
                    printError("Searching for the same search terms! Breaking out of loop.")
                    break
                else:
                    searchedTerms.append(currentSearchString)
                    searchResults = getSearchResponse(currentSearchString, intMaxSources, intMaxSentences)
                    if len(searchResults) > 0:
                        for key, value in searchResults.items():
                            additionalPrompts += "\nThe following is a search result - consider this in your next response: " + value + "(" + key + ")"
                            hrefs.append(key)
                    if not shouldLoopbackSearch:
                        printInfo("You have search loopback disabled, not searching anymore.")
                        break
                    else:
                        printDebug("Looping back with search results.")
    getChatCompletion(promptIn, strModelChat)
    if len(hrefs) > 0:
        printSuccess("Sources:\n")
        for h in hrefs:
            printSuccess(h)
    return


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
    # TODO: file management
    return "Your image is available at:\n\n" + completion.data[0].url


##################################################
################### BEGIN CHAT ###################
##################################################


def handlePrompt(promptIn):
    if checkCommands(promptIn) == False:
        if checkTriggers(promptIn) == False:
            # TODO:
            # may need to change this later
            # if there are more functions that
            # use the internet
            if shouldUseInternet:
                getFunctionResponse(promptIn)
            else:
                printInfo("You have disabled internet access! Generating offline response.")
                getChatCompletion(promptIn, strModelChat)
    return


def checkCommands(promptIn):
    for key, value in commandMap.items():
        for v in value:
            if strPrompt == v:
                key()
                return True
    printDebug("No commands detected.")
    return False


def checkTriggers(promptIn):
    for key, value in triggerMap.items():
        for v in value:
            if v in promptIn:
                printDebug("Calling trigger: " + key)
                key(promptIn)
                return True
    printDebug("No triggers detected.")
    return False


def getResponse(promptIn):
    return getReply(promptIn)


def getPromptHistory():
    conversation = getConversation()
    promptHistoryStrings = []
    promptHistory = []
    stringBuilder = ""
    for line in conversation:
        if line.startswith("SYSTEM: ") or line.startswith("USER: ") or line.startswith("ASSISTANT: "):
            if len(stringBuilder) == 0:
                stringBuilder += line
            else:
                promptHistoryStrings.append(stringBuilder)
                stringBuider = line
        else:
            stringBuilder += line
    promptHistoryStrings.append(stringBuilder)
    for entry in promptHistoryStrings:
        if len(entry) > 0:
            if entry.startswith("SYSTEM: "):
                promptHistory.append(
                    {
                        "role": "system",
                        "content": entry.replace("SYSTEM: ", "", 1),
                    }
                )
            elif entry.startswith("USER: "):
                promptHistory.append(
                    {
                        "role": "user",
                        "content": entry.replace("USER: ", "", 1),
                    }
                )
            elif entry.startswith("ASSISTANT: "):
                promptHistory.append(
                    {
                        "role": "assistant",
                        "content": entry.replace("ASSISTANT: ", "", 1),
                    }
                )
    return promptHistory


##################################################
################### BEGIN MAIN ###################
##################################################


def detectModelsNew():
    modelList = openai.Model.list()
    for model in modelList["data"]:
        modelName = model["id"]
        if modelName not in strIgnoredModels:
            listModels.append(modelName)
    return


detectModelsNew()


if len(strModelChat) == 0:
    strModelChat = listModels[0]
if len(strModelCompletion) == 0:
    strModelCompletion = listModels[0]
printInfo("Chat model ('chatmodel' to change): " + strModelChat)
printInfo("Comp model ('compmodel' to change): " + strModelCompletion)
printInfo("SD model ('sdmodel' to change): " + strModelStableDiffusion)


while True:
    printInfo("Current conversation file: " + strConvoName + ".convo")
    if shouldUseInternet:
        printInfo("Internet access is enabled.")
    else:
        printInfo("Internet access is disabled.")
    printSeparator()
    strPrompt = printInput("Enter a prompt ('help' for list of commands): ")
    printSeparator()
    if strPrompt == "exit" or strPrompt == "quit":
        break
    else:
        printInfo("Generating response...")
        tic = time.perf_counter()
        handlePrompt(strPrompt)
        toc = time.perf_counter()
        printDebug(f"\n\n{toc - tic:0.3f} seconds")

