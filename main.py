import datetime
import json
import openai
import os
import random
import re
import requests
import time
import urllib


from difflib import SequenceMatcher
from threading import Thread
from pynput import keyboard


from modules.file_operations import *
from modules.file_reader import *
from modules.utils import *
from modules.utils_command import *
from modules.utils_web import *


# TODO:
# - clean code, start dividing main into modules
# - fix target links being smashed together
# - add tests for
#   - video / speech recognition
#   - pdf
#   - pptx
#   - docx
# - test write file operation in functions
# - save config
# - support newer localAI and features (after successful compile)
# - /exit and exit confirmation in main menu


#################################################
############## BEGIN CONFIGURATION ##############
#################################################


stopwords = ["|im_end|>", "\n\n\n\n\n", "</s>"]
openai.api_key = OPENAI_API_KEY = os.environ["OPENAI_API_KEY"] = "sk-xxx"
strRespondUsingInformation = "Provide a response that is restricted to the information contained in the following data: "
strDetermineBestAssistant = "Use the following descriptions of each assistant to determine which assistant has the most relevant skills related to the task given by USER: "


######## GLOBAL VARS ########


configs = {}
modelConfigs = {}
defaultModelName = ""
strConvoTimestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
strConvoName = strConvoTimestamp
shouldGenerateNextImage = False
imageThreadsGPU = {}
imageThreadsCPU = {}


####### MODELS CONFIG #######


def loadModelConfiguration():
    global modelConfigs
    modelConfigs = json.loads(readFile("", "models.json"))
    return


def getModelByName(modelNameIn, textModel = True):
    for model, modelMetadata in modelConfigs.items():
        if (modelNameIn in model or modelNameIn == model) and modelMetadata["text_model"] == textModel:
            return model
    return None


def resetCurrentModel():
    configs["default_model"] = getModelByName(defaultModelName, True)
    return


def getModels(textModels = True):
    out = {}
    for model, modelMetadata in modelConfigs.items():
        if modelMetadata["text_model"] == textModels:
            out[model] = modelMetadata
    return out


def getEnabledModelNames():
    out = []
    for model, modelMetadata in getModels(True).items():
        if modelMetadata["switchable"]:
            out.append(model)
    return out


def getEnabledModelDescriptions():
    out = ""
    for model, modelMetadata in getModels(True).items():
        if modelMetadata["switchable"]:
            if len(out) > 0:
                out += " "
            out += modelMetadata["description"]
    return out


def printCurrentSystemPrompt(printer, space = ""):
    if len(configs["system_prompt"]) > 0:
        printer(configs["system_prompt"] + space)
    else:
        printer("(Empty)" + space)
    return


######## MAIN CONFIG ########


def loadConfiguration():
    fileConfiguration = json.loads(readFile("", "config.json"))
    
    configMain      = fileConfiguration["main_configuration"]
    configModel     = fileConfiguration["model_configuration"]
    configBehaviour = fileConfiguration["behavioural_configuration"]
    
    ############### main configs ###############
    
    
    if not configMain["address"].endswith("/v1"):
        newAddress = configMain["address"]
        if not newAddress.endswith("/"):
            newAddress += "/"
        openai.api_base = newAddress + "v1"
    
    configs["parallel_requests_gpu_max"]        = configMain["parallel_requests_gpu_max"]
    configs["parallel_requests_cpu_max"]        = configMain["parallel_requests_cpu_max"]
    configs["response_timeout_seconds"]         = configMain["response_timeout_seconds"]
    configs["delete_output_files_on_exit"]      = configMain["delete_output_files_on_exit"]
    configs["automatically_open_files"]         = configMain["automatically_open_files"]
    
    
    global imageThreadsGPU
    imageThreadsGPU = {}
    g = 1
    while g <= configs["parallel_requests_gpu_max"]:
        imageThreadsGPU[g] = False
        g += 1


    global imageThreadsCPU
    imageThreadsCPU = {}
    c = 1
    while c <= configs["parallel_requests_cpu_max"]:
        imageThreadsCPU[c] = False
        c += 1
    
    
    ############### model configs ###############
    
    
    configs["default_model"]                    = getModelByName(configModel["default_model"], True)
    configs["system_prompt"]                    = configModel["system_prompt"]
    configs["default_image_model"]              = configModel["default_image_model"]
    configs["image_size"]                       = configModel["image_size"]
    configs["image_step"]                       = configModel["image_step"]
    configs["model_scanner_ignored_filenames"]  = configModel["model_scanner_ignored_filenames"]
    
    
    if configs["default_model"] is None:
        printError("\nYour default model is missing from models.json! Please fix your configuration.")
        command_exit()
    
    
    global defaultModelName
    defaultModelName = configModel["default_model"]
    
    
    ############ behavioural configs ###########
    
    
    configs["enable_functions"]                     = configBehaviour["enable_functions"]
    configs["enable_internet"]                      = configBehaviour["enable_internet"]
    configs["enable_automatic_model_switching"]     = configBehaviour["enable_automatic_model_switching"]
    configs["enable_chat_history_consideration"]    = configBehaviour["enable_chat_history_consideration"]
    configs["max_sources_per_search"]               = configBehaviour["max_sources_per_search"]
    configs["max_sentences_per_source"]             = configBehaviour["max_sentences_per_source"]
    
    return


