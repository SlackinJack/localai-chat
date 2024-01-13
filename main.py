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
from templates import *

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
intMaxLoopbackIterations = int(configuration["MAX_SEARCH_LOOPBACK_ITERATIONS"])
shouldUseInternet = (configuration["ENABLE_INTERNET"] == "True")
shouldUwU = (configuration["UWU_IFY"] == "True")
shouldConsiderHistory = (configuration["CHAT_HISTORY_CONSIDERATION"] == "True")

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
            writeConversation("DATA: " + websiteText)
            getChatCompletion(promptIn.replace(s, ""))
    return


def trigger_openFile(promptIn):
    filePath = getFilePathFromPrompt(promptIn)
    fileContents = getFileContents(filePath)
    printDebug("File text:\n" + fileContents)
    writeConversation("DATA: " + fileContents)
    getChatCompletion(promptIn.replace(filePath, ""))
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


def command_clear():
    i = 0
    j = 64
    while i <= j:
        printGeneric("\n")
        i +=1
    return


def command_convo():
    convoList = []
    for conversation in os.listdir("conversations"):
        if conversation.endswith(".convo"):
            convoList.append(conversation.replace(".convo", ""))
    printGeneric("Conversations available: ")
    for convo in convoList:
        printGeneric(convo)
    printSeparator()
    convoName = printInput("Select a conversation to use, create a new one by using an unique name, or leave blank for auto-generated: ")
    printSeparator()
    if len(convoName) == 0:
        convoName = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    setConversation(convoName)
    printSuccess("Conversation set to: " + convoName)
    return


def command_chat_model():
    # TODO: autofill model names
    global strModelChat
    printGeneric("Available models: " + str(listModels))
    printGeneric("Tip: you can type partial names.")
    printSeparator()
    model = printInput("Select model for chat (leave empty for current '" + strModelChat + "'): ")
    if len(model) == 0:
        model = strModelChat
    else:
        testModel = modelAutocomplete(model)
        if testModel is not None:
            model = testModel
        else:
            printError("Model not found! Keeping current model '" + strModelChat + "'")
            return
    strModelChat = model
    printSeparator()
    printSuccess("Chat model set to: " + model)
    return


def command_comp_model():
    # TODO: autofill model names
    global strModelCompletion
    printGeneric("Available models: " + str(listModels))
    printGeneric("Tip: you can type partial names.")
    printSeparator()
    model = printInput("Select model for chat (leave empty for current '" + strModelCompletion + "'): ")
    if len(model) == 0:
        model = strModelCompletion
    else:
        testModel = modelAutocomplete(model)
        if testModel is not None:
            model = testModel
        else:
            printError("Model not found! Keeping current model '" + strModelCompletion + "'")
            return
    strModelCompletion = model
    printSeparator()
    printSuccess("Completion model set to: " + model)
    return


def command_sd_model():
    global strModelStableDiffusion
    printSeparator()
    model = printInput("Select model for Stable Diffusion (leave empty for current '" + strModelStableDiffusion + "'): ")
    if len(model) == 0:
        model = strModelStableDiffusion
    strModelStableDiffusion = model
    printSeparator()
    printSuccess("Stable Diffusion model set to: " + model)
    return


def modelAutocomplete(modelNameIn):
    for model in listModels:
        if model.startswith(modelNameIn) or model == modelNameIn:
            return model
    return None


def command_offline():
    global shouldUseInternet
    shouldUseInternet = False
    printRed("Set to offline mode!")
    return


def command_online():
    global shouldUseInternet
    shouldUseInternet = True
    printSuccess("Set to online mode!")
    return


def command_historyon():
    global shouldConsiderHistory
    shouldConsiderHistory = True
    printSuccess("Now using chat history in prompts!")
    return


def command_historyoff():
    global shouldConsiderHistory
    shouldConsiderHistory = False
    printRed("Not using chat history in prompts!")
    return


def command_help():
    printGeneric("Available commands:")
    for entry, value in commandMap.items():
        commandName = value[0]
        if len(commandName) > 0:
            printGeneric(" - " + commandName)
    printGeneric(" - exit / quit")
    return


