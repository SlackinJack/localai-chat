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
# - rework convo names to be easier to type
# - clean code
# - fix target links being smashed together


#################################################
############## BEGIN CONFIGURATION ##############
#################################################


#### STATIC CONFIGURATION ####
stopwords = ["|im_end>", "\n\n\n\n\n", "</s>"]
openai.api_key = OPENAI_API_KEY = os.environ["OPENAI_API_KEY"] = "sk-xxx"
strRespondUsingInformation = "Provide a response that is restricted to the information contained in the following data: "
strDetermineBestAssistant = "Use the following descriptions of each assistant to determine which assistant has the most relevant skills related to the task given by USER: "


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


##### MAIN CONFIGURATION #####
currentModel = getModelByName(configuration["DEFAULT_MODEL"])
if currentModel is None:
    printRed("\nYour default model is missing from models.json! Please fix your configuration.")
    exit()


if not configuration["ADDRESS"].endswith("/v1"):
    newAddress = configuration["ADDRESS"]
    if not newAddress.endswith("/"):
        newAddress += "/"
    openai.api_base = newAddress + "v1"


strSystemPrompt                 =    (configuration["SYSTEM_PROMPT"])
intResponseTimeout              = int(configuration["RESPONSE_TIMEOUT_SECONDS"])
shouldAutomaticallySwitchModels =    (configuration["ENABLE_AUTOMATIC_MODEL_SWITCHING"].lower() == "true")
shouldConsiderHistory           =    (configuration["CHAT_HISTORY_CONSIDERATION"].lower() == "true")
shouldUseInternet               =    (configuration["ENABLE_INTERNET"].lower() == "true")
intMaxSourcesPerSearch          = int(configuration["MAX_SOURCES_PER_SEARCH"])
intMaxSentencesPerSource        = int(configuration["MAX_SENTENCES_PER_SOURCE"])
shouldAutomaticallyOpenFiles    =    (configuration["AUTO_OPEN_FILES"].lower() == "true")


# STABLEDIFFUSION CONFIGURATION #
strModelStableDiffusion         =    (configuration["STABLE_DIFFUSION_MODEL"])
strImageSize                    =    (configuration["IMAGE_SIZE"])


def printCurrentSystemPrompt(printer, space = ""):
    if len(strSystemPrompt) > 0:
        printer(strSystemPrompt + space)
    else:
        printer("(Empty)" + space)
    return


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
    detectedWebsites = []
    for filePath in filePaths:
        fullFileName = filePath.split("/")
        fileName = fullFileName[len(fullFileName) - 1]
        promptWithoutFilePaths = promptWithoutFilePaths.replace("'" + filePath + "'", "")
        fileContent = getFileContents(filePath)
        if checkEmptyString(fileContent):
            fileContent = errorBlankEmptyText("file")
        else:
            words = fileContent.split("http")
            endHttpLetters = " )]}>"
            for word in words:
                if word.startswith("://") or word.startswith("s://"):
                    linkBuilder = "http"
                    for letter in word:
                        if letter not in endHttpLetters:
                            linkBuilder += letter
                        else:
                            detectedWebsites.append(linkBuilder)
                            break
        fileContents.append("File: '" + fileName + "': " + fileContent)
        if len(detectedWebsites) > 0:
            for website in detectedWebsites:
                websiteText = getInfoFromWebsite(website, True)[1]
                if not checkEmptyString(websiteText):
                    printDebug("Retrieved text from " + website + ": " + websiteText)
                    fileContents.append("Website in file: '" + website + "': " + websiteText)
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


def command_settings():
    printGeneric("\nSettings:")
    printSetting(shouldUseInternet, "Auto Internet Search")
    printSetting(shouldAutomaticallySwitchModels, "Automatically Switch Models")
    printSetting(shouldConsiderHistory, "Consider Chat History")
    
    printGeneric("\nModel:")
    printGeneric(getCurrentModelName())
    
    printGeneric("\nConversation file:")
    printGeneric(strConvoName + ".convo")
    
    printGeneric("\nSystem prompt:")
    printCurrentSystemPrompt(printGeneric)
    
    printGeneric("")
    return


def command_convo():
    printGeneric("\nConversations available:\n")
    convoList = []
    
    for conversation in os.listdir("conversations"):
        if conversation.endswith(".convo"):
            convoName = conversation.replace(".convo", "")
            convoList.append(convoName)
            printGeneric(convoName)
    
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
    printGreen("\nConversation set to: " + convoName + "\n")
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
    printGeneric("")
    return