#################################################
############## BEGIN CONVERSATIONS ##############
#################################################


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
            if not configs["enable_internet"]:
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


################ General Commands ################


def command_help():
    printGeneric("\nAvailable commands:")
    currentCategory = ""
    for commandMetadata in commandMap.values():
        commandName = commandMetadata[0]
        commandCategory = commandMetadata[1]
        commandDescription = commandMetadata[2]
        if len(currentCategory) == 0:
            currentCategory = commandCategory
            printGeneric("\n-------------------- " + currentCategory + " --------------------\n")
        else:
            if not currentCategory == commandCategory:
                currentCategory = commandCategory
                printGeneric("\n-------------------- " + currentCategory + " --------------------\n")
        printGeneric(" - " + commandName + " > " + commandDescription)
    printGeneric("")
    return


def command_config():
    loadModelConfiguration()
    loadConfiguration()
    printGeneric("\nConfiguration reloaded.\n")
    return


def command_config_model():
    loadModelConfiguration()
    printGeneric("\nModel configuration reloaded.\n")
    return


def command_settings():
    printGeneric("\nSettings:")
    printSetting(configs["enable_functions"], "Functions")
    printSetting(configs["enable_internet"], "Auto Internet Search")
    printSetting(configs["enable_automatic_model_switching"], "Automatically Switch Models")
    printSetting(configs["enable_chat_history_consideration"], "Consider Chat History")
    
    printGeneric("\nModel: " + configs["default_model"])
    printGeneric("Image model: " + configs["default_image_model"])
    
    printGeneric("\nConversation file: " + strConvoName + ".convo")
    
    printGeneric("\nSystem prompt:")
    printCurrentSystemPrompt(printGeneric)
    
    printGeneric("")
    return


def command_exit():
    for conversation in os.listdir("conversations"):
        if conversation.endswith(".convo"):
            if checkEmptyString(readFile("conversations/", conversation)):
                deleteFile("conversations/", conversation)
                printDebug("\nDeleted empty conversation file: " + conversation + "\n")
    
    if configs["delete_output_files_on_exit"]:
        for outputFile in os.listdir("output"):
            if not outputFile == ".keep":
                deleteFile("output/", outputFile)
                printDebug("\nDeleted output file: " + outputFile + "\n")
    
    keyboardListener.stop()
    
    exit()
    return


################ Settings Commands ################


def command_convo():
    presetName = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    printGeneric("\nConversations available:\n")
    convoList = []
    
    for conversation in os.listdir("conversations"):
        if conversation.endswith(".convo"):
            convoName = conversation.replace(".convo", "")
            convoList.append(convoName)
            printGeneric(convoName)
    
    printGeneric("")
    
    def convo_verifier(convoNameIn):
        if len(convoNameIn) > 0:
            for conversation in convoList:
                if convoNameIn in conversation:
                    return[conversation, True]
        return [presetName, True]
    
    setConversation(
        setOrPresetValueWithResult(
            "Select a conversation to use or create a new one by using an unique name",
            presetName,
            convo_verifier,
            "auto-generated",
            "Using generated name",
            "Conversation set to",
            ""
        )
    )
    return


def command_system_prompt():
    printGeneric("\nCurrent system prompt:")
    printCurrentSystemPrompt(printGeneric, "\n")
    printSeparator()
    configs["system_prompt"] = printInput("Enter the new system prompt: ")
    printSeparator()
    printGreen("\nSet system prompt to:")
    printCurrentSystemPrompt(printGreen, "\n")
    return


def command_model():
    submenus = ["chat", "image", "exit"]
    while True:
        printGeneric("\nModel menu:\n")
        for submenu in submenus:
            printGeneric(" - " + submenu)
        printGeneric("")
        printSeparator()
        selection = printInput("Select item: ")
        printSeparator()
        
        match selection:
            case "chat":
                submenu_model_chat()
            case "image":
                submenu_model_image()
            case "exit":
                printGeneric("\nReturning to main menu.\n")
                break
            case _:
                printError("\nInvalid selection.\n")
        printSeparator()
    return