commandMap = {
    command_help: [
        "",
        "help",
        "?",
    ],
    command_clear: [
        "clear",
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
    command_historyon: [
        "historyon",
    ],
    command_historyoff: [
        "historyoff",
    ],
}


def getChatCompletion(userPromptIn):
    if shouldUwU:
        systemPrompt = templateChatCompletionSystemUwU
    else:
        systemPrompt = templateChatCompletionSystem
    if shouldConsiderHistory:
        promptHistory = getPromptHistory()
    else:
        promptHistory = []
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
    #promptHistory.append(
    #    {
    #        "role": "assistant",
    #        "content": "",
    #    }
    #)
    completion = openai.ChatCompletion.create(
        model = strModelChat,
        stream = True,
        messages = promptHistory,
    )
    assistantResponse = ""
    
    for chunk in completion:
        if chunk.choices[0].delta.content is not None:
            printResponse(chunk.choices[0].delta.content, "", modifier = shouldUwU)
            time.sleep(0.020)
            sys.stdout.flush()
            assistantResponse = assistantResponse + chunk.choices[0].delta.content
    writeConversation("USER: " + userPromptIn)
    writeConversation("ASSISTANT: " + assistantResponse)
    return


availableFunctions = [
    {
        "name": "function_result",
        "description": templateFunctionResponseDescription,
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
                    "description": templateFunctionResponseSearchTerms,
                },
            },
            "required": ["action", "search_terms"],
        },
    },
]


def function_result(action, search_terms):
    return


def getFunctionResponse(promptIn):
    timesSearched = 0
    searchedTerms = []
    hrefs = []
    while True:
        if shouldConsiderHistory:
            promptHistory = getPromptHistory()
        else:
            promptHistory = []
        promptHistory.append(
            {
                "role": "system",
                "content": templateFunctionResponseSystem,
            }
        )
        promptHistory.append(
            {
                "role": "user",
                "content": promptIn,
            }
        )
        #promptHistory.append(
        #    {
        #        "role": "assistant",
        #        "content": "",
        #    }
        #)
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
        if arguments.get("action"):
            match arguments.get("action"):
                case "REPLY_TO_CONVERSATION":
                    break
                case "SEARCH_INTERNET_FOR_ADDITIONAL_INFORMATION":
                    currentSearchString = arguments.get("search_terms")
                    if currentSearchString in searchedTerms:
                        printError("Duplicated previous search terms! Breaking out of loop.")
                        break
                    else:
                        searchedTerms.append(currentSearchString)
                        searchResults = getSearchResponse(currentSearchString, intMaxSources, intMaxSentences)
                        if len(searchResults) > 0:
                            for key, value in searchResults.items():
                                if key not in hrefs:
                                    hrefs.append(key)
                                    writeConversation("DATA: " + "(From " + key + ")" + value)
                                else:
                                    printDebug("Skipped duplicate source: " + key)
                        timesSearched += 1
                        if not shouldLoopbackSearch:
                            printInfo("You have search loopback disabled. Breaking out of loop.")
                            break
                        elif timesSearched >= intMaxLoopbackIterations:
                            printInfo("Maximum number of searches reached! Breaking out of loop.")
                            break
                        else:
                            printDebug("Looping back with search results.")
        else:
            printError("Function generation failed! Defaulting to chat generation.")
    getChatCompletion(promptIn)
    if len(hrefs) > 0:
        printSuccess("\n\n\nSources analyzed:\n")
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
                printInfo("You have disabled automatic internet searching! Generating offline response.")
                getChatCompletion(promptIn)
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
                printDebug("Calling trigger: " + str(key))
                key(promptIn)
                return True
    printDebug("No triggers detected.")
    return False


def getResponse(promptIn):
    return getReply(promptIn)


def getPromptHistory():
    conversation = getConversation()
    promptHistoryStrings = []
    stringBuilder = ""
    for line in conversation:
        if line.startswith("SYSTEM: ") or line.startswith("USER: ") or line.startswith("ASSISTANT: ") or line.startswith("DATA: " ):
            if len(stringBuilder) == 0:
                stringBuilder += line
            else:
                promptHistoryStrings.append(stringBuilder)
                stringBuilder = "" + line
        else:
            stringBuilder += line
    promptHistoryStrings.append(stringBuilder)
    promptHistory = []
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
            elif entry.startswith("DATA: "):
                promptHistory.append(
                    {
                        "role": "data",
                        "content": entry.replace("DATA: ", "", 1),
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
printInfo("")
printInfo("Current model settings:")
printInfo("[CHAT] " + strModelChat)
printInfo("[COMP] " + strModelCompletion)
printInfo("[STDF] " + strModelStableDiffusion)


while True:
    printInfo("")
    printInfo("Current settings:")
    if shouldUseInternet:
        printInfo("[ON] Auto Internet Search")
    else:
        printInfo("[OFF] Auto Internet Search")
    if shouldConsiderHistory:
        printInfo("[ON] Consider Chat History")
    else:
        printInfo("[OFF] Consider Chat History")
    printInfo("")
    printInfo("Current conversation file: " + strConvoName + ".convo")
    printInfo("")
    printSeparator()
    strPrompt = printInput("Enter a prompt ('help' for list of commands): ")
    printSeparator()
    if strPrompt == "exit" or strPrompt == "quit":
        break
    else:
        tic = time.perf_counter()
        handlePrompt(strPrompt)
        toc = time.perf_counter()
        printDebug(f"\n\n{toc - tic:0.3f} seconds")
        printGeneric("")