def command_sd_model():
    global strModelStableDiffusion
    model = printInput("Select model for Stable Diffusion (leave empty for current '" + strModelStableDiffusion + "'): ")
    if len(model) == 0:
        model = strModelStableDiffusion
    strModelStableDiffusion = model
    printSeparator()
    printGreen("\nStable Diffusion model set to: " + model + "\n")
    return


def command_online():
    global shouldUseInternet
    shouldUseInternet = not shouldUseInternet
    if shouldUseInternet:
        printGreen("\nSet to online mode!\n")
    else:
        printRed("\nSet to offline mode!\n")
    return


def command_curl():
    sendCurlCommand()
    return


def command_history():
    global shouldConsiderHistory
    shouldConsiderHistory = not shouldConsiderHistory
    if shouldConsiderHistory:
        printGreen("\nNow using chat history in prompts!\n")
    else:
        printRed("\nNot using chat history in prompts!\n")
    return


def command_switcher():
    global shouldAutomaticallySwitchModels
    shouldAutomaticallySwitchModels = not shouldAutomaticallySwitchModels
    if shouldAutomaticallySwitchModels:
        printGreen("\nNow automatically switching models!\n")
    else:
        printRed("\nNot automatically switching models!\n")
    return


def command_help():
    printGeneric("\nAvailable commands:\n")
    for commandName in commandMap.values():
        if len(commandName) > 0:
            commandAliasStringBuilder = ""
            for commandAlias in commandName:
                if len(commandAliasStringBuilder) > 0:
                    commandAliasStringBuilder += ", " + commandAlias
                else:
                    commandAliasStringBuilder = commandAlias
            printGeneric(" - " + commandAliasStringBuilder)
        else:
            printGeneric(" - " + commandName)
    printGeneric("")
    return


def command_system_prompt():
    global strSystemPrompt
    printGeneric("\nCurrent system prompt:")
    printCurrentSystemPrompt(printGeneric, "\n")
    printSeparator()
    strSystemPrompt = printInput("Enter the new system prompt: ")
    printSeparator()
    printGreen("\nSet system prompt to:")
    printCurrentSystemPrompt(printGreen, "\n")
    return


def command_exit():
    exit()
    return

commandMap = {
    command_help: ["", "/help"],
    command_clear: ["/clear"],
    command_convo: ["/convo"],
    command_curl: ["/curl"],
    command_history: ["/history"],
    command_model: ["/model"],
    command_online: ["/online"],
    command_sd_model: ["/sdmodel"],
    command_settings: ["/settings"],
    command_system_prompt: ["/system", "/systemprompt"],
    command_switcher: ["/switcher"],
    command_exit: ["/exit"]
}


#################################################
############### BEGIN COMPLETIONS ###############
#################################################


def function_action(actions_array):
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
        promptHistory = addToPrompt(promptHistory, "system", strRespondUsingInformation + formatArrayToString(dataIn, " "))
    
    if len(strSystemPrompt) > 0:
        promptHistory = addToPrompt(promptHistory, "system", strSystemPrompt)
    
    promptHistory = addToPrompt(promptHistory, "user", userPromptIn)
    
    printPromptHistory(promptHistory)
    
    completion = createOpenAIChatCompletionRequest(getCurrentModelName(), promptHistory, shouldStream = True)
    
    printResponse("")
    if completion is not None:
        assistantResponse = ""
        pausedLetters = ""
        potentialStopwords = {}
        stop = False
        tic = time.perf_counter()
        toc = time.perf_counter()
        while (toc - tic) < intResponseTimeout:
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
                            break
                    # check current stop words
                    for stopword, index in potentialStopwords.items():
                        if index > 1 or not hasAdded:
                            if index >= len(stopword):
                                stop = True
                                break
                            elif stopword[index] == letter:
                                potentialStopwords[stopword] = index + 1
                                pausedLetters += letter
                                pause = True
                                if index >= len(stopword) - 1:
                                    stop = True
                                    break
                    if not pause and not stop:
                        if len(pausedLetters) > 0:
                            printResponse(pausedLetters, "")
                            assistantResponse += pausedLetters
                            pausedLetters = ""
                        printResponse(letter, "")
                        tic = toc
                        time.sleep(0.015)
                        sys.stdout.flush()
                        assistantResponse += letter
                    elif stop:
                        break # chunk iteration
                        break # while loop
        printResponse("")
        if len(dataIn) > 0 and shouldWriteDataToConvo:
            writeConversation("SYSTEM: " + strRespondUsingInformation + formatArrayToString(dataIn, "\n\n"))
        writeConversation("USER: " + userPromptIn)
        writeConversation("ASSISTANT: " + assistantResponse.replace("ASSISTANT: ", "").replace("SYSTEM: ", ""))
    return