### Begin model submenus ###


def submenu_model_chat():
    def model_verifier(nextModelIn):
        result = getModelByName(nextModelIn, True)
        return [result, result is not None]
    
    printGeneric("\nAvailable models:\n")
    for model in getModels(True):
        printGeneric(model)
    printGeneric("")
    
    configs["default_model"] = setOrDefault(
        "Select a model",
        configs["default_model"],
        model_verifier,
        "Keeping current model",
        "Chat model set to",
        "Cannot find a match - keeping current chat model"
    )
    return


def submenu_model_image():
    def image_model_verifier(nextModelIn):
        result = getModelByName(nextModelIn, False)
        return [result, result is not None]
    
    printGeneric("\nAvailable image models:\n")
    for model in getModels(False):
        printGeneric(model)

    printGeneric("\n(Note: If you are using parallel requests with the CPU,")
    printGeneric("the CPU model should be named '[modelname]-cpu' on the server,")
    printGeneric("with your CPU-specific tuning and configuration settings.)")
    
    configs["default_image_model"] = setOrDefault(
        "Select a model for image generation",
        configs["default_image_model"],
        image_model_verifier,
        "Keeping current image model",
        "Image model set to",
        "Cannot find a match - keeping current image model"
    )
    return


### End model submenus ###



################# Toggle Commands #################


def command_functions():
    configs["enable_functions"] = toggleSetting(
        configs["enable_functions"],
        "Functions is now disabled for prompts.",
        "Functions is now enabled for prompts."
    )
    return


def command_online():
    configs["enable_internet"] = toggleSetting(
        configs["enable_internet"],
        "Internet is now disabled for functions.",
        "Internet is now enabled for functions."
    )
    return


def command_history():
    configs["enable_chat_history_consideration"] = toggleSetting(
        configs["enable_chat_history_consideration"],
        "Chat history will not be used in prompts.",
        "Chat history will now be used in prompts."
    )
    return


def command_switcher():
    configs["enable_automatic_model_switching"] = toggleSetting(
        configs["enable_automatic_model_switching"],
        "Response model will not be switched.",
        "Response model will now be automatically chosen."
    )
    return


################## Tools Commands ##################


def command_curl():
    sendCurlCommand()
    return


def command_image():
    submenus = ["single", "endless", "settings", "exit"]
    while True:
        printGeneric("\nImage menu:\n")
        for submenu in submenus:
            printGeneric(" - " + submenu)
        printGeneric("")
        printSeparator()
        selection = printInput("Select item: ")
        printSeparator()
        
        match selection:
            case "single":
                submenu_image_single()
            case "endless":
                submenu_image_endless()
            case "settings":
                while True:
                    settings_submenus = ["size", "step", "exit"]
                    printGeneric("\nImage Settings:")
                    printGeneric("Dimensions: " + configs["image_size"])
                    printGeneric("Step: " + str(configs["image_step"]))
                    printGeneric("\nImage settings menu:\n")
                    for setting_submenu in settings_submenus:
                        printGeneric(" - " + setting_submenu)
                    printGeneric("")
                    printSeparator()
                    settings_selection = printInput("Select item: ")
                    printSeparator()
                    
                    match settings_selection:
                        case "size":
                            submenu_image_settings_size()
                        case "step":
                            submenu_image_settings_step()
                        case "exit":
                            printGeneric("\nReturning to image menu.\n")
                            break
                        case _:
                            printError("\nInvalid selection.\n")
                    printSeparator()
            case "exit":
                printGeneric("\nReturning to main menu.\n")
                break
            case _:
                printError("\nInvalid selection.\n")
        printSeparator()
    return


### Begin image submenus ###

def submenu_image_single():
    imageDesc = printInput("Enter image description: ")
    if not checkEmptyString(imageDesc):
        
        seed = setOrPresetValue(
            "Enter an image seed (eg. 1234567890)",
            None,
            intVerifier,
            "random",
            "Using a random seed",
            "The seed you entered is invalid - using a random seed!"
        )
        
        printSeparator()
        
        while True:
            tic = time.perf_counter()
            printResponse("\n" + getImageResponse(imageDesc, seed) + "\n")
            toc = time.perf_counter()
            printDebug(f"\n\n{toc - tic:0.3f} seconds")
            if not printYNQuestion("Do you want to regenerate the image with the same prompt and seed?"):
                printGeneric("\nReturning to menu.\n")
                break
    else:
        printSeparator()
        printError("\nImage prompt was empty - returning to image menu.\n")
    return


