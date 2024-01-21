import datetime
import json
import openai
import os
import time

from pathlib import Path

from modules.openfile import *
from modules.search import *
from modules.utils import *


# TODO:
# split input file first then prompt after
# openfile trigger -> upload files to server, then parse from server
# add back autocomplete for model command


lastModelUsed = ""
openai.api_key = OPENAI_API_KEY = "sk-xxx"
os.environ["OPENAI_API_KEY"] = "sk-xxx"


#################################################
############## BEGIN CONFIGURATION ##############
#################################################


#### CONFIGURATION LOADER ####
fileConfig = open("config.cfg", "r")
fileConfiguration = (fileConfig.read()).split("\n")
fileConfig.close()
initConfig(fileConfiguration)


####### MODELS LOADER #######
fileModels = open("models.json", "r")
fileModelsConfiguration = json.loads(fileModels.read())
fileModels.close()
modelsEnum = []
modelsDescriptions = ""
for obj in fileModelsConfiguration:
    modelsEnum.append(obj["name"])
    modelsDescriptions += obj["description"] + "\n"


##### MAIN CONFIGURATION #####
openai.api_base = configuration["ADDRESS"]
shouldAutomaticallySwitchModels = (configuration["ENABLE_AUTOMATIC_MODEL_SWITCHING"] == "True")
strModelDefault = configuration["DEFAULT_MODEL"]
shouldConsiderHistory = (configuration["CHAT_HISTORY_CONSIDERATION"] == "True")
shouldUseInternet = (configuration["ENABLE_INTERNET"] == "True")
shouldLoopbackSearch = (configuration["SEARCH_LOOPBACK"] == "True")
intMaxLoopbackIterations = int(configuration["MAX_SEARCH_LOOPBACK_ITERATIONS"])
intMaxSources = int(configuration["MAX_SOURCES"])
intMaxSentences = int(configuration["MAX_SENTENCES"])
shouldAutomaticallyOpenFiles = (configuration["AUTO_OPEN_FILES"] == "True")
shouldUwU = (configuration["UWU_IFY"] == "True")


# STABLEDIFFUSION CONFIGURATION #
strModelStableDiffusion = configuration["STABLE_DIFFUSION_MODEL"]
strImageSize = configuration["IMAGE_SIZE"]


### TEMPLATE CONFIGURATION ###
strTemplateFunctionResultSearchTermsDescription = configuration["TEMPLATE_FUNCTION_RESULT_SEARCH_TERMS_DESCRIPTION"]
strTemplateFunctionResponseSystemPrompt = configuration["TEMPLATE_FUNCTION_RESULT_SYSTEM_PROMPT"]
strTemplateChatCompletionSystemPrompt = configuration["TEMPLATE_CHAT_COMPLETION_SYSTEM_PROMPT"]
strTemplateChatCompletionSystemPromptUwU = configuration["TEMPLATE_CHAT_COMPLETION_SYSTEM_PROMPT_UWU"]
strTemplateModelSystemPrompt = configuration["TEMPLATE_MODEL_SYSTEM_PROMPT"]


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


def errorBlankEmptyText(sourceIn):
    printError("The " + sourceIn + " is empty/blank!")
    return "The text received from the " + sourceIn + " is blank and/or empty. Notify the user about this."


def trigger_browse(promptIn):
    for s in promptIn.split(" "):
        if s.startswith("http"):
            websiteText = getInfoFromWebsite(s, True)
            if checkEmptyString(websiteText):
                websiteText = errorBlankEmptyText("website")
            getChatCompletionResponse(promptIn.replace(s, ""), [websiteText], True)
    return


def trigger_openFile(promptIn):
    filePath = getFilePathFromPrompt(promptIn)
    fileContents = getFileContents(filePath)
    if checkEmptyString(fileContents):
        fileContents = errorBlankEmptyText("file")
    getChatCompletionResponse(promptIn.replace(filePath, ""), [fileContents], True)
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


def command_settings():
    printGeneric("Current Settings:\n")
    printGeneric("Model: " + strModelDefault)
    printSetting(shouldUseInternet, "Auto Internet Search")
    printSetting(shouldAutomaticallySwitchModels, "Automatically Switch Models")
    printSetting(shouldConsiderHistory, "Consider Chat History")
    printGeneric("")
    printGeneric("Current conversation file: " + strConvoName + ".convo")
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
    printGreen("Conversation set to: " + convoName)
    return


def command_model():
    global strModelDefault
    model = printInput("Select the default model (leave empty for current '" + strModelDefault + "'): ")
    if len(model) == 0:
        model = strModelDefault
    if lastModelUsed != model:
        killLlama()
    strModelDefault = model
    printSeparator()
    printGreen("Chat model set to: " + model)
    return


