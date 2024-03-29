import datetime
import json
import openai
import os
import time

from difflib import SequenceMatcher

from modules.file_operations import *
from modules.file_reader import *
from modules.utils import *
from modules.utils_command import *
from modules.utils_web import *

# TODO:
# - Get more resources if the information is too short / insufficient

#################################################
############## BEGIN CONFIGURATION ##############
#################################################


#### STATIC CONFIGURATION ####
stopwords = ["<|im_end|>"]
openai.api_key = OPENAI_API_KEY = os.environ["OPENAI_API_KEY"] = "sk-xxx"
strRespondUsingInformation = " Provide a response that is restricted to the facts contained in the following input data: "


#### CONFIGURATION LOADER ####
fileConfiguration = readFile("", "config.cfg", "\n")
initConfig(fileConfiguration)


####### MODELS LOADER #######
fileModelsConfiguration = json.loads(readFile("", "models.json"))


def getModelByName(modelNameIn):
    for model in fileModelsConfiguration:
        if modelNameIn in model["model_name"] or modelNameIn == model["model_name"]:
            return model
    return None


def getCurrentModelName():
    return currentModel["model_name"]


def resetCurrentModel():
    global currentModel
    currentModel = getModelByName(configuration["DEFAULT_MODEL"])
    return


def getCurrentModelSystemPrompt():
    return currentModel["model_system_prompt"]


def getEnabledModelNames():
    out = []
    for model in fileModelsConfiguration:
        if model["model_enabled"]:
            out.append(model["model_name"])
    return out


def getEnabledModelDescriptions():
    out = ""
    for model in fileModelsConfiguration:
        if model["model_enabled"]:
            if len(out) > 0:
                out += " "
            out += model["model_description"]
    return out


def getCurrentModelSystemPrefixSuffix():
    return getCurrentModelPrefixSuffixFor("system")


def getCurrentModelUserPrefixSuffix():
    return getCurrentModelPrefixSuffixFor("user")


def getCurrentModelPrefixSuffixFor(modeIn):
    prefix = currentModel["model_" + modeIn + "_prefix"]
    suffix = currentModel["model_" + modeIn + "_suffix"]
    if prefix is None:
        prefix = ""
    if suffix is None:
        suffix = ""
    return [prefix, suffix]


##### MAIN CONFIGURATION #####
if configuration["ADDRESS"].endswith("/"):
    openai.api_base = configuration["ADDRESS"] + "v1"
else:
    openai.api_base = configuration["ADDRESS"] + "/v1"
shouldAutomaticallySwitchModels = (configuration["ENABLE_AUTOMATIC_MODEL_SWITCHING"] == "True")
currentModel = getModelByName(configuration["DEFAULT_MODEL"])
if currentModel is None:
    printRed("")
    printRed("Your default model is missing from models.json! Please fix your configuration.")
    exit()
shouldConsiderHistory = (configuration["CHAT_HISTORY_CONSIDERATION"] == "True")
shouldUseInternet = (configuration["ENABLE_INTERNET"] == "True")
intMaxLoopbackIterations = int(configuration["MAX_SEARCH_LOOPBACK_ITERATIONS"])
intMaxSources = int(configuration["MAX_SOURCES"])
intMaxSearchTerms = int(configuration["MAX_SEARCH_TERMS"])
intMaxSentences = int(configuration["MAX_SENTENCES"])
shouldAutomaticallyOpenFiles = (configuration["AUTO_OPEN_FILES"] == "True")


# STABLEDIFFUSION CONFIGURATION #
strModelStableDiffusion = configuration["STABLE_DIFFUSION_MODEL"]
strImageSize = configuration["IMAGE_SIZE"]


#################################################
############## BEGIN CONVERSATIONS ##############
#################################################


strConvoTimestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
strConvoName = strConvoTimestamp


def setConversation(filename):
    global strConvoName
    writeFile("conversations/", filename + ".convo")
    strConvoName = filename
    return


