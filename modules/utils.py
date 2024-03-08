import json
import openai
import os
import psutil
import random
import re
import time

from termcolor import colored
# https://pypi.org/project/termcolor/


configuration = dict()


def initConfig(fileConfiguration):
    for line in fileConfiguration:
        if len(line) > 0 and not line.startswith("#") and not checkEmptyString(line):
            key = line.split("=")[0]
            value = line.split("=")[1]
            configuration[key] = value


def printInput(string):
    strInput = input(colored(string, "white", attrs=["bold"]))
    return strInput


def printResponse(string, endIn="\n"):
    print(colored(string, "green"), end=endIn)
    return


def printGeneric(string):
    print(colored(string, "light_grey"))
    return


def printGreen(string):
    print(colored(string, "light_green"))
    return


def printRed(string):
    print(colored(string, "light_red"))
    return


def printError(string):
    if int(configuration["DEBUG_LEVEL"]) >= 1:
        print(colored(string, "red"))
    return


def printInfo(string):
    if int(configuration["DEBUG_LEVEL"]) >= 2:
        print(colored(string, "yellow"))
    return


def printDebug(string):
    if int(configuration["DEBUG_LEVEL"]) >= 3:
        print(colored(string, "light_grey"))
    return


def printDump(string):
    if int(configuration["DEBUG_LEVEL"]) >= 4:
        print(colored(string, "dark_grey"))
    return


def printSeparator():
    printGeneric("-------------------------------------------------------------")
    return


def printSetting(isEnabled, descriptionIn):
    if isEnabled:
        printGeneric("[ON] " + descriptionIn)
    else:
        printGeneric("[OFF] " + descriptionIn)
    return


def cleanupString(stringIn):
    out = stringIn.replace("\n", " ").replace("\r", " ")         # remove all newlines
    out = ' '.join(out.split())                                  # remove all redundant spaces
    out = (out.encode("ascii", errors="ignore")).decode()        # drop all non-ascii chars
    return out


def getFilePathFromPrompt(stringIn):
    return (re.findall(r"'(.*?)'", stringIn, re.DOTALL))[0]


def trimTextBySentenceLength(textIn, maxLength):
    i = 0               # char position
    j = 0               # sentences
    k = 0               # chars since last sentence
    flag = False        # deleted a "short" sentence this run
    for char in textIn:
        i += 1
        k += 1
        if ("!" == char or 
            "?" == char or 
            "." == char and 
                (not textIn[i - 1].isnumeric() or 
                (i + 1 <= len(textIn) - 1 and not textIn[i + 1].isnumeric()))
            ):
            j += 1
            if k < 24 and not flag:
                j -= 1
                flag = True
            if j == maxLength:
                return textIn[0:i]
            k = 0
            flag = False
    return textIn


def checkEmptyString(strIn):
    blanks = [" ", "\t", "\n", "\v", "\r", "\f"]
    for s in strIn:
        if s not in blanks:
            return False
    return True


def formatArrayToString(dataIn, separator):
    stringBuilder = ""
    i = 0
    while i < len(dataIn):
        stringBuilder += dataIn[i]
        if i is not len(dataIn) - 1:
            stringBuilder += separator
        i += 1
    return stringBuilder


def errorBlankEmptyText(sourceIn):
    printError("The " + sourceIn + " is empty/blank!")
    return "The text received from the " + sourceIn + " is blank and/or empty. Notify the user about this."


def createOpenAIChatCompletionRequest(modelIn, messagesIn, shouldStream = False, functionsIn = None, functionCallIn = None, grammarIn = None):
    failedCompletions = 0
    while True:
        try:
            completion = openai.ChatCompletion.create(
                model = modelIn,
                messages = messagesIn,
                stream = shouldStream,
                functions = functionsIn,
                function_call = functionCallIn,
                grammar = grammarIn
            )
            if shouldStream:
                return completion
            else:
                if functionsIn is None:
                    return completion.choices[0].message.content
                else:
                    return json.loads(completion.choices[0].message.function_call.arguments)
        except Exception as e:
            printOpenAIError(e, failedCompletions)
            if failedCompletions < 2:
                failedCompletions += 1
                time.sleep(3)
            else:
                return None
    return


def createOpenAIImageRequest(modelIn, promptIn, sizeIn):
    failedCompletions = 0
    while True:
        try:
            completion = openai.Image.create(
                model = strModelStableDiffusion,
                prompt = promptIn,
                size = strImageSize,
            )
            return completion.data[0].url
        except Exception as e:
            printOpenAIError(e, failedCompletions)
            if failedCompletions < 2:
                failedCompletions += 1
                time.sleep(3)
            else:
                return
    return


def printOpenAIError(error, iteration):
    if iteration < 2:
        printError("Failed to create completion! Trying again...")
    else:
        printError("Failed to create completion after 3 tries!")
    printError(str(error))
    if error.json_body is None:
        printError("Failed to read the error!")
        printError("(Are you sure you have the correct address set?)")
    else:
        theError = json.loads(json.dumps(error.json_body["error"]))
        code = theError["code"]
        message = theError["message"]
        printError("(" + str(code) + ": " + message + ")")
    return


def killLlama():
    hasResult = False
    for process in psutil.process_iter():
        if process.name() == "llama":
            process.kill()
            printDebug("llama has been killed off!")
            hasResult = True
            time.sleep(1)
    if not hasResult:
        printError("Couldn't kill the llama process! Are you on the same machine as LocalAI?")
        printError("(You can ignore this if llama hasn't been started yet.)")
    return