def submenu_image_endless():
    imageDesc = printInput("Enter image description (endless mode): ")
    printSeparator()
    if not checkEmptyString(imageDesc):
        positivePrompt = ""
        negativePrompt = ""
        prompts = imageDesc.split(" | ")
        if len(prompts) == 2:
            positivePrompt = prompts[0]
            negativePrompt = prompts[1]
        elif len(prompts) == 1:
            positivePrompt = imageDesc
        else:
            printError("\nThe prompt is malformed.")
            printError("You must enter a prompt in the form of:")
            printError("'positive prompt | negative prompt'")
            return
        
        actualRunningThreadsGPU = {}
        actualRunningThreadsCPU = {}
        
        def imageWorkerGPU(threadNumberIn):
            tic = time.perf_counter()
            printDebug("\n[GPU" + str(threadNumberIn) + "]: Worker started.")
            printResponse(
                "\n[GPU" + str(threadNumberIn) + "]: Image created: " +
                getImageResponse(
                    imageDesc,
                    silent=True,
                    threadNumber=threadNumberIn
                ) + "\n"
            )
            
            actualRunningThreadsGPU[threadNumberIn] = False
            toc = time.perf_counter()
            printDebug(f"{toc - tic:0.3f} seconds\n")
            printSeparator()
        
        def imageWorkerCPU(threadNumberIn):
            tic = time.perf_counter()
            printDebug("\n[CPU" + str(threadNumberIn) + "]: Worker started.")
            printResponse(
                "\n[CPU" + str(threadNumberIn) + "]: Image created: " +
                getImageResponse(
                    imageDesc,
                    silent=True,
                    isCPU=True,
                    threadNumber=threadNumberIn
                ) + "\n"
            )
            
            actualRunningThreadsCPU[threadNumberIn] = False
            toc = time.perf_counter()
            printDebug(f"{toc - tic:0.3f} seconds\n")
            printSeparator()
        
                
        printGeneric("\n(Press [F12] to stop image generation.)\n")
        printGeneric("\nGenerating images...\n")
        printGeneric("Positive prompt:\n" + positivePrompt + "\n")
        if len(negativePrompt) > 0:
            printGeneric("Negative prompt:\n" + negativePrompt + "\n")
        printGeneric("Image Settings:")
        printGeneric("Dimensions: " + configs["image_size"])
        printGeneric("Step: " + str(configs["image_step"]))
        if configs["parallel_requests_gpu_max"] + configs["parallel_requests_cpu_max"] > 1:
            printGeneric("\nWorkers: " +
                str(configs["parallel_requests_gpu_max"]) + " GPU + " +
                str(configs["parallel_requests_cpu_max"]) + " CPU")
        else:
            printDebug("\nUsing single worker.")
        printGeneric("")
        printSeparator()
        
        global shouldGenerateNextImage
        shouldGenerateNextImage = True
        
        
        global imageThreadsCPU
        global imageThreadsGPU
        
        if len(imageThreadsCPU) + len(imageThreadsGPU) > 1:
            printGeneric("")
            if len(imageThreadsCPU) > 0:
                for c in imageThreadsCPU.keys():
                    fullCPUModelName = configs["default_image_model"] + "-cpu" + str(c)
                    if getModelByName(fullCPUModelName, False) is not None:
                        actualRunningThreadsCPU[c] = False
                        printDebug("Found config for: " + fullCPUModelName)
                    else:
                        printError(fullCPUModelName + " does not exist - skipping worker.")
            if len(imageThreadsGPU) > 0:
                for g in imageThreadsGPU.keys():
                    fullGPUModelName = configs["default_image_model"] + "-gpu" + str(g)
                    if getModelByName(fullGPUModelName, False) is not None:
                        actualRunningThreadsGPU[g] = False
                        printDebug("Found config for: " + fullGPUModelName)
                    else:
                        printError(fullGPUModelName + " does not exist - skipping worker.")
            
            if len(actualRunningThreadsGPU) + len(actualRunningThreadsCPU) > 0:
                while True:
                    if shouldGenerateNextImage:
                        for threadNumber, isRunning in actualRunningThreadsGPU.items():
                            if not isRunning:
                                actualRunningThreadsGPU[threadNumber] = True
                                Thread(target=imageWorkerGPU, args=(threadNumber,)).start()
                        for threadNumber, isRunning in actualRunningThreadsCPU.items():
                            if not isRunning:
                                actualRunningThreadsCPU[threadNumber] = True
                                Thread(target=imageWorkerCPU, args=(threadNumber,)).start()
                    else:
                        runningThread = False
                        for isRunning in actualRunningThreadsGPU.values():
                            if isRunning:
                                runningThread = True
                                break
                        if not runningThread:
                            for isRunning in actualRunningThreadsCPU.values():
                                if isRunning:
                                    runningThread = True
                                    break
                        if not runningThread:
                            printGeneric("\nExiting continous image generation - returning to image menu.\n")
                            break
            else:
                printError("\nThere are no worker threads to run.")
                printError("Ensure models are correctly configured.\n")
                return
        else:
            while True:
                if shouldGenerateNextImage:
                    tic = time.perf_counter()
                    printResponse("\nImage created: " + getImageResponse(imageDesc, silent=True) + "\n")
                    toc = time.perf_counter()
                    printDebug(f"{toc - tic:0.3f} seconds\n")
                    printSeparator()
                else:
                    printGeneric("\nExiting continous image generation - returning to image menu.\n")
                    break
    else:
        printError("\nImage prompt was empty - returning to image menu.\n")
    return


