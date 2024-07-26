import json
import openai
import os
import random
import readline
import time


from termcolor import colored
# https://pypi.org/project/termcolor/


from modules.file_operations import *


debugLevel = (json.loads(readFile("", "config.json")))["main_configuration"]["debug_level"]
bypassYN = (json.loads(readFile("", "config.json")))["main_configuration"]["always_yes_to_yn_operations"]


##################################################
################## BEGIN PRINTS ##################
##################################################


def printInput(string):
    strInput = input(string)
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
    if debugLevel >= 1:
        print(colored(string, "red"))
    return


def printInfo(string):
    if debugLevel >= 2:
        print(colored(string, "yellow"))
    return


def printDebug(string):
    if debugLevel >= 3:
        print(colored(string, "light_grey"))
    return


def printDump(string):
    if debugLevel >= 4:
        print(colored(string, "dark_grey"))
    return


def printSeparator():
    printGeneric("-------------------------------------------------------------")
    return


def printPromptHistory(promptHistory):
    printDump("")
    printDump("Current conversation:")
    for item in promptHistory:
        printDump(item["content"])
    return


def printSetting(isEnabled, descriptionIn):
    if isEnabled:
        printGeneric("[ON] " + descriptionIn)
    else:
        printGeneric("[OFF] " + descriptionIn)
    return


def command_clear():
    i = 0
    j = 64
    while i <= j:
        printGeneric("\n")
        i += 1
    return


def printOpenAIError(error, iteration):
    if iteration < 2:
        printError("\nFailed to create completion! Trying again...")
    else:
        printError("\nFailed to create completion after 3 tries!")
    if type(error) is openai.OpenAIError:
        if error.json_body is None:
            body = str(error)
            if "111" in body or "Connection refused" in body:
                printError("(Are you sure you have the correct address set?)")
            else:
                printError(body)
        else:
            theError = json.loads(json.dumps(error.json_body["error"]))
            code = theError["code"]
            message = theError["message"]
            printError("(" + str(code) + ": " + message + ")")
    else:
        printError(str(error))
    return


def printFormattedJson(jsonIn, printFunc=printDump):
    printFunc(json.dumps(jsonIn, sort_keys=True, indent=4))
    return


def printYNQuestion(messageIn, override=False):
    if bypassYN and not override:
        return True
    else:
        printSeparator()
        result = printInput(messageIn + " (Y/n): ")
        printSeparator()
        return result.lower() == "y"


##################################################
################ BEGIN STRING OPS ################
##################################################


blankCharacters = [
    "\t",
    "\n",
    "\v",
    "\r",
    "\f"
]


def addToPrompt(prompt, role, content):
    roleName = role.upper() + ": "
    prompt.append({"role": role, "content": roleName + content})
    return prompt


def cleanupString(stringIn):
    for char in blankCharacters:
        out = stringIn.replace(char, " ")                        # remove all tabs, newlines, other special spaces
    out = ' '.join(out.split())                                  # remove all redundant spaces
    out = (out.encode("ascii", errors="ignore")).decode()        # drop all non-ascii chars
    return out


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
    blanks = blankCharacters + [" "]
    for s in strIn:
        if s not in blanks:
            return False
    return True


def formatArrayToString(dataIn, separator):
    stringBuilder = ""
    i = 0
    while i < len(dataIn):
        stringBuilder += str(dataIn[i])
        if i is not len(dataIn) - 1:
            stringBuilder += separator
        i += 1
    return cleanupString(stringBuilder)


def getGrammarString(listIn):
    grammarStringBuilder = "root ::= ("
    for item in listIn:
        if len(grammarStringBuilder) > 10:
            grammarStringBuilder += " | "
        grammarStringBuilder += "\"" + item + "\""
    grammarStringBuilder += ")"
    return grammarStringBuilder


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


def errorBlankEmptyText(sourceIn):
    printError("The " + sourceIn + " is empty/blank!")
    return "The text received from the " + sourceIn + " is blank and/or empty."


##################################################
################ BEGIN MISC UTILS ################
##################################################


def setOrDefault(promptIn, defaultValueIn, verifierFuncIn, keepDefaultValueStringIn, setValueStringIn, verifierErrorStringIn):
    result = printInput(promptIn + " (leave empty for current '" + defaultValueIn + "'): ")
    printSeparator()
    if len(result) == 0:
        printRed("\n" + keepDefaultValueStringIn + ": " + defaultValueIn + "\n")
        return defaultValueIn
    else:
        verifiedResult = verifierFuncIn(result)
        if verifiedResult[1]:
            printGreen("\n" + setValueStringIn + ": " + verifiedResult[0] + "\n")
            return verifiedResult[0]
        else:
            printRed("\n" + verifierErrorStringIn + ": " + defaultValueIn + "\n")
            return defaultValueIn


#################################################
############# BEGIN OPENAI REQUESTS #############
#################################################


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
                message = completion.choices[0].message
                if functionsIn is None:
                    return message.content
                else:
                    try:
                        if message.function_call is not None and message.function_call.arguments is not None:
                            return json.loads(message.function_call.arguments)
                    except Exception as e:
                        arguments = json.loads(message.content.replace("</s>", ""))
                        return arguments["arguments"]
        except Exception as e:
            printOpenAIError(e, failedCompletions)
            if failedCompletions < 2:
                failedCompletions += 1
                time.sleep(3)
            else:
                return None


def createOpenAIImageRequest(modelIn, positivePromptIn, negativePromptIn, sizeIn, seedIn, stepIn, clipSkipIn):
    failedCompletions = 0
    while True:
        try:
            completion = openai.Image.create(
                model = modelIn,
                prompt = positivePromptIn,
                negative_prompt = negativePromptIn,
                size = sizeIn,
                seed = seedIn,
                step = stepIn,
                clip_skip = clipSkipIn,
            )
            return completion.data[0].url
        except Exception as e:
            printOpenAIError(e, failedCompletions)
            if failedCompletions < 2:
                failedCompletions += 1
                time.sleep(3)
            else:
                return

