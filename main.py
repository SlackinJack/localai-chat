import datetime
import json
import openai
import os
import re
import requests
import time
import urllib


from difflib import SequenceMatcher


from modules.file_operations import *
from modules.file_reader import *
from modules.utils import *
from modules.utils_command import *
from modules.utils_web import *


# TODO:
# - clean code
# - fix target links being smashed together
# - fix location and time in prompts
# - add more (comprehensive) tests
# - test file ops
# - organize commands
# - add up-down arrow key support
# - config reload command
# - image seeds, retries
# - support newer localAI and features


#################################################
############## BEGIN CONFIGURATION ##############
#################################################


#### STATIC CONFIGURATION ####
stopwords = ["|im_end|>", "\n\n\n\n\n", "</s>"]
openai.api_key = OPENAI_API_KEY = os.environ["OPENAI_API_KEY"] = "sk-xxx"
strRespondUsingInformation = "Provide a response that is restricted to the information contained in the following data: "
strDetermineBestAssistant = "Use the following descriptions of each assistant to determine which assistant has the most relevant skills related to the task given by USER: "


####### MODELS LOADER #######
fileModelsConfiguration = json.loads(readFile("", "models.json"))


def getModelByName(modelNameIn, textModel = True):
    for model, modelMetadata in fileModelsConfiguration.items():
        if (modelNameIn in model or modelNameIn == model) and modelMetadata["text_model"] == textModel:
            return model
    return None


def resetCurrentModel():
    global currentModel
    currentModel = getModelByName(configModel["default_model"], True)
    return


def getModels(textModels = True):
    out = {}
    for model, modelMetadata in fileModelsConfiguration.items():
        if modelMetadata["text_model"] == textModels:
            out[model] = modelMetadata
    return out


def getEnabledModelNames():
    out = []
    for model, modelMetadata in getModels(True):
        if modelMetadata["switchable"]:
            out.append(model)
    return out


def getEnabledModelDescriptions():
    out = ""
    for model, modelMetadata in getModels(True):
        if modelMetadata["switchable"]:
            if len(out) > 0:
                out += " "
            out += modelMetadata["description"]
    return out


def printCurrentSystemPrompt(printer, space = ""):
    if len(strSystemPrompt) > 0:
        printer(strSystemPrompt + space)
    else:
        printer("(Empty)" + space)
    return


#### CONFIGURATION LOADER ####
fileConfiguration = json.loads(readFile("", "config.json"))


configMain = fileConfiguration["main_configuration"]
configModel = fileConfiguration["model_configuration"]
configBehaviour = fileConfiguration["behavioural_configuration"]


# main configs
if not configMain["address"].endswith("/v1"):
    newAddress = configMain["address"]
    if not newAddress.endswith("/"):
        newAddress += "/"
    openai.api_base = newAddress + "v1"


intResponseTimeout              = configMain["response_timeout_seconds"]
shouldDeleteOutputFilesOnExit   = configMain["delete_output_files_on_exit"]
shouldAutomaticallyOpenFiles    = configMain["automatically_open_files"]


# model configs
currentModel                    = getModelByName(configModel["default_model"], True)
strSystemPrompt                 = configModel["system_prompt"]
currentImageModel               = configModel["default_image_model"]
strImageSize                    = configModel["image_size"]
lstIgnoredModelNames            = configModel["model_scanner_ignored_filenames"]


if currentModel is None:
    printRed("\nYour default model is missing from models.json! Please fix your configuration.")
    exit()


# behavioural configs
shouldUseFunctions              = configBehaviour["enable_functions"]
shouldUseInternet               = configBehaviour["enable_internet"]
shouldAutomaticallySwitchModels = configBehaviour["enable_automatic_model_switching"]
shouldConsiderHistory           = configBehaviour["enable_chat_history_consideration"]
intMaxSourcesPerSearch          = configBehaviour["max_sources_per_search"]
intMaxSentencesPerSource        = configBehaviour["max_sentences_per_source"]


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


def checkForYoutube(linkIn):
    for youtubeFormat in triggerMap[trigger_youtube]:
        if linkIn.startswith(youtubeFormat):
            return getYouTubeCaptions(linkIn.replace(youtubeFormat, ""))
    return None