def command_sd_model():
    global strModelStableDiffusion
    printSeparator()
    model = printInput("Select model for Stable Diffusion (leave empty for current '" + strModelStableDiffusion + "'): ")
    if len(model) == 0:
        model = strModelStableDiffusion
    strModelStableDiffusion = model
    printSeparator()
    printGreen("Stable Diffusion model set to: " + model)
    # TODO: kill stablediffusion if required ?
    return


def command_offline():
    global shouldUseInternet
    shouldUseInternet = False
    printRed("Set to offline mode!")
    return


def command_online():
    global shouldUseInternet
    shouldUseInternet = True
    printGreen("Set to online mode!")
    return


def command_historyon():
    global shouldConsiderHistory
    shouldConsiderHistory = True
    printGreen("Now using chat history in prompts!")
    return


def command_historyoff():
    global shouldConsiderHistory
    shouldConsiderHistory = False
    printRed("Not using chat history in prompts!")
    return


def command_switcheron():
    global shouldAutomaticallySwitchModels
    shouldAutomaticallySwitchModels = True
    printGreen("Now automatically switching models!")
    return


def command_switcheroff():
    global shouldAutomaticallySwitchModels
    shouldAutomaticallySwitchModels = False
    printRed("Not automatically switching models!")
    return


def command_help():
    printGeneric("Available commands:")
    printGeneric(" - generate [prompt]")
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
    command_settings: [
        "settings",
    ],
    command_model: [
        "model",
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
    command_switcheron: [
        "switcheron",
    ],
    command_switcheroff: [
        "switcheroff",
    ],
}


#################################################
############### BEGIN COMPLETIONS ###############
#################################################


def function_result(action, search_terms):
    return


def function_model(assistant_name):
    return


def getChatCompletionResponse(userPromptIn, dataIn = [], shouldWriteDataToConvo = False):
    modelToUse = getModelResponse(userPromptIn)
    global lastModelUsed
    if lastModelUsed != modelToUse:
        lastModelUsed = modelToUse
        killLlama()
    if shouldUwU:
        systemPrompt = strTemplateChatCompletionSystemPromptUwU
    else:
        systemPrompt = strTemplateChatCompletionSystemPrompt
    if shouldConsiderHistory:
        promptHistory = getPromptHistory()
    else:
        promptHistory = []
    if len(dataIn) > 0:
        for data in dataIn:
            promptHistory.append(
                {
                    "role": "data",
                    "content": data,
                }
            )
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
    printDump("Current conversation:")
    for obj in promptHistory:
        printDump(str(obj))
    failedCompletions = 0
    while True:
        try:
            completion = openai.ChatCompletion.create(
                model = modelToUse,
                stream = True,
                messages = promptHistory,
            )
            break
        except Exception as e:
            if failedCompletions < 3:
                printError("Failed to create completion! Trying again...")
                printError(str(e))
                time.sleep(3)
            else:
                printError("Failed to create completion after 3 tries!")
                printError(str(e))
                return
    assistantResponse = ""
    for chunk in completion:
        if chunk.choices[0].delta.content is not None:
            printResponse(chunk.choices[0].delta.content, "", modifier = shouldUwU)
            time.sleep(0.020)
            sys.stdout.flush()
            assistantResponse = assistantResponse + chunk.choices[0].delta.content
    if len(dataIn) > 0 and shouldWriteDataToConvo:
        writeConversation("DATA: " + dataIn)
    writeConversation("USER: " + userPromptIn)
    writeConversation("ASSISTANT: " + assistantResponse)
    return