def submenu_image_settings_size():
    def image_size_verifier(nextSizeIn):
        newRes = nextSizeIn.split("x")
        if len(newRes) == 2:
            try:
                int(newRes[0])
                int(newRes[1])
                return [nextSizeIn, True]
            except:
                return [nextSizeIn, False]
        else:
            return [nextSizeIn, False]
    
    printGeneric("\nSet the output image resolution, in [width]x[height].")
    printGeneric("Large images will take more time, especially with a high step value.\n")
    
    
    configs["image_size"] = setOrDefault(
        "Enter the new image size",
        configs["image_size"],
        image_size_verifier,
        "Keeping current image size",
        "Image size set to",
        "Resolution entered is not in the format [width]x[height]\nKeeping current image size"
    )
    return


def submenu_image_settings_step():
    printGeneric("\nSteps is the number of refinement iterations to do on a given image.")
    printGeneric("More steps usually result in better images, but with gradual diminishing returns.")
    printGeneric("Higher values will negatively affect processing time with large images.\n")
    
    configs["image_step"] = setOrDefault(
        "Enter image step value",
        configs["image_step"],
        intVerifier,
        "Keeping current image step value",
        "Image step value set to",
        "Invalid integer value - keeping current image step value"
    )
    return


### End image submenus ###


def command_modelscanner():
    modelList = getModelList()
    if modelList is not None:
        addModels = {}
        for model in modelList:
            if not model["id"] in configs["model_scanner_ignored_filenames"] and not model["id"] in modelConfigs.keys():
                printDebug(model["id"] + " is missing from model config")
                addModels[model["id"]] = {"text_model": False, "switchable": False, "description": ""}
        printDebug("")

        newModelsJson = modelConfigs | addModels
        outputFileString = json.dumps(newModelsJson, indent=4)
        
        printDump("\nNew models.json:\n\n" + outputFileString + "\n")
        
        deleteFile("", "models.json")
        appendFile("", "models.json", outputFileString)
        loadModelConfiguration()
        
        printGeneric("\nSuccessfully updated your models.json!\n")
    else:
        printGeneric("\nCould not update your models.json. (Check your connection?)\n")
    return


def command_selftest():
    printGeneric("\nWe will run a few tests to ensure everything works with the server...and in the program! :)")
    printGeneric("(This may take a really long time.)\n")
    if printYNQuestion("Do you want to continue?"):
        passes = 0
        target = 7
        
        printGeneric("\nTesting chat completion...\n")
        getChatCompletionResponse("Hi there, how are you?", ["Respond to USER in a respectful manner."], True)
        printGreen("\nChat completion test passed!\n")
        passes += 1
        
        printGeneric("\nTesting model switcher...\n")
        currentModelSwitcherSetting = configs["enable_automatic_model_switching"]
        configs["enable_automatic_model_switching"] = True
        getModelResponse("Write a simple python function that prints 'Hello, World!'")
        configs["enable_automatic_model_switching"] = currentModelSwitcherSetting
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
            printError("\nSome tests failed - read log for details.\n")
    else:
        printDebug("\nReturning to menu.\n")
    return