actionEnums = [
    "SEARCH_INTERNET_WITH_SEARCH_TERM",
    #"GENERATE_IMAGE_WITH_DESCRIPTION"
]


strFunctionSystemPrompt = "Determine if it is necessary to perform additional actions in order to complete the USER's request. Create an action plan in the form of an array, if actions are necessary. Otherwise, create an blank array. Available actions are: '" + formatArrayToString(actionEnums, "', '") + "'."


function = [{
    "name": "function_action",
    "parameters": {
        "type": "object",
        "properties": {
            "actions_array": {
                "type": "array",
                "description": "An order-sensitive action plan array that will be completed in order to complete the USER's prompt." +
                    " Actions should only be added when it is necessary to accurately respond to the prompt." +
                    " Available actions are: '" + formatArrayToString(actionEnums, "', '") + "'." +
                    " Each item in the array consists of a single action with its corresponding input data for the action." +
                    " Duplicate actions are permitted only when the input data is different between each action." +
                    " If no additional actions are to be completed, then create an empty array with no items.",
                "items": {
                    "type": "object",
                    "properties": {
                        "action": {
                            "type": "string",
                            "description": "The action to be completed at this step of the action plan." +
" Use 'SEARCH_INTERNET_WITH_SEARCH_TERM' to research a single topic or subject using updated information from the internet.",
#" Use 'GENERATE_IMAGE_WITH_DESCRIPTION' to create an artificial image, only when explicitly requested",
                            "enum": actionEnums,
                        },
                        "action_input_data": {
                            "type": "string",
                            "description": "The input data that corresponds to this specific action." + 
" If the action is 'SEARCH_INTERNET_WITH_SEARCH_TERM', then provide the search terms that will be used to search for updated information on the internet."
#" If the action is 'GENERATE_IMAGE_WITH_DESCRIPTION', then provide a brief detailed description of the image to be created.",
                        }
                    }
                }
            }
        },
        #"required": ["actions_array"]
    }
}]


def getFunctionResponse(promptIn):
    # TODO:
    # APPEND_TO_FILE, READ_FILE, DELETE_FILE, ...
    # for file operations, catch "dangerous" actions (edit system files, etc.)
    
    resetCurrentModel()
    
    hrefs = []
    searchedTerms = []
    datas = []
    promptHistory = []
    
    if shouldConsiderHistory:
        promptHistory = getPromptHistory()
    
    prompt = addToPrompt([], "system", strFunctionSystemPrompt)
    prompt = addToPrompt(prompt, "user", promptIn)
    
    fullPrompt = promptHistory + prompt
    
    printPromptHistory(fullPrompt)
    printDebug("\nDetermining function(s) to do for this prompt...")

    actionsResponse = createOpenAIChatCompletionRequest(
        getCurrentModelName(),
        fullPrompt,
        functionsIn = function,
        functionCallIn = { "name": "function_action" },
    )
    
    if actionsResponse is not None and actionsResponse.get("actions_array") is not None:
        printDebug("\nDetermined actions and input data:")
        
        # print all actions to do
        if len(actionsResponse.get("actions_array")) > 0 and len(actionsResponse.get("actions_array")[0]) > 0:
            for action in actionsResponse.get("actions_array"):
                printDebug(" - '" + action.get("action") +"': " + action.get("action_input_data"))
        else:
            printDebug("(None)")
        
        # do the actions one by one
        for action in actionsResponse.get("actions_array"):
            theAction = action.get("action")
            theActionInputData = action.get("action_input_data")
            match theAction:
                case "SEARCH_INTERNET_WITH_SEARCH_TERM":
                    if not shouldUseInternet:
                        printDebug("\nInternet is disabled - skipping this action. ('" + theAction + "': " + theActionInputData + ")")
                    else:
                        if len(theActionInputData) > 0:
                            theActionInputData = theActionInputData.lower()
                            if not theActionInputData in searchedTerms and not theActionInputData.upper() in actionEnums:
                                searchedTerms.append(theActionInputData)
                                searchResultSources = getSourcesResponse(theActionInputData, intMaxSourcesPerSearch)
                                nonDuplicateHrefs = []
                                for href in searchResultSources:
                                    if href not in hrefs:
                                        nonDuplicateHrefs.append(href)
                                    else:
                                        printDebug("\nSkipped duplicate source: " + key)
                                if len(nonDuplicateHrefs) > 0:
                                    searchResults = getSourcesTextAsync(nonDuplicateHrefs, intMaxSentencesPerSource)
                                    if len(searchResults) > 0:
                                        for key, value in searchResults.items():
                                            hrefs.append(key)
                                            datas.append(value)
                                            printDebug("Appended source data: " + key)
                                    else:
                                        printError("\nNo search results with this search term.")
                                else:
                                    printDebug("\nAll target links are duplicates!")
                                    printDebug("Skipping this search.")
                            else:
                                printError("\nSkipping duplicated search term: " + theActionInputData)
                        else:
                            printError("\nNo search term provided.")
                case "GENERATE_IMAGE_WITH_DESCRIPTION":
                    getImageResponse(theActionInputData)
                case _:
                    printError("\nUnrecognized action: " + action)
                    printError("Breaking out of loop.")
                    break
    else:
        printError("\nNo response - defaulting to chat completion.")
        getChatCompletionResponse(promptIn, shouldWriteDataToConvo = True)
        return
    
    hasHref = len(hrefs) > 0
    
    if not hasHref:
        printInfo("\nThis is an offline response!")
    
    getChatCompletionResponse(promptIn, dataIn = datas, shouldWriteDataToConvo = True)
    
    if hasHref:
        printResponse("\n\n\nSources analyzed:\n")
        for href in hrefs:
            printResponse(href)
    return