def writeConversation(strIn):
    appendFile("conversations/", strConvoName + ".convo", strIn + "\n")
    return


def getConversation():
    return readFile("conversations/", strConvoName + ".convo", "\n")


setConversation(strConvoTimestamp)


##################################################
################# BEGIN TRIGGERS #################
##################################################


def trigger_youtube(promptIn):
    for s in promptIn.split(" "):
        for linkFormat in triggerMap[trigger_youtube]:
            if s.startswith(linkFormat):
                link = s
                ytId = link.replace(linkFormat, "")
                captions = getYouTubeCaptions(ytId)
                getChatCompletionResponse(promptIn.replace(link, ""), [captions], True)
                return
    return


def trigger_browse(promptIn):
    for s in promptIn.split(" "):
        if s.startswith("http"):
            websiteText = getInfoFromWebsite(s, True)
            if checkEmptyString(websiteText):
                websiteText = errorBlankEmptyText("website")
            getChatCompletionResponse(promptIn.replace(s, ""), [websiteText], True)
            return
    return


def trigger_openFile(promptIn):
    filePath = getFilePathFromPrompt(promptIn)
    fileContents = getFileContents(filePath)
    if checkEmptyString(fileContents):
        fileContents = errorBlankEmptyText("file")
    getChatCompletionResponse(promptIn.replace(filePath, ""), [fileContents], True)
    return