commandMap = {
    command_help:               ["/help",           "General",      "Shows all available commands."],
    command_clear:              ["/clear",          "General",      "Clears the prompt window."],
    command_config:             ["/config",         "General",      "Reload the configuration files."],
    command_settings:           ["/settings",       "General",      "Prints all current settings."],
    command_exit:               ["/exit",           "General",      "Exits the program."],
    
    command_convo:              ["/convo",          "Settings",     "Change the conversation file."],
    command_model:              ["/model",          "Settings",     "Change the text model."],
    command_system_prompt:      ["/system",         "Settings",     "Change the system prompt."],
    
    command_functions:          ["/functions",      "Toggles",      "Toggle on/off functions."],
    command_history:            ["/history",        "Toggles",      "Toggle on/off history consideration."],
    command_online:             ["/online",         "Toggles",      "Toggle on/off internet for actions."],
    command_switcher:           ["/switcher",       "Toggles",      "Toggle on/off automatic model switcher."],
    
    command_curl:               ["/curl",           "Tools",        "Send cURL commands to the server."],
    command_image:              ["/image",          "Tools",        "Generate images."],
    command_modelscanner:       ["/modelscanner",   "Tools",        "Scan for models on the server."],
    command_selftest:           ["/selftest",       "Tools",        "Test all program functionality."],
}


#################################################
############### BEGIN COMPLETIONS ###############
#################################################


def function_action(actions_array):
    return


def getChatCompletionResponse(userPromptIn, dataIn = [], shouldWriteDataToConvo = False):
    nextModel = getModelResponse(userPromptIn)
    
    if nextModel is not None and nextModel is not configs["default_model"]:
        configs["default_model"] = nextModel
    
    if configs["enable_chat_history_consideration"]:
        promptHistory = getPromptHistory()
    else:
        promptHistory = []
    
    if len(dataIn) > 0:
        promptHistory = addToPrompt(promptHistory, "system", strRespondUsingInformation + formatArrayToString(dataIn, " "))
    
    if len(configs["system_prompt"]) > 0:
        promptHistory = addToPrompt(promptHistory, "system", configs["system_prompt"])
    
    promptHistory = addToPrompt(promptHistory, "user", userPromptIn)
    
    printPromptHistory(promptHistory)
    
    completion = createOpenAIChatCompletionRequest(configs["default_model"], promptHistory, shouldStream = True)
    
    printResponse("")
    if completion is not None:
        assistantResponse = ""
        pausedLetters = ""
        potentialStopwords = {}
        stop = False
        tic = time.perf_counter()
        toc = time.perf_counter()
        while (toc - tic) < configs["response_timeout_seconds"]:
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


strFunctionSystemPromptBody = """Actions in the action plan should only be present if they are crucial for task completion and to provide accurate responses.
You are always strongly encouraged to use the internet for updated and current information, as well as for information on niche and specific topics.
You will get the current location data, when prompted for local information, such as, but not limited to, nearby places and venues, or weather updates.
You will get the current time and date data, when prompted for current information that is time-sensitive, such as, but not limited to, news updates.
If additional actions should be used, then create an action plan in the form of an array.
Otherwise, create an blank array.
Available actions are: '""" + formatArrayToString(actionEnums, "', '") + """'."""


strFunctionSystemPrompt = """Determine if additional actions should be completed in order to fulfill the tasks given by, and/or to provide an accurate response to, the USER's requests.
""" + strFunctionSystemPromptBody


strFunctionEditSystemPrompt = """Make revisions to the remaining actions in the action plan, if necessary, using the newly gathered information.
""" + strFunctionSystemPromptBody


strFunctionActionsArrayDescription = """An order-sensitive action plan array that will be completed in order to complete the USER's prompt.
Each item in the array consists of a single action, and its corresponding input data for the action.
Duplicate actions are permitted, only when the input data is different between each action.
If additional actions should be used, then create an action plan in the form of an array.
Otherwise, create an blank array.
Available actions are: '""" + formatArrayToString(actionEnums, "', '") + """'."""


strFunctionActionDescription = """The action to be completed at this step of the action plan.
Use 'GET_UPDATED_LOCATION_DATA' to get the current location.
Use 'GET_UPDATED_TIME_AND_DATE_DATA' to get the current date and time.
Use 'SEARCH_INTERNET_WITH_SEARCH_TERM' to search for a single topic or subject, using current and updated information from the internet.
Use 'GENERATE_IMAGE_WITH_DESCRIPTION' to create an artificial image, only when explicitly requested.
Use 'WRITE_FILE_TO_FILESYSTEM' to create a new file on the filesystem."""


strFunctionActionInputDataDescription = """The input data that corresponds to this specific action.
If the action is 'SEARCH_INTERNET_WITH_SEARCH_TERM', then provide the search terms that will be used to search for information on the internet.
If the action is 'GENERATE_IMAGE_WITH_DESCRIPTION', then provide a brief detailed description of the image to be created.
If the action is 'WRITE_FILE_TO_FILESYSTEM', then provide the name for the file, a colon and a space, and then the contents of the file inside of curly braces."""


