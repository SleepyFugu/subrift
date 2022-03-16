import util
import inspect

loglevels = ["INFO ", "WARN ", "ERROR", "FATAL", "DEBUG"]
debug_enabled = False

def enableDebug():
  global debug
  global debug_enabled
  debug_enabled = True
  info("Enabled debugging mode")
  def debug(msg):
    print(f"{levelToString(4)} | {inspect.stack()[1].function}: {msg}")

def disableDebug():
  global debug
  global debug_enabled
  debug_enabled = False
  info("Disabled debugging mode")
  def debug(_):
    return None

def debugEnabled() -> bool:
  debug_enabled

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

def debug(_):
  return