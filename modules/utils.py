import json
import openai
import os
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


def addToPrompt(prompt, role, content):
    roleName = role.upper() + ": "
    prompt.append({"role": role, "content": roleName + content})
    return prompt


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


def cleanupString(stringIn):
    out = stringIn.replace("\n", " ").replace("\r", " ")         # remove all newlines
    out = ' '.join(out.split())                                  # remove all redundant spaces
    out = (out.encode("ascii", errors="ignore")).decode()        # drop all non-ascii chars
    return out


def getFilePathFromPrompt(stringIn):
    return (re.findall(r"'(.*?)'", stringIn, re.DOTALL))


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


def getGrammarString(listIn):
    grammarStringBuilder = "root ::= ("
    for item in listIn:
        if len(grammarStringBuilder) > 10:
            grammarStringBuilder += " | "
        grammarStringBuilder += "\"" + item + "\""
    grammarStringBuilder += ")"
    return grammarStringBuilder


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
    return


def createOpenAIImageRequest(modelIn, promptIn, sizeIn):
    failedCompletions = 0
    while True:
        try:
            completion = openai.Image.create(
                model = modelIn,
                prompt = promptIn,
                size = sizeIn,
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

