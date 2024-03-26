import subprocess


from modules.utils import *


availableCommands = [
    "apply",
    "available",
    "jobs",
    "models",
    "raw"
]


def printStdout(errorsIn):
    if errorsIn is not None and len(errorsIn) > 0:
        j = json.loads(errorsIn)
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
    cmdStringBuilder = "curl "
    printSeparator()
    cmdType = printInput("Enter the command type: " ).lower()
    printSeparator()
    if configuration["ADDRESS"].endswith("/"):
        cmdStringBuilder += configuration["ADDRESS"]
    else:
        cmdStringBuilder += configuration["ADDRESS"] + "/"
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

