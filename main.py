import datetime
import json
import openai
import os
import time

from difflib import SequenceMatcher

from modules.file_operations import *
from modules.file_reader import *
from modules.utils import *
from modules.utils_web import *


lastModelUsed = ""
openai.api_key = OPENAI_API_KEY = "sk-xxx"
os.environ["OPENAI_API_KEY"] = "sk-xxx"
stopwords = ["<|im_end|>"]


#################################################
############## BEGIN CONFIGURATION ##############
#################################################


#### CONFIGURATION LOADER ####
fileConfiguration = readFile("", "config.cfg", "\n")
initConfig(fileConfiguration)


####### MODELS LOADER #######
fileModelsConfiguration = json.loads(readFile("", "models.json"))
modelsDescriptions = ""
modelsPrompts = {}
modelsEnabled = {}
for modelObj in fileModelsConfiguration:
    modelsPrompts[modelObj["name"]] = modelObj["prompt"]
    modelsEnabled[modelObj["name"]] = modelObj["isSwitchable"]
    if len(modelObj["description"]) > 0 and modelObj["isSwitchable"]:
        modelsDescriptions += modelObj["description"] + "\n"


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


def errorBlankEmptyText(sourceIn):
    printError("The " + sourceIn + " is empty/blank!")
    return "The text received from the " + sourceIn + " is blank and/or empty. Notify the user about this."


def trigger_youtube(promptIn):
    link = ""
    ytId = ""
    for s in promptIn.split(" "):
        for linkFormat in triggerMap[trigger_youtube]:
            if s.startswith(linkFormat):
                link = s
                ytId = link.replace(linkFormat, "")
                break
    captions = getYouTubeCaptions(ytId)
    getChatCompletionResponse(promptIn.replace(link, ""), [captions], True)
    return


def trigger_browse(promptIn):
    for s in promptIn.split(" "):
        if s.startswith("http"):
            websiteText = getInfoFromWebsite(s, True)
            if checkEmptyString(websiteText):
                websiteText = errorBlankEmptyText("website")
            getChatCompletionResponse(promptIn.replace(s, ""), [websiteText], True)
            break
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
    printGeneric("Available models:")
    for name, prompt in modelsPrompts.items():
        printGeneric(name)
    printSeparator()
    model = printInput("Select a model (leave empty for current '" + strModelDefault + "'): ")
    if len(model) == 0:
        model = strModelDefault
    else:
        matched = False
        for name, prompt in modelsPrompts.items():
            if model in name or model == name:
                model = name
                matched = True
                break
        if not matched:
            printRed("Can't find a match! Using current model " + strModelDefault)
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
    if modelToUse is None:
        modelToUse = strModelDefault
    global lastModelUsed
    if lastModelUsed != modelToUse:
        lastModelUsed = modelToUse
        killLlama()
    if shouldConsiderHistory:
        promptHistory = getPromptHistory()
    else:
        promptHistory = []
    if len(dataIn) > 0:
        promptHistory.append(
            {
                "role": "system",
                "content": modelsPrompts[modelToUse] + """
                
                Use the following information in your response: """ + formatArrayToString(dataIn, "\n\n"),
            }
        )
    else:
        promptHistory.append(
            {
                "role": "system",
                "content": modelsPrompts[modelToUse],
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
            printOpenAIError(e, failedCompletions)
            if failedCompletions < 2:
                failedCompletions += 1
                time.sleep(3)
            else:
                return
    assistantResponse = ""
    potentialStopwords = {}
    stop = False
    pausedLetters = ""
    while not stop:
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
                    time.sleep(0.020)
                    sys.stdout.flush()
                    assistantResponse = assistantResponse + letter
    if len(dataIn) > 0 and shouldWriteDataToConvo:
        writeConversation("""SYSTEM:
        
        Use the following information in your response: """ + formatArrayToString(dataIn, "\n\n"))
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
    actionEnums = [
        "REPLY_TO_CONVERSATION",
        "SEARCH_INTERNET_FOR_ADDITIONAL_INFORMATION",
    ]
    actionEnumsAsString = formatArrayToString(actionEnums, "\n")
    while True:
        if shouldConsiderHistory:
            promptHistory = getPromptHistory()
        else:
            promptHistory = []
        promptHistory.append(
            {
                "role": "system",
                "content": """Your goal is to respond accurately to the current conversation.
                Determine your next action:
                """ + actionEnumsAsString,
            }
        )
        promptHistory.append(
            {
                "role": "user",
                "content": promptIn,
            }
        )
        printDump("Current prompt for function response:")
        for obj in promptHistory:
            printDump(str(obj))
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
                                        "enum": actionEnums,
                                    },
                                    "search_terms": {
                                        "type": "string",
                                        "description": """Determine the question or task that you are completing.
                                        Then determine either a 'search term' or a 'search phrase' for the question.
                                        Use short, specific, and descriptive vocabulary.
                                        Consider the context and topic of the current conversation in your search.
                                        Use a recommended maximum of 5 words.
                                        """,
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
                printOpenAIError(e, failedCompletions)
                if failedCompletions < 2:
                    failedCompletions += 1
                    time.sleep(3)
                else:
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
    dataBuilder = []
    for key, value in dataCollection.items():
        dataBuilder.append("[From " + key + "]" + value)
    if len(dataBuilder) > 0:
        writeConversation("""SYSTEM:
        
        Use the following information in your response: """ + formatArrayToString(dataBuilder, "\n\n"))
    data = []
    for key, value in dataCollection.items():
        data.append(value)
    getChatCompletionResponse(promptIn, data, False)
    if len(hrefs) > 0:
        printResponse("\n\n\nSources analyzed:\n")
        for h in hrefs:
            printResponse(h)
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
            printOpenAIError(e, failedCompletions)
            if failedCompletions < 2:
                failedCompletions += 1
                time.sleep(3)
            else:
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
        for model, enabled in modelsEnabled.items():
            if enabled:
                if len(grammarStringBuilder) > 10:
                    grammarStringBuilder += " | "
                grammarStringBuilder += "\"" + model + "\""
            else:
                printDebug("Skipping model: " + model)
        grammarStringBuilder += ")"
        promptMessage = []
        promptMessage.append(
            {
                "role": "system",
                "content": "Which assistant has the most relevant skills related to the task given by USER?" + """
                Consider the following descriptions of each model:
                """ + modelsDescriptions
            }
        )
        promptMessage.append(
            {
                "role": "user",
                "content": promptIn
            }
        )
        printDump("Current prompt for model response:")
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
                printOpenAIError(e, failedCompletions)
                if failedCompletions < 2:
                    failedCompletions += 1
                    time.sleep(3)
                else:
                    return
        model = completion.choices[0].message.content
        for modelName, prompt in modelsPrompts.items():
            if model in modelName or model == modelName:
                printDebug("Determined model: " + modelName)
                return modelName
        return


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
    potentialTriggers = {}
    for key, value in triggerMap.items():
        for v in value:
            if v in promptIn:
                matchPercentage = SequenceMatcher(None, v, promptIn).ratio() * 100
                potentialTriggers[key] = matchPercentage
    if len(potentialTriggers) == 1:
        for key, value in potentialTriggers.items():
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
            printDebug("Calling trigger: " + str(triggerToCall))
            triggerToCall(promptIn)
            return True
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

