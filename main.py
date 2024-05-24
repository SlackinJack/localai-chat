import datetime
import json
import openai
import os
import re
import time


from difflib import SequenceMatcher


from modules.file_operations import *
from modules.file_reader import *
from modules.utils import *
from modules.utils_command import *
from modules.utils_web import *


# TODO:
# - Navigate to a link automatically if it is linked in a source (eg. input file)
# - rework convo names to be easier to type, autocompletion
# - clean code
# - async web fetch
# - "catch" forbidden response words "<im_start>system", etc.


#################################################
############## BEGIN CONFIGURATION ##############
#################################################


#### STATIC CONFIGURATION ####
stopwords = ["<|im_end|>"]
openai.api_key = OPENAI_API_KEY = os.environ["OPENAI_API_KEY"] = "sk-xxx"
strRespondUsingInformation = " Provide a response that is restricted to the information contained in the following input data: "
strDetermineBestAssistant = "Use the following descriptions of each assistant to determine the assistant with the most relevant skills related to the task given by USER: "

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
        if model["model_switchable"]:
            out.append(model["model_name"])
    return out


def getEnabledModelDescriptions():
    out = ""
    for model in fileModelsConfiguration:
        if model["model_switchable"]:
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
    printRed("\nYour default model is missing from models.json! Please fix your configuration.")
    exit()
intResponseTimeout = int(configuration["RESPONSE_TIMEOUT_SECONDS"])
shouldConsiderHistory = (configuration["CHAT_HISTORY_CONSIDERATION"] == "True")
shouldUseInternet = (configuration["ENABLE_INTERNET"] == "True")
intMaxSourcesPerSearch = int(configuration["MAX_SOURCES_PER_SEARCH"])
intMaxSentencesPerSource = int(configuration["MAX_SENTENCES_PER_SOURCE"])
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
    promptWithoutWebsites = promptIn
    youtubeTranscripts = []
    videoCounter = 1
    for s in promptIn.split(" "):
        for linkFormat in triggerMap[trigger_youtube]:
            if s.startswith(linkFormat):
                promptWithoutWebsites = promptWithoutWebsites.replace(s, "")
                ytId = s.replace(linkFormat, "")
                youtubeTranscripts.append("Video " + str(videoCounter) + ": " + getYouTubeCaptions(ytId))
                videoCounter += 1
    getChatCompletionResponse(promptWithoutWebsites, youtubeTranscripts, True)
    return


def trigger_browse(promptIn):
    promptWithoutWebsites = promptIn
    websiteTexts = []
    websiteCounter = 1
    for s in promptIn.split(" "):
        if s.startswith("http"):
            promptWithoutWebsites = promptWithoutWebsites.replace(s, "")
            websiteText = getInfoFromWebsite(s, True)[1]
            if checkEmptyString(websiteText):
                websiteText = errorBlankEmptyText("website")
            websiteTexts.append("Website " + str(websiteCounter) + ": " + websiteText)
            websiteCounter += 1
    getChatCompletionResponse(promptWithoutWebsites, websiteTexts, True)
    return


def trigger_openFile(promptIn):
    promptWithoutFilePaths = promptIn
    filePaths = getFilePathFromPrompt(promptIn)
    fileContents = []
    for filePath in filePaths:
        fullFileName = filePath.split("/")
        fileName = fullFileName[len(fullFileName) - 1]
        promptWithoutFilePaths = promptWithoutFilePaths.replace("'" + filePath + "'", "")
        fileContent = getFileContents(filePath)
        if checkEmptyString(fileContent):
            fileContent = errorBlankEmptyText("file")
        fileContents.append("File: '" + fileName + "': " + fileContent)
    getChatCompletionResponse(promptWithoutFilePaths, fileContents, True)
    return


triggerMap = {
    trigger_youtube: ["https://www.youtu.be/", "https://youtu.be/", "https://www.youtube.com/watch?v=", "https://youtube.com/watch?v="],
    trigger_browse: ["http://", "https://"],
    trigger_openFile: ["'/"]
}


