import util
import inspect

loglevels = ["INFO ", "WARN ", "ERROR"]

def levelToString(level: int):
    return loglevels[util.constrain(level, 0, len(loglevels)-1)]

def info(msg):
    print(f"{levelToString(0)} | {msg}")

def warning(msg):
    print(f"{levelToString(1)} | {inspect.stack()[1].function}: {msg}")

def error(msg):
    print(f"{levelToString(2)} | {inspect.stack()[1].function}: {msg}")

def fatal(msg):
    print(f"{levelToString(3)} | {inspect.stack()[1].function}: {msg}")
    exit(1)