def getImageResponse(promptIn):
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
        promptMessage = addToPrompt([], "system", strDetermineBestAssistant + getEnabledModelDescriptions())
        promptMessage = addToPrompt(promptMessage, "user", promptIn)
        
        grammarString = getGrammarString(getEnabledModelNames())
        
        printDump("\nCurrent prompt for model response:")
        printPromptHistory(promptMessage)
        printDump("\nChoices: " + grammarString)
        nextModel = createOpenAIChatCompletionRequest(getCurrentModelName(), promptMessage, grammarIn = grammarString)
        printDebug("\nNext model: " + nextModel)
        return getModelByName(nextModel)


##################################################
################### BEGIN CHAT ###################
##################################################


def handlePrompt(promptIn):
    if checkCommands(promptIn) == False:
        if checkTriggers(promptIn) == False:
            tic = time.perf_counter()
            getFunctionResponse(promptIn)
            toc = time.perf_counter()
            printDebug(f"\n\n{toc - tic:0.3f} seconds")
            printGeneric("")
    return


def checkCommands(promptIn):
    if promptIn.startswith("/"):
        for key, value in commandMap.items():
            for v in value:
                if strPrompt == v:
                    key()
                    return True
        printError("\nUnknown command.\n")
        return True
    else:
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
        if not triggerToCall is None:
            printDebug("\nCalling trigger: " + str(triggerToCall))
            triggerToCall(promptIn)
            return True
    printDebug("\nNo triggers detected.")
    return False


def getPromptHistory():
    conversation = getConversation()
    promptHistory = []
    stringBuilder = ""
    for line in conversation:
        if line.startswith("SYSTEM: ") or line.startswith("USER: ") or line.startswith("ASSISTANT: "):
            if len(stringBuilder) == 0:
                stringBuilder += line
            else:
                s = getRoleAndContentFromString(stringBuilder)
                if s is not None:
                    promptHistory = addToPrompt(promptHistory, s[0].lower(), s[1])
                stringBuilder = line
        else:
            stringBuilder += line
    s = getRoleAndContentFromString(stringBuilder)
    if s is not None:
        promptHistory = addToPrompt(promptHistory, s[0].lower(), s[1])
    return promptHistory


def getRoleAndContentFromString(stringIn):
    if len(stringIn) > 0:
        separator = ": "
        split = stringIn.split(separator)
        if len(split) == 2:
            return split
        else:
            printDebug("The following string is not in a valid role-content form!")
            printDebug(stringIn)
    return None


##################################################
################### BEGIN MAIN ###################
##################################################
command_clear()
command_settings()


while True:
    printSeparator()
    strPrompt = printInput("Enter a prompt ('/help' for list of commands): ")
    printSeparator()
    handlePrompt(strPrompt)