def getFunctionResponse(promptIn):
    global lastModelUsed
    if lastModelUsed != strModelDefault:
        lastModelUsed = strModelDefault
        killLlama()
    timesSearched = 0
    searchedTerms = []
    hrefs = []
    dataCollection = {}
    tries = 0
    while True:
        if shouldConsiderHistory:
            promptHistory = getPromptHistory()
        else:
            promptHistory = []
        promptHistory.append(
            {
                "role": "system",
                "content": strTemplateFunctionResponseSystemPrompt,
            }
        )
        promptHistory.append(
            {
                "role": "user",
                "content": promptIn,
            }
        )
        failedCompletions = 0
        while True:
            try:
                completion = openai.ChatCompletion.create(
                    model = strModelDefault,
                    messages = promptHistory,
                    functions = [
                        {
                            "name": "function_result",
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
                                        "description": strTemplateFunctionResultSearchTermsDescription,
                                    },
                                },
                                "required": ["action", "search_terms"],
                            },
                        },
                    ],
                    function_call = {
                        "name": "function_result",
                    },
                )
                break
            except Exception as e:
                if failedCompletions < 3:
                    printError("Failed to create completion! Trying again...")
                    printError(str(e))
                    time.sleep(3)
                else:
                    printError("Failed to create completion after 3 tries!")
                    printError(str(e))
                    return
        printDump("Current conversation:")
        for obj in promptHistory:
            printDump(str(obj))
        arguments = json.loads(completion.choices[0].message.function_call.arguments)
        if arguments is not None and arguments.get("action") is not None:
            printInfo("Next determined action is: " + arguments.get("action"))
            if arguments.get("action") in "REPLY_TO_CONVERSATION":
                break
            elif arguments.get("action") in "SEARCH_INTERNET_FOR_ADDITIONAL_INFORMATION":
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
                                dataCollection[key] = value
                                printDump("Appending search result: [" + key + "] " + value)
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
                printError("This action is invalid/unsupported! Breaking out of loop.")
                break
            tries = 0
        else:
            if tries < 3:
                printError("Function generation failed! Trying again...")
                tries += 1
                time.sleep(3)
            else:
                printError("Function generation failed after 3 attempts! Defaulting to chat generation.")
                break
    data = []
    for key, value in dataCollection.items():
        data.append(value)
    getChatCompletionResponse(promptIn, data, False)
    if len(hrefs) > 0:
        printResponse("\n\n\nSources analyzed:\n")
        for h in hrefs:
            printResponse(h)
    for key, value in dataCollection.items():
        writeConversation("DATA: " + "(From " + key + ")" + value)
    return


def getImageResponse(promptIn):
    #TODO: kill stablediffusion if required?
    printInfo("Generating image with prompt: " + promptIn)
    failedCompletions = 0
    while True:
        try:
            completion = openai.Image.create(
                model = strModelStableDiffusion,
                prompt = promptIn,
                size = strImageSize,
            )
            break
        except Exception as e:
            if failedCompletions < 3:
                printError("Failed to create completion! Trying again...")
                printError(str(e))
                time.sleep(3)
            else:
                printError("Failed to create completion after 3 tries!")
                printError(str(e))
                return
    theURL = completion.data[0].url
    split = theURL.split("/")
    filename = split[len(split) - 1]
    urllib.request.urlretrieve(theURL, filename)
    if shouldAutomaticallyOpenFiles:
        openLocalFile(filename)
    # TODO: file management
    return "Your image is available at:\n\n" + completion.data[0].url


def getModelResponse(promptIn):
    global lastModelUsed
    if lastModelUsed != strModelDefault:
        lastModelUsed = strModelDefault
        killLlama()
    if not shouldAutomaticallySwitchModels:
        return strModelDefault
    else:
        grammarStringBuilder = "root ::= ("
        i = 0
        while i < len(modelsEnum) - 1:
            modelName = modelsEnum[i]
            printDump("Adding model to grammar: " + modelName)
            grammarStringBuilder += "\"" + modelName + "\" | "
            i += 1
        lastModel = modelsEnum[len(modelsEnum) - 1]
        printDump("Adding model to grammar: " + lastModel)
        grammarStringBuilder += "\"" + lastModel + "\")"
        promptMessage = []
        promptMessage.append(
            {
                "role": "data",
                "content": modelsDescriptions
            }
        )
        promptMessage.append(
            {
                "role": "system",
                "content": strTemplateModelSystemPrompt
            }
        )
        promptMessage.append(
            {
                "role": "user",
                "content": promptIn
            }
        )
        for obj in promptMessage:
            printDump(str(obj))
        printDump("Choices: " + grammarStringBuilder)
        failedCompletions = 0
        while True:
            try:
                completion = openai.ChatCompletion.create(
                    model = strModelDefault,
                    messages = promptMessage,
                    grammar = grammarStringBuilder
                )
                break
            except Exception as e:
                if failedCompletions < 3:
                    printError("Failed to create completion! Trying again...")
                    printError(str(e))
                    time.sleep(3)
                else:
                    printError("Failed to create completion after 3 tries!")
                    printError(str(e))
                    return
        model = completion.choices[0].message.content
        printDebug("Determined model: " + model)
        return model


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
                getChatCompletionResponse(promptIn)
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


printGeneric("")
command_settings()
printGeneric("")


while True:
    printSeparator()
    strPrompt = printInput("Enter a prompt ('help' for list of commands): ")
    printSeparator()
    if strPrompt == "exit" or strPrompt == "quit":
        break
    elif strPrompt.startswith("generate"):
        tic = time.perf_counter()
        getImageResponse(strPrompt.replace("generate ", ""))
        toc = time.perf_counter()
    else:
        tic = time.perf_counter()
        handlePrompt(strPrompt)
        toc = time.perf_counter()
        printDebug(f"\n\n{toc - tic:0.3f} seconds")
        printGeneric("")