triggerMap = {
    trigger_youtube: [
    "https://www.youtu.be/",
    "https://youtu.be/",
    "https://www.youtube.com/watch?v=",
    "https://youtube.com/watch?v="
    ],
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
    printGeneric("")
    printGeneric("Current Settings:\n")
    printGeneric("Model: " + getCurrentModelName())
    printSetting(shouldUseInternet, "Auto Internet Search")
    printSetting(shouldAutomaticallySwitchModels, "Automatically Switch Models")
    printSetting(shouldConsiderHistory, "Consider Chat History")
    printGeneric("")
    printGeneric("Current conversation file: " + strConvoName + ".convo")
    return


def command_convo():
    printGeneric("")
    printGeneric("Conversations available: ")
    printGeneric("")
    convoList = []
    for conversation in os.listdir("conversations"):
        if conversation.endswith(".convo"):
            convoList.append(conversation.replace(".convo", ""))
    for convo in convoList:
        printGeneric(convo)
    printGeneric("")
    printSeparator()
    convoName = printInput("Select a conversation to use, create a new one by using an unique name, or leave blank for auto-generated: ")
    printSeparator()
    if len(convoName) == 0:
        convoName = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    setConversation(convoName)
    printGreen("")
    printGreen("Conversation set to: " + convoName)
    return


def command_model():
    global currentModel
    printGeneric("")
    printGeneric("Available models:")
    printGeneric("")
    for model in fileModelsConfiguration:
        printGeneric(model["model_name"])
    printGeneric("")
    printSeparator()
    nextModel = printInput("Select a model (leave empty for current '" + getCurrentModelName() + "'): ")
    printSeparator()
    nextModelObj = None
    if len(nextModel) == 0:
        printRed("")
        printRed("Keeping current model: " + getCurrentModelName())
    else:
        nextModelObj = getModelByName(nextModel)
        if nextModelObj is None:
            printRed("")
            printRed("Can't find a match! Keeping current model: " + getCurrentModelName())
        else:
            currentModel = nextModelObj
            printGreen("")
            printGreen("Chat model set to: " + getCurrentModelName())
    return


def command_sd_model():
    global strModelStableDiffusion
    model = printInput("Select model for Stable Diffusion (leave empty for current '" + strModelStableDiffusion + "'): ")
    if len(model) == 0:
        model = strModelStableDiffusion
    strModelStableDiffusion = model
    printSeparator()
    printGreen("")
    printGreen("Stable Diffusion model set to: " + model)
    # TODO: kill stablediffusion if required ?
    return


def command_online():
    global shouldUseInternet
    shouldUseInternet = not shouldUseInternet
    if shouldUseInternet:
        printGreen("")
        printGreen("Set to online mode!")
    else:
        printRed("")
        printRed("Set to offline mode!")
    return


def command_curl():
    sendCurlCommand()
    return


def command_history():
    global shouldConsiderHistory
    shouldConsiderHistory = not shouldConsiderHistory
    if shouldConsiderHistory:
        printGreen("")
        printGreen("Now using chat history in prompts!")
    else:
        printRed("")
        printRed("Not using chat history in prompts!")
    return


def command_switcher():
    global shouldAutomaticallySwitchModels
    shouldAutomaticallySwitchModels = not shouldAutomaticallySwitchModels
    if shouldAutomaticallySwitchModels:
        printGreen("")
        printGreen("Now automatically switching models!")
    else:
        printRed("")
        printRed("Not automatically switching models!")
    return


def command_help():
    printGeneric("")
    printGeneric("Available commands:")
    printGeneric("")
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
    command_curl: [
        "curl",
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
    command_history: [
        "history",
    ],
    command_switcher: [
        "switcher",
    ]
}


#################################################
############### BEGIN COMPLETIONS ###############
#################################################


def function_result(actions, search_terms):
    return


def function_model(assistant_name):
    return


def getChatCompletionResponse(userPromptIn, dataIn = [], shouldWriteDataToConvo = False):
    nextModel = getModelResponse(userPromptIn)
    
    global currentModel
    if nextModel is not None and nextModel is not currentModel:
        currentModel = nextModel
    
    if shouldConsiderHistory:
        promptHistory = getPromptHistory()
    else:
        promptHistory = []
    
    if len(dataIn) > 0:
        promptHistory.append(
            {
                "role": "system",
                "content": getCurrentModelSystemPrefixSuffix()[0] + getCurrentModelSystemPrompt() + strRespondUsingInformation + "\n" + formatArrayToString(dataIn, "\n\n") + getCurrentModelSystemPrefixSuffix()[1],
            }
        )
    else:
        promptHistory.append(
            {
                "role": "system",
                "content": getCurrentModelSystemPrefixSuffix()[0] + getCurrentModelSystemPrompt() + getCurrentModelSystemPrefixSuffix()[1],
            }
        )
    
    promptHistory.append(
        {
            "role": "user",
            "content": getCurrentModelUserPrefixSuffix()[0] + userPromptIn + getCurrentModelUserPrefixSuffix()[1],
        }
    )
    
    printDump("")
    printDump("Current conversation:")
    printDump("")
    for obj in promptHistory:
        printDump(str(obj))
    
    completion = createOpenAIChatCompletionRequest(getCurrentModelName(), promptHistory, shouldStream = True)
    
    printResponse("")
    if completion is not None:
        assistantResponse = ""
        potentialStopwords = {}
        stop = False
        pausedLetters = ""
        # TODO: fix this
        tic = toc = time.perf_counter()
        while not stop and (toc - tic < 20.0):
            toc = time.perf_counter()
            for chunk in completion:
                letter = chunk.choices[0].delta.content
                if letter is not None:
                    pause = False
                    hasAdded = False
                    # check stop words
                    for stopword in stopwords:
                        if stopword.startswith(letter):
                            potentialStopwords[stopword] = 1
                            pausedLetters += letter
                            hasAdded = True
                            pause = True
                    # check current stop words
                    for stopword, index in potentialStopwords.items():
                        if index > 1 or not hasAdded:
                            if stopword[index] == letter:
                                potentialStopwords[stopword] = index + 1
                                pausedLetters += letter
                                pause = True
                                if index >= len(stopword) - 1:
                                    stop = True
                    if not pause and not stop:
                        if len(pausedLetters) > 0:
                            printResponse(pausedLetters, "")
                            pausedLetters = ""
                        printResponse(letter, "")
                        tic = toc
                        time.sleep(0.020)
                        sys.stdout.flush()
                        assistantResponse = assistantResponse + letter
        if len(dataIn) > 0 and shouldWriteDataToConvo:
            writeConversation("SYSTEM: " + strRespondUsingInformation + "\n" + formatArrayToString(dataIn, "\n\n"))
        writeConversation("USER: " + userPromptIn)
        writeConversation("ASSISTANT: " + assistantResponse)
    return


def getFunctionResponse(promptIn):
    # edit for additional actions later
    actionEnums = [
        "SEARCH_INTERNET_FOR_INFORMATION"
    ]
    todaysDate = datetime.datetime.now().strftime("%A, %B %d, %Y")
    actionEnumsAsString = formatArrayToString(actionEnums, ", or ")
    if shouldConsiderHistory:
        promptHistory = getPromptHistory()
    else:
        promptHistory = []
    promptHistory.append(
        {
            "role": "system",
            "content": getCurrentModelSystemPrefixSuffix()[0] + "Create a list of actions that will completed in order to respond to the current conversation. Maximum of " + str(intMaxSearchTerms) + " items." + getCurrentModelSystemPrefixSuffix()[1]
        }
    )
    promptHistory.append(
        {
            "role": "user",
            "content": promptIn,
        }
    )
    printDump("")
    printDump("Current prompt for function response:")
    printDump("")
    for obj in promptHistory:
        printDump(str(obj))
    failedCompletions = 0
    functions = [
        {
            "name": "function_result",
            "parameters": {
                "type": "object",
                "properties": {
                    "actions": {
                        "type": "array",
                        # edit for additional actions later
                        "description": "An array of actions to be completed. Maximum of " + str(intMaxSearchTerms) + " items. Use 'SEARCH_INTERNET_FOR_INFORMATION' to search for recent or additional information. Leave blank if there is nothing to do.",
                        "items": {
                            "type": "string",
                            "description": "The action.",
                            "enum": actionEnums,
                        },
                    },
                    # edit for additional actions later
                    "search_terms": {
                        "type": "array",
                        "description": "An array of search terms. Use the same number of search terms as the number of actions.",
                        "items": {
                            "type": "string",
                            "description": "The search term.",
                        },
                    },
                },
                
                "required": ["actions", "search_terms"],
            }
        }
    ]
    
    function_call = {
        "name": "function_result"
    }
    
    resetCurrentModel()
    arguments = createOpenAIChatCompletionRequest(
        getCurrentModelName(),
        promptHistory,
        functionsIn = functions,
        functionCallIn = function_call
    )
    isOnlineResponse = False
    dataCollection = {}
    hrefs = []
    if arguments is not None and arguments.get("actions") is not None:
        actions = arguments.get("actions")
        searchTerms = arguments.get("search_terms")
        while len(actions) < len(searchTerms):
            actions.insert(0, "SEARCH_INTERNET_FOR_INFORMATION")
        i = 0
        for action in actions:
            if action == "SEARCH_INTERNET_FOR_INFORMATION":
                isOnlineResponse = True
                if i < len(searchTerms) and i < intMaxSearchTerms - 1:
                    searchTerm = searchTerms[i]
                    if searchTerm is not None and len(searchTerm) > 0:
                        searchResults = getSearchResponse(searchTerm, intMaxSources, intMaxSentences)
                        if len(searchResults) > 0:
                            for key, value in searchResults.items():
                                if key not in hrefs:
                                    hrefs.append(key)
                                    dataCollection[key] = value
                                    printDump("")
                                    printDump("Appending search result: [" + key + "] " + value)
                                else:
                                    printDebug("")
                                    printDebug("Skipped duplicate source: " + key)
                        i += 1
                    else:
                        break
                else:
                    break
            else:
                # edit for additional actions later
                break
    if len(dataCollection) > 0:
        dataBuilder = []
        for key, value in dataCollection.items():
            dataBuilder.append("[From " + key + "] " + value)
        data = []
        for key, value in dataCollection.items():
            data.append(value)
    if not isOnlineResponse:
        printInfo("")
        printInfo("This is an offline response!")
        getChatCompletionResponse(promptIn)
    else:
        getChatCompletionResponse(promptIn, data, True)
    if len(hrefs) > 0:
        printResponse("")
        printResponse("\n\n\nSources analyzed:\n")
        for h in hrefs:
            printResponse(h)
    return


def getImageResponse(promptIn):
    #TODO: kill stablediffusion if required?
    printInfo("")
    printInfo("Generating image with prompt: " + promptIn)
    theURL = createOpenAIImageRequest(strModelStableDiffusion, promptIn, strImageSize)
    if theURL is not None:
        split = theURL.split("/")
        filename = split[len(split) - 1]
        urllib.request.urlretrieve(theURL, filename)
        if shouldAutomaticallyOpenFiles:
            openLocalFile(filename)
        # TODO: file management
        return "Your image is available at:\n\n" + completion.data[0].url
    else:
        printError("")
        printError("Image creation failed!")
        printError("")
        return ""


def getModelResponse(promptIn):
    if not shouldAutomaticallySwitchModels:
        return currentModel
    else:
        grammarStringBuilder = "root ::= ("
        for modelName in getEnabledModelNames():
            if len(grammarStringBuilder) > 10:
                grammarStringBuilder += " | "
            grammarStringBuilder += "\"" + modelName + "\""
        grammarStringBuilder += ")"
        promptMessage = []
        
        promptMessage.append(
            {
                "role": "system",
                "content": "Which assistant has the most relevant skills related to the task given by USER?" + """
Consider the following descriptions of each model:
""" + getEnabledModelDescriptions()
            }
        )
        promptMessage.append(
            {
                "role": "user",
                "content": promptIn
            }
        )
        printDump("")
        printDump("Current prompt for model response:")
        for obj in promptMessage:
            printDump(str(obj))
        printDump("")
        printDump("Choices: " + grammarStringBuilder)
        nextModel = createOpenAIChatCompletionRequest(getCurrentModelName(), promptMessage, grammarIn = grammarStringBuilder)
        printDump("")
        printDebug("Next model: " + nextModel)
        return getModelByName(nextModel)


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
                printInfo("")
                printInfo("You have disabled automatic internet searching! Generating offline response.")
                getChatCompletionResponse(promptIn)
    return


def checkCommands(promptIn):
    for key, value in commandMap.items():
        for v in value:
            if strPrompt == v:
                key()
                return True
    printDebug("")
    printDebug("No commands detected.")
    return False


def checkTriggers(promptIn):
    potentialTriggers = {}
    for key, value in triggerMap.items():
        for v in value:
            if v in promptIn:
                matchPercentage = SequenceMatcher(None, v, promptIn).ratio() * 100
                potentialTriggers[key] = matchPercentage
    if len(potentialTriggers) == 1:
        for key, value in potentialTriggers.items():
            printDebug("")
            printDebug("Calling trigger: " + str(key))
            key(promptIn)
            return True
    else:
        triggerToCall = None
        targetPercentage = 0
        for trigger, percentage in potentialTriggers.items():
            if triggerToCall == None:
                triggerToCall = trigger
                targetPercentage = percentage
            else:
                if percentage > targetPercentage:
                    triggerToCall = trigger
                    targetPercentage = percentage
        if triggerToCall is None:
            return False
        else:
            printDebug("")
            printDebug("Calling trigger: " + str(triggerToCall))
            triggerToCall(promptIn)
            return True
    printDebug("")
    printDebug("No triggers detected.")
    return False


def getPromptHistory():
    conversation = getConversation()
    promptHistoryStrings = []
    stringBuilder = ""
    for line in conversation:
        if line.startswith("SYSTEM: ") or line.startswith("USER: ") or line.startswith("ASSISTANT: "):
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
    return promptHistory


##################################################
################### BEGIN MAIN ###################
##################################################


command_clear()
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