def trigger_youtube(promptIn):
    promptWithoutWebsites = promptIn
    youtubeTranscripts = []
    videoCounter = 1
    for s in promptIn.split(" "):
        youtubeResult = checkForYoutube(s)
        if youtubeResult is not None:
            promptWithoutWebsites = promptWithoutWebsites.replace(s, "")
            youtubeTranscripts.append("Video " + str(videoCounter) + ": " + youtubeResult)
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
            youtubeResult = checkForYoutube(s)
            websiteType = "Website"
            if youtubeResult is not None:
                websiteText = youtubeResult
                websiteType = "Video"
            else:
                websiteText = getInfoFromWebsite(s, True)[1]
                if checkEmptyString(websiteText):
                    websiteText = errorBlankEmptyText("website")
            websiteTexts.append(websiteType + " " + str(websiteCounter) + ": " + websiteText)
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
            if not shouldUseInternet:
                printDebug("\nInternet is disabled - skipping embedded website check.\n")
            else:
                # check for websites in file
                words = re.split(' |\n|\r|\)|\]|\}|\>', fileContent)
                for word in words:
                    if word.startswith("http://") or word.startswith("https://"):
                        detectedWebsites.append(word)
                        printDebug("Found website in file: " + word)
        fileContents.append("File: '" + fileName + "': " + fileContent)
        if len(detectedWebsites) > 0:
            for website in detectedWebsites:
                youtubeResult = checkForYoutube(website)
                websiteType = "Website"
                if youtubeResult is not None:
                    websiteText = youtubeResult
                    websiteType = "Video"
                else: 
                    websiteText = getInfoFromWebsite(website, True)[1]
                    if not checkEmptyString(websiteText):
                        printDebug("Retrieved text from " + website + ": " + websiteText)
                fileContents.append(websiteType + " in file: '" + website + "': " + websiteText)
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
    printSetting(shouldUseFunctions, "Functions")
    printSetting(shouldUseInternet, "Auto Internet Search")
    printSetting(shouldAutomaticallySwitchModels, "Automatically Switch Models")
    printSetting(shouldConsiderHistory, "Consider Chat History")
    
    printGeneric("\nModel:")
    printGeneric(currentModel)
    
    printGeneric("\nImage model:")
    printGeneric(currentImageModel)
    
    printGeneric("\nConversation file:")
    printGeneric(strConvoName + ".convo")
    
    printGeneric("\nSystem prompt:")
    printCurrentSystemPrompt(printGeneric)
    
    printGeneric("")
    return


def command_image():
    imageDesc = printInput("Enter image description: ")
    printSeparator()
    if not checkEmptyString(imageDesc):
        while True:
            tic = time.perf_counter()
            printResponse("\n" + getImageResponse(imageDesc) + "\n")
            toc = time.perf_counter()
            printDebug(f"\n\n{toc - tic:0.3f} seconds")
            if not printYNQuestion("Do you want to regenerate the image with the same prompt?"):
                break
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
    for model in getModels(True):
        printGeneric(model)
    printGeneric("")
    printSeparator()
    nextModel = printInput("Select a model (leave empty for current '" + currentModel + "'): ")
    printSeparator()
    nextModelObj = None
    if len(nextModel) == 0:
        printRed("\nKeeping current model: " + currentModel)
    else:
        nextModelObj = getModelByName(nextModel, True)
        if nextModelObj is None:
            printRed("\nCan't find a match - keeping current model: " + currentModel)
        else:
            currentModel = nextModelObj
            printGreen("\nChat model set to: " + currentModel)
    printGeneric("")
    return


def command_image_model():
    global currentImageModel
    printGeneric("\nAvailable image models:\n")
    for model in getModels(False):
        printGeneric(model)
    printGeneric("")
    printSeparator()
    nextModel = printInput("Select a model for image generation (leave empty for current '" + currentImageModel + "'): ")
    printSeparator()
    nextModelObj = None
    if len(nextModel) == 0:
        printRed("\nKeeping current model: " + currentImageModel)
    else:
        nextModelObj = getModelByName(nextModel, False)
        if nextModelObj is None:
            printRed("\nCan't find a match - keeping current model: " + currentImageModel)
        else:
            currentImageModel = nextModelObj
            printGreen("\nImage model set to: " + currentImageModel)
    printGeneric("")
    return