##################################################
################# BEGIN COMMANDS #################
##################################################


def command_clear():
    i = 0
    j = 64
    while i <= j:
        printGeneric("\n")
        i += 1
    return


def command_settings():
    printGeneric("\nCurrent Settings:")
    printGeneric("\nModel: " + getCurrentModelName())
    printSetting(shouldUseInternet, "Auto Internet Search")
    printSetting(shouldAutomaticallySwitchModels, "Automatically Switch Models")
    printSetting(shouldConsiderHistory, "Consider Chat History")
    printGeneric("\nCurrent conversation file: " + strConvoName + ".convo")
    return


def command_convo():
    printGeneric("\nConversations available:\n")
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
    else:
        for conversation in convoList:
            if convoName in conversation:
                convoName = conversation
    setConversation(convoName)
    printGreen("\nConversation set to: " + convoName)
    return


def command_model():
    global currentModel
    printGeneric("\nAvailable models:\n")
    for model in fileModelsConfiguration:
        printGeneric(model["model_name"])
    printGeneric("")
    printSeparator()
    nextModel = printInput("Select a model (leave empty for current '" + getCurrentModelName() + "'): ")
    printSeparator()
    nextModelObj = None
    if len(nextModel) == 0:
        printRed("\nKeeping current model: " + getCurrentModelName())
    else:
        nextModelObj = getModelByName(nextModel)
        if nextModelObj is None:
            printRed("\nCan't find a match - keeping current model: " + getCurrentModelName())
        else:
            currentModel = nextModelObj
            printGreen("\nChat model set to: " + getCurrentModelName())
    return


def command_sd_model():
    global strModelStableDiffusion
    model = printInput("Select model for Stable Diffusion (leave empty for current '" + strModelStableDiffusion + "'): ")
    if len(model) == 0:
        model = strModelStableDiffusion
    strModelStableDiffusion = model
    printSeparator()
    printGreen("\nStable Diffusion model set to: " + model)
    # TODO: kill stablediffusion if required ?
    return


def command_online():
    global shouldUseInternet
    shouldUseInternet = not shouldUseInternet
    if shouldUseInternet:
        printGreen("\nSet to online mode!")
    else:
        printRed("\nSet to offline mode!")
    return


def command_curl():
    sendCurlCommand()
    return


def command_history():
    global shouldConsiderHistory
    shouldConsiderHistory = not shouldConsiderHistory
    if shouldConsiderHistory:
        printGreen("\nNow using chat history in prompts!")
    else:
        printRed("\nNot using chat history in prompts!")
    return


def command_switcher():
    global shouldAutomaticallySwitchModels
    shouldAutomaticallySwitchModels = not shouldAutomaticallySwitchModels
    if shouldAutomaticallySwitchModels:
        printGreen("\nNow automatically switching models!")
    else:
        printRed("\nNot automatically switching models!")
    return


def command_help():
    printGeneric("\nAvailable commands:\n")
    printGeneric(" - generate [prompt]")
    for entry, value in commandMap.items():
        commandName = value[0]
        if len(commandName) > 0:
            printGeneric(" - " + commandName)
    printGeneric(" - exit / quit")
    return


commandMap = {
    command_help: ["", "help", "?"],
    command_clear: ["clear"],
    command_convo: ["convo"],
    command_curl: ["curl"],
    command_settings: ["settings"],
    command_model: ["model"],
    command_sd_model: ["sdmodel"],
    command_online: ["online"],
    command_history: ["history"],
    command_switcher: ["switcher"]
}


#################################################
############### BEGIN COMPLETIONS ###############
#################################################


