import json
import subprocess


from modules.utils import *


address = (json.loads(readFile("", "config.json")))["main_configuration"]["address"]


availableCommands = [
    "apply",
    "available",
    "jobs",
    "models",
    "raw"
]


def printStdout(stdoutIn):
    if stdoutIn is not None and len(stdoutIn) > 0:
        j = json.loads(stdoutIn)
        printGeneric("")
        if j is not None and "error" in j and not '"error:null"' in j:
            printRed("Response:")
            printFormattedJson(j, printRed)
        else:
            printGreen("Response:")
            printFormattedJson(j, printGreen)
    return


def sendCurlCommand():
    printGeneric("")
    printGeneric("Commands types available:")
    printGeneric("")
    for c in availableCommands:
        printGeneric("- " + c)
    printGeneric("")
    cmdStringBuilder = "curl " + address
    printSeparator()
    cmdType = printInput("Enter the command type: " ).lower()
    printSeparator()
    if not address.endswith("/"):
        cmdStringBuilder += "/"
    isFunction = False
    match cmdType:
        case "apply":
            cmdStringBuilder += "models/apply"
        case "available":
            isFunction = True
            cmdStringBuilder += "models/available"
        case "jobs":
            isFunction = True
            cmdStringBuilder += "models/jobs/" + printInput("Input the job UUID: ")
            printSeparator()
        case "models":
            isFunction = True
            cmdStringBuilder += "v1/models"
        case "raw":
            isFunction = True
            printGeneric("")
            printGeneric("Current curl command: '" + cmdStringBuilder + "'")
            printGeneric("")
            printSeparator()
            cmdStringBuilder += printInput("Enter the text to append: ")
        case _:
            printRed("")
            printRed("This is not a valid command type!")
            return
    if not isFunction:
        cmdStringBuilder += " -H 'Content-Type: application/json' -d '{"
        cmdStringBuilder += printInput("Enter the command contents: " )
        printSeparator()
        cmdStringBuilder += " }'"
    printDebug("")
    printDebug("Sending command:")
    printDebug(cmdStringBuilder)
    printStdout(
        subprocess.run(
            cmdStringBuilder.split(" "),
            capture_output = True,
            text = True
        ).stdout
    )
    return


def getModelList():
    cmdStringBuilder = "curl " + address
    if not address.endswith("/"):
        cmdStringBuilder += "/"
    cmdStringBuilder += "v1/models"
    result = subprocess.run(
        cmdStringBuilder.split(" "),
        capture_output = True,
        text = True
    ).stdout
    printDump("\n" + result + "\n")
    if result is not None and not checkEmptyString(result):
        return json.loads(result)["data"]
    else:
        printDebug("\nError getting model list.\n")
        return None