def command_modelscanner():
    modelList = getModelList()
    if modelList is not None:
        global fileModelsConfiguration
        
        addModels = {}
        for model in modelList:
            if not model["id"] in lstIgnoredModelNames and not model["id"] in fileModelsConfiguration.keys():
                # add the model
                printDebug(model["id"] + " is missing from model config")
                addModels[model["id"]] = {"text_model": False, "switchable": False, "description": ""}
        
        printDebug("")

        newModelsJson = fileModelsConfiguration | addModels
        outputFileString = json.dumps(newModelsJson, indent=4)
        
        printDump("\nNew models.json:\n\n" + outputFileString + "\n")
        
        deleteFile("", "models.json")
        appendFile("", "models.json", outputFileString)
        
        fileModelsConfiguration = json.loads(readFile("", "models.json"))
        
        printGeneric("\nSuccessfully updated your models.json!\n")
    else:
        printGeneric("\nCould not update your models.json. (Check your connection?)\n")
    return


def command_functions():
    global shouldUseFunctions
    shouldUseFunctions = not shouldUseFunctions
    if shouldUseFunctions:
        printGreen("\nNow using functions for prompts!\n")
    else:
        printRed("\nNot using functions for prompts!\n")
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


def command_selftest():
    if printYNQuestion("The program will self-test. Do you want to continue?"):
        passes = 0
        target = 7
        
        printGeneric("\nTesting chat completion...\n")
        getChatCompletionResponse("Hi there, how are you?", ["Respond to USER in a respectful manner."], True)
        printGreen("\nChat completion test passed!\n")
        passes += 1
        
        printGeneric("\nTesting model switcher...\n")
        global shouldAutomaticallySwitchModels
        currentModelSwitcherSetting = shouldAutomaticallySwitchModels
        shouldAutomaticallySwitchModels = True
        getModelResponse("Write a simple python function that prints 'Hello, World!'")
        shouldAutomaticallySwitchModels = currentModelSwitcherSetting
        printGreen("\nModel switcher test passed!\n")
        passes += 1
        
        printGeneric("\nTesting functions...\n")
        getFunctionResponse("Search the internet for information on Big Ben.")
        printGreen("\nFunctions test passed!\n")
        passes += 1
        
        printGeneric("\nTesting input file...\n")
        trigger_openFile("What is in this file 'tests/sample'")
        printGreen("\nInput file test passed!\n")
        passes += 1
        
        printGeneric("\nTesting internet browse...\n")
        trigger_browse("Summarize this webpage https://example.com/")
        printGreen("\nInternet browse test passed!\n")
        passes += 1
        
        printGeneric("\nTesting YouTube...\n")
        trigger_youtube("Summarize this YouTube video https://www.youtube.com/watch?v=TVLYtiunWJA")
        printGreen("\nYouTube test passed!\n")
        passes += 1
        
        printGeneric("\nTesting image generation...\n")
        getImageResponse("A red box")
        printGreen("\nImage generation test passed!\n")
        passed += 1
        
        if passes == target:
            printGreen("\nAll tests passed!\n")
        else:
            printRed("\nSome tests failed - read log for details.\n")
    return


def command_exit():
    for conversation in os.listdir("conversations"):
        if conversation.endswith(".convo"):
            if checkEmptyString(readFile("conversations/", conversation)):
                deleteFile("conversations/", conversation)
                printDebug("\nDeleted empty conversation file: " + conversation + "\n")
    
    if shouldDeleteOutputFilesOnExit:
        for outputFile in os.listdir("output"):
            if not outputFile == ".keep":
                deleteFile("output/", outputFile)
                printDebug("\nDeleted output file: " + outputFile + "\n")
    exit()
    return