function = [{
    "name": "function_action",
    "parameters": {
        "type": "object",
        "properties": {
            "actions_array": {
                "type": "array",
                "description": strFunctionActionsArrayDescription,
                "items": {
                    "type": "object",
                    "properties": {
                        "action": {
                            "type": "string",
                            "description": strFunctionActionDescription,
                            "enum": actionEnums,
                        },
                        "action_input_data": {
                            "type": "string",
                            "description": strFunctionActionInputDataDescription,
                        }
                    }
                }
            }
        }
    }
}]


def getFunctionResponse(promptIn):
    if configs["enable_automatic_model_switching"]:
        resetCurrentModel()
    
    hrefs = []
    searchedTerms = []
    datas = []
    promptHistory = []
    lastActionsArray = []
    firstRun = True
    
    # revision, formatting and code cleanup needed
    while True:
        if configs["enable_chat_history_consideration"]:
            promptHistory = getPromptHistory()
        
        if firstRun:
            firstRun = False
            prompt = addToPrompt([], "system", strFunctionSystemPrompt)
        else:
            formattedLastActionsArray = []
            for a in lastActionsArray:
                formattedLastActionsArray.append("\n - " + a["action"] + ": " + a["action_input_data"])
            systemPromptHistory = []
            systemPromptHistory = addToPrompt(systemPromptHistory, "system", strRespondUsingInformation + formatArrayToString(datas, " "))
            systemPromptWithLastActionsResponse = strFunctionEditSystemPrompt + """Remaining actions: """ + formatArrayToString(formattedLastActionsArray, " ")
            prompt = addToPrompt(systemPromptHistory, "system", systemPromptWithLastActionsResponse)
        
        prompt = addToPrompt(prompt, "user", promptIn)
        
        fullPrompt = promptHistory + prompt
        
        printPromptHistory(fullPrompt)
        printDebug("\nDetermining function(s) to do for this prompt...")

        actionsResponse = createOpenAIChatCompletionRequest(
            configs["default_model"],
            fullPrompt,
            functionsIn = function,
            functionCallIn = { "name": "function_action" },
        )
        
        if actionsResponse is not None and actionsResponse.get("actions_array") is not None:
            actionsArray = actionsResponse.get("actions_array")
            
            printDebug("\nDetermined actions and input data:")
            
            # print all actions to do
            if len(actionsArray) > 0 and len(actionsArray[0]) > 0:
                for action in actionsArray:
                    printDebug(" - " + action.get("action") +": " + action.get("action_input_data"))
            else:
                printDebug("(None)")
            
            # do the first action in the array
            if len(actionsArray) > 0:
                action = actionsArray[0]
                theAction = action.get("action")
                theActionInputData = action.get("action_input_data")
                match theAction:
                    
                    
                    case "SEARCH_INTERNET_WITH_SEARCH_TERM":
                        if not configs["enable_internet"]:
                            printDebug("\nInternet is disabled - skipping this action. ('" + theAction + "': " + theActionInputData + ")")
                        else:
                            if len(theActionInputData) > 0:
                                theActionInputData = theActionInputData.lower()
                                if not theActionInputData in searchedTerms and not theActionInputData.upper() in actionEnums:
                                    searchedTerms.append(theActionInputData)
                                    searchResultSources = getSourcesResponse(theActionInputData, configs["max_sources_per_search"])
                                    nonDuplicateHrefs = []
                                    for href in searchResultSources:
                                        if href not in hrefs:
                                            nonDuplicateHrefs.append(href)
                                        else:
                                            printDebug("\nSkipped duplicate source: " + key)
                                    if len(nonDuplicateHrefs) > 0:
                                        searchResults = getSourcesTextAsync(nonDuplicateHrefs, configs["max_sentences_per_source"])
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
                        if not configs["enable_internet"]:
                            printDebug("\nInternet is disabled - skipping this action. ('" + theAction + "': " + theActionInputData + ")")
                        else:
                            ipRequest = requests.get('https://api64.ipify.org?format=json').json()
                            printDump("\nIP result: " + str(ipRequest))
                            ip = ipRequest["ip"]
                            loc = requests.get(f'https://ipapi.co/{ip}/json/').json()
                            if loc.get("error") is None:
                                printDump("\nLocation result: " + str(loc))
                                fullAddr = loc.get("city") + ", " + loc.get("region") + ", " + loc.get("country_name")
                                for a in actionsArray:
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
                        for a in actionsArray:
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
                
                printDebug("\nAction '" + theAction +": " + theActionInputData + "' has completed successfully.")
                
                if len(actionsArray) >= 1:
                    lastActionsArray = actionsArray
                    lastActionsArray.pop(0)
                    printDebug("\nReprompting model with action plan.")
                else:
                    printDebug("\nThis was the last action in the action plan - exiting loop.")
                    break
            else:
                printDebug("\nNo more actions in the action plan - exiting loop.")
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