def function_action(actions_dictionary):
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
                "content": getCurrentModelSystemPrefixSuffix()[0] +
                    getCurrentModelSystemPrompt() +
                    strRespondUsingInformation + "\n" +
                    formatArrayToString(dataIn, "\n\n") +
                    getCurrentModelSystemPrefixSuffix()[1],
            }
        )
    else:
        promptHistory.append(
            {
                "role": "system",
                "content": getCurrentModelSystemPrefixSuffix()[0] +
                    getCurrentModelSystemPrompt() +
                    getCurrentModelSystemPrefixSuffix()[1],
            }
        )
    
    promptHistory.append(
        {
            "role": "user",
            "content": getCurrentModelUserPrefixSuffix()[0] +
                userPromptIn +
                getCurrentModelUserPrefixSuffix()[1],
        }
    )
    
    printDump("\nCurrent conversation:\n")
    for obj in promptHistory:
        printDump(str(obj))
    
    completion = createOpenAIChatCompletionRequest(getCurrentModelName(), promptHistory, shouldStream = True)
    
    printResponse("")
    if completion is not None:
        assistantResponse = ""
        potentialStopwords = {}
        stop = False
        pausedLetters = ""
        tic = toc = time.perf_counter()
        while not stop and (toc - tic < intResponseTimeout):
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
                            if index >= len(stopword):
                                stop = True
                            elif stopword[index] == letter:
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
                        time.sleep(0.005)
                        sys.stdout.flush()
                        assistantResponse = assistantResponse + letter
        printResponse("")
        if len(dataIn) > 0 and shouldWriteDataToConvo:
            writeConversation("SYSTEM: " + strRespondUsingInformation + "\n" + formatArrayToString(dataIn, "\n\n"))
        writeConversation("USER: " + userPromptIn)
        writeConversation("ASSISTANT: " + assistantResponse)
    return


def getFunctionResponse(promptIn):
    # new format:
    # ask the AI to make a list of actions to be completed in order to complete the task
    actionEnums = ["SEARCH_INTERNET_WITH_SEARCH_TERM"] # APPEND_TO_FILE, READ_FILE, DELETE_FILE, ...
    
    function = [
        {
            "name": "function_action",
            "parameters": {
                "type": "object",
                "properties": {
                    "actions_dictionary": {
                        "type": "array",
                        "description": "Generate an array of additional actions that need to be completed prior to responding to the prompt. Duplicate actions are allowed, only if the input data is different. If no actions are required, generate an empty array.",
                        "items": {
                            "type": "object",
                            "properties": {
                                "action": {
                                    "type": "string",
                                    "description": "The action to be completed." +
                                        " Use 'SEARCH_INTERNET_WITH_SEARCH_TERM', with a short and descriptive search term, to search for recent or additional information.",
                                    "enum": actionEnums,
                                },
                                "action_input_data": {
                                    "type": "string",
                                    "description": "The data that corresponds to this action.",
                                },
                            },
                        },
                    },
                },
                "required": ["actions_dictionary"],
            },
        },
    ]
    
    function_call = {
        "name": "function_action"
    }
    
    if shouldConsiderHistory:
        promptHistory = getPromptHistory()
    else:
        promptHistory = []
    
    printDump("\nCurrent conversation:\n")
    for obj in promptHistory:
        printDump(str(obj))
    
    prompt = [
        {
            "role": "system",
            "content": getCurrentModelSystemPrefixSuffix()[0] +
                "You are a helpful assistant." +
                " You will respond accurately and factually." +
                " Use the conversation as context, only when it is relevant to the newest prompt." +
                getCurrentModelSystemPrefixSuffix()[1]
        },
        {
            "role": "user",
            "content": promptIn,
        }
    ]
    
    resetCurrentModel()
    
    hrefs = []
    searchedTerms = []
    datas = []
    
    #while True:
    dataPrompt = []
    if len(datas) > 0:
        dataPrompt = [
            {
                "role": "system",
                "content": getCurrentModelSystemPrefixSuffix()[0] +
                    strRespondUsingInformation + "\n" +
                    formatArrayToString(datas, "\n\n") +
                    getCurrentModelSystemPrefixSuffix()[1],
            }
        ]
    fullPrompt = dataPrompt + promptHistory + prompt
    printDump("\nCurrent conversation:\n")
    for obj in fullPrompt:
        printDump(str(obj))
    actionsResponse = createOpenAIChatCompletionRequest(
        getCurrentModelName(),
        fullPrompt,
        functionsIn = function,
        functionCallIn = function_call,
    )
    
    if actionsResponse is not None and actionsResponse.get("actions_dictionary") is not None:
        for action in actionsResponse.get("actions_dictionary"):
            theAction = action.get("action")
            theActionInputData = action.get("action_input_data")
            match theAction:
                case "SEARCH_INTERNET_WITH_SEARCH_TERM":
                    if len(theActionInputData) > 0:
                        if not theActionInputData in searchedTerms:
                            searchedTerms.append(theActionInputData)
                            searchResults = getSearchResponse(theActionInputData, intMaxSourcesPerSearch, intMaxSentencesPerSource)
                            if len(searchResults) > 0:
                                for key, value in searchResults.items():
                                    if key not in hrefs:
                                        hrefs.append(key)
                                        datas.append(value)
                                        printDebug("\nAppended source data: " + key)
                                    else:
                                        printDebug("\nSkipped duplicate source: " + key)
                            else:
                                printError("\nNo search results with this search term.")
                        else:
                            #TODO: allow for search term retry
                            printError("\nDuplicated search term: " + theActionInputData)
                            printError("Breaking out of loop.")
                            break
                    else:
                        printError("\nNo search term provided.")
                case _:
                    printError("\nUnsupported action: " + action)
                    printError("Breaking out of loop.")
                    break
    else:
        printError("No response - aborting.")
        return
    if len(hrefs) < 1:
        printInfo("\nThis is an offline response!")
    
    getChatCompletionResponse(promptIn, dataIn = datas, shouldWriteDataToConvo = True)
    
    if len(hrefs) > 0:
        printResponse("\n\n\nSources analyzed:\n")
        for href in hrefs:
            printResponse(href)
    
    return