commandMap = {
    command_help:               ["", "/help"],
    command_clear:              ["/clear"],
    command_convo:              ["/convo"],
    command_curl:               ["/curl"],
    command_functions:          ["/functions"],
    command_history:            ["/history"],
    command_image:              ["/image"],
    command_model:              ["/model"],
    command_modelscanner:       ["/modelscanner"],
    command_online:             ["/online"],
    command_image_model:           ["/imagemodel"],
    command_selftest:           ["/selftest"],
    command_settings:           ["/settings"],
    command_switcher:           ["/switcher"],
    command_system_prompt:      ["/system", "/systemprompt"],
    command_exit:               ["/exit"]
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
    
    completion = createOpenAIChatCompletionRequest(currentModel, promptHistory, shouldStream = True)
    
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
        if len(dataIn) > 0 and shouldWriteDataToConvo:
            writeConversation("SYSTEM: " + strRespondUsingInformation + formatArrayToString(dataIn, "\n\n"))
        writeConversation("USER: " + userPromptIn)
        writeConversation("ASSISTANT: " + assistantResponse.replace("ASSISTANT: ", "").replace("SYSTEM: ", ""))
        printResponse("\n")
    return


actionEnums = [
    "SEARCH_INTERNET_WITH_SEARCH_TERM",
    "GENERATE_IMAGE_WITH_DESCRIPTION",
    "GET_UPDATED_LOCATION_DATA",
    "GET_UPDATED_TIME_AND_DATE_DATA",
    "WRITE_FILE_TO_FILESYSTEM"
]


strFunctionSystemPrompt = """Determine if it is necessary to perform additional actions in order to fulfill the tasks given by, and/or to provide an accurate response to, the USER's requests.
Create an action plan in the form of an array, if actions are necessary.
Otherwise, create an blank array.
Available actions are: '""" + formatArrayToString(actionEnums, "', '") + """'.
You will get updated location, time and date data when it is applicable to the USER's inquiry."""


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
                    " Use placeholders in input data when the input data should be generated by preceding steps." + 
                    " Duplicate actions are permitted only when the input data is different between each action." +
                    " If no additional actions are to be completed, then create an empty array with no items.",
                "items": {
                    "type": "object",
                    "properties": {
                        "action": {
                            "type": "string",
                            "description": "The action to be completed at this step of the action plan." +
" Use 'GET_UPDATED_LOCATION_DATA' to get our current location, and should also be used when USER is prompting on local information." +
" Use 'GET_UPDATED_TIME_AND_DATE_DATA' to get our current date and time, and should also be used when USER is prompting on updated information." +
" Use 'SEARCH_INTERNET_WITH_SEARCH_TERM' to research a single topic or subject using updated information from the internet." +
" Use 'GENERATE_IMAGE_WITH_DESCRIPTION' to create an artificial image, only when explicitly requested." +
" Use 'WRITE_FILE_TO_FILESYSTEM' to create a new file on the filesystem.",
                            "enum": actionEnums,
                        },
                        "action_input_data": {
                            "type": "string",
                            "description": "The input data that corresponds to this specific action." +
" If the action is 'SEARCH_INTERNET_WITH_SEARCH_TERM', then provide the search terms that will be used to search for information on the internet." +
" If the action is 'GENERATE_IMAGE_WITH_DESCRIPTION', then provide a brief detailed description of the image to be created." +
" If the action is 'WRITE_FILE_TO_FILESYSTEM', then provide the name for the file, a colon and a space, and then the contents of the file inside of curly braces.",
                        }
                    }
                }
            }
        }
    }
}]