def getImageResponse(promptIn, seedIn=None, silent=False, isCPU=False, threadNumber=1):
    if seedIn is None:
        seedIn = random.randrange(-9999999999, 9999999999)
    else:
        seedIn = int(seedIn)
    
    positivePrompt = ""
    negativePrompt = ""
    prompts = promptIn.split(" | ")
    if len(prompts) == 2:
        positivePrompt = prompts[0]
        negativePrompt = prompts[1]
    elif len(prompts) == 1:
        positivePrompt = promptIn
    else:
        printError("\nThe prompt is malformed.")
        printError("You must enter a prompt in the form of:")
        printError("'positive prompt | negative prompt'")
        return ""
    
    if not silent:
        printInfo("\nGenerating image...\n")
        printDebug("Positive prompt:\n" + positivePrompt + "\n")
        if len(negativePrompt) > 0:
            printDebug("Negative prompt:\n" + negativePrompt + "\n")
        printDebug("Image Settings:")
        printDebug("Dimensions: " + configs["image_size"])
        printDebug("Seed: " + str(seedIn))
        printDebug("Step: " + str(configs["image_step"]))
    
    
    imageModel = configs["default_image_model"]
    
    if isCPU:
        imageModel += "-cpu"
    else:
        imageModel += "-gpu"
    
    imageModel += str(threadNumber)
    
    theURL = createOpenAIImageRequest(
        imageModel,
        positivePrompt,
        negativePrompt,
        configs["image_size"],
        seedIn,
        configs["image_step"]
    )
    
    if theURL is not None:
        split = theURL.split("/")
        filename = split[len(split) - 1]
        filename = "output/" + filename
        urllib.request.urlretrieve(theURL, filename)
        
        if configs["automatically_open_files"]:
            openLocalFile(filename)
        
        if silent:
            return filename
        else:
            return "Your image is available at: " + filename
    else:
        printError("\nImage creation failed!\n")
        return ""


def getModelResponse(promptIn):
    if not configs["enable_automatic_model_switching"]:
        return configs["default_model"]
    else:
        resetCurrentModel()
        
        promptMessage = addToPrompt([], "system", strDetermineBestAssistant + getEnabledModelDescriptions())
        promptMessage = addToPrompt(promptMessage, "user", promptIn)
        
        grammarString = getGrammarString(getEnabledModelNames())
        
        printDump("\nCurrent prompt for model response:")
        printPromptHistory(promptMessage)
        printDump("\nChoices: " + grammarString)
        nextModel = createOpenAIChatCompletionRequest(configs["default_model"], promptMessage, grammarIn = grammarString)
        printDebug("\nNext model: " + nextModel)
        return getModelByName(nextModel)


##################################################
################### BEGIN CHAT ###################
##################################################


def handlePrompt(promptIn):
    if checkCommands(promptIn) == False:
        if checkTriggers(promptIn) == False:
            tic = time.perf_counter()
            if configs["enable_functions"]:
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
        for func, value in commandMap.items():
            if promptIn == value[0]:
                func()
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


#################################################
############## BEGIN INITALIZATION ##############
#################################################


loadModelConfiguration()
loadConfiguration()


def key_Listener(key):
    global shouldGenerateNextImage
    if key == keyboard.Key.f12 and shouldGenerateNextImage:
        shouldGenerateNextImage = False
        printRed("\n[F12] pressed - waiting for image generators to complete then exiting...\n")
        printSeparator()
    return


keyboardListener = keyboard.Listener(on_press=key_Listener)
keyboardListener.start()

setConversation(strConvoTimestamp)

command_clear()

printSeparator()
printGeneric("Note: This script can sometimes block the use of the [F12] key.")
printGeneric("Remap this in code if needed.")
printSeparator()

command_settings()


##################################################
################### BEGIN MAIN ###################
##################################################


def main():
    while True:
        printSeparator()
        strPrompt = printInput("Enter a prompt ('/help' for list of commands): ")
        printSeparator()
        if not checkEmptyString(strPrompt):
            handlePrompt(strPrompt)
        else:
            command_help()


if __name__ == "__main__":
    main()