def getImageResponse(promptIn):
    #TODO: kill stablediffusion if required?
    printInfo("\nGenerating image with prompt: " + promptIn)
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
        printError("\nImage creation failed!\n")
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
                "content": strDetermineBestAssistant + getEnabledModelDescriptions()
            }
        )
        promptMessage.append(
            {
                "role": "user",
                "content": promptIn
            }
        )
        printDump("\nCurrent prompt for model response:")
        for obj in promptMessage:
            printDump(str(obj))
        printDump("\nChoices: " + grammarStringBuilder)
        nextModel = createOpenAIChatCompletionRequest(getCurrentModelName(), promptMessage, grammarIn = grammarStringBuilder)
        printDebug("\nNext model: " + nextModel)
        return getModelByName(nextModel)


##################################################
################### BEGIN CHAT ###################
##################################################


def handlePrompt(promptIn):
    if checkCommands(promptIn) == False:
        if checkTriggers(promptIn) == False:
            tic = time.perf_counter()
            if shouldUseInternet:
                getFunctionResponse(promptIn)
            else:
                printInfo("\nYou have disabled automatic internet searching! Generating offline response.")
                getChatCompletionResponse(promptIn)
            toc = time.perf_counter()
            printDebug(f"\n\n{toc - tic:0.3f} seconds")
            printGeneric("")
    return


def checkCommands(promptIn):
    for key, value in commandMap.items():
        for v in value:
            if strPrompt == v:
                key()
                return True
    printDebug("\nNo commands detected.")
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
            printDebug("\nCalling trigger: " + str(key))
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
            printDebug("\nCalling trigger: " + str(triggerToCall))
            triggerToCall(promptIn)
            return True
    printDebug("\nNo triggers detected.")
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
        handlePrompt(strPrompt)