def getFunctionResponse(promptIn):
    if shouldAutomaticallySwitchModels:
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
        currentModel,
        fullPrompt,
        functionsIn = function,
        functionCallIn = { "name": "function_action" },
    )
    
    if actionsResponse is not None and actionsResponse.get("actions_array") is not None:
        printDebug("\nDetermined actions and input data:")
        
        # print all actions to do
        if len(actionsResponse.get("actions_array")) > 0 and len(actionsResponse.get("actions_array")[0]) > 0:
            for action in actionsResponse.get("actions_array"):
                printDebug(" - " + action.get("action") +": " + action.get("action_input_data"))
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
                    printGeneric("\nThe model wants to create an image with the following description: " + theActionInputData + "\n")
                    if printYNQuestion("Do you want to allow this action?"):
                        printResponse(getImageResponse(theActionInputData))
                
                
                case "GET_UPDATED_LOCATION_DATA":
                    if not shouldUseInternet:
                        printDebug("\nInternet is disabled - skipping this action. ('" + theAction + "': " + theActionInputData + ")")
                    else:
                        ipRequest = requests.get('https://api64.ipify.org?format=json').json()
                        printDump("\nIP result: " + str(ipRequest))
                        ip = ipRequest["ip"]
                        loc = requests.get(f'https://ipapi.co/{ip}/json/').json()
                        if loc.get("error") is None:
                            printDump("\nLocation result: " + str(loc))
                            fullAddr = loc.get("city") + ", " + loc.get("region") + ", " + loc.get("country_name")
                            for a in actionsResponse.get("actions_array"):
                                d = a.get("action_input_data").replace("{location}", fullAddr)
                            datas.append("Current location is: " + fullAddr)
                            printDebug("\nLocation placeholders updated.")
                        else:
                            errorReason = loc.get("reason")
                            printError("\nError while getting location: " + errorReason)
                            printError("Skipping fetching location - response may not be accurate!")
                
                
                case "GET_UPDATED_TIME_AND_DATE_DATA":
                    now = str(datetime.datetime.now())
                    printDump("\nTime: " + now)
                    for a in actionsResponse.get("actions_array"):
                        d = a.get("action_input_data").replace("{time_and_date}", now)
                    datas.append("The current time is: " + now)
                    printDebug("\nTime placeholders updated.")
                
                
                case "WRITE_FILE_TO_FILESYSTEM":
                    fileName = theActionInputData.split(": ")[0]
                    fileContents = theActionInputData.replace(fileName + ": ", "")
                    printGeneric("\nThe model wants to write the following file: " + fileName + ", with the following contents:\n")
                    printGreen(fileContents + "\n")
                    if printYNQuestion("Do you want to allow this action?"):
                        appendFile("output/", fileName, fileContents + "\n")
                        printGreen("\nFile has been written.")
                    else:
                        printRed("\nWill not write file, continuing...")
                
                
                case _:
                    printError("\nUnrecognized action: " + action)
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
    theURL = createOpenAIImageRequest(currentImageModel, promptIn, strImageSize)
    if theURL is not None:
        split = theURL.split("/")
        filename = split[len(split) - 1]
        filename = "output/" + filename
        urllib.request.urlretrieve(theURL, filename)
        if shouldAutomaticallyOpenFiles:
            openLocalFile(filename)
        # TODO: file management
        return "Your image is available at: " + filename
    else:
        printError("\nImage creation failed!\n")
        return ""


def getModelResponse(promptIn):
    if not shouldAutomaticallySwitchModels:
        return currentModel
    else:
        resetCurrentModel()
        
        promptMessage = addToPrompt([], "system", strDetermineBestAssistant + getEnabledModelDescriptions())
        promptMessage = addToPrompt(promptMessage, "user", promptIn)
        
        grammarString = getGrammarString(getEnabledModelNames())
        
        printDump("\nCurrent prompt for model response:")
        printPromptHistory(promptMessage)
        printDump("\nChoices: " + grammarString)
        nextModel = createOpenAIChatCompletionRequest(currentModel, promptMessage, grammarIn = grammarString)
        printDebug("\nNext model: " + nextModel)
        return getModelByName(nextModel)


##################################################
################### BEGIN CHAT ###################
##################################################


def handlePrompt(promptIn):
    if checkCommands(promptIn) == False:
        if checkTriggers(promptIn) == False:
            tic = time.perf_counter()
            if shouldUseFunctions:
                getFunctionResponse(promptIn)
            else:
                printDebug("Functions are disabled - using chat completion only")
                getChatCompletionResponse(promptIn)
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


##################################################
################### BEGIN MAIN ###################
##################################################
command_clear()
command_settings()


while True:
    printSeparator()
    strPrompt = printInput("Enter a prompt ('/help' for list of commands): ")
    printSeparator()
    if not checkEmptyString(strPrompt):
        handlePrompt(strPrompt)
    else:
        command_help()

