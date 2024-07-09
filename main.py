# Imports (standard library)
import os
import sys
import json
import time
import datetime

# Imports (non-standard library)
import psutil
import requests

LOG_TO_FILE = True
LOGPATH = None
CONFIG = {}
TEST = False
CFG_PATH = "cfg.json"

default_config = {
    "webhook_url": "[YOUR DISCORD WEBHOOK REPORT URL HERE]",
    "panic_url": "[YOUR DISCORD WEBHOOK PANIC URL HERE]",
    "webhook_name": "[YOUR DISCORD WEBHOOK NAME HERE]",
    "cpu_threshold": 80,
    "log_file_retention_days": 30,
    "delay_secs": 5
}

# # Set up logging
# if(LOG_TO_FILE):
#     # Ensure the logs directory exists
#     if not os.path.exists("logs"):
#         os.makedirs("logs")

#     # Get the current date  
#     current_date = datetime.datetime.now().strftime("%Y-%m-%d")
#     logging.basicConfig(filename=os.path.join("logs", str(current_date + ".txt")), level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")
# else:
#     logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")
# l = logging.getLogger()

# # print(l.handlers)

# Setup logging



if(LOG_TO_FILE):
    # Ensure the logs directory exists
    if not os.path.exists("logs"):
        os.makedirs("logs")

    # Get the current date  
    current_date = datetime.datetime.now().strftime("%Y-%m-%d")
    LOGPATH = os.path.join("logs", str(current_date + ".txt"))


def log(log_msg, log_lvl="info"):
    # Get the current time
    current_time = datetime.datetime.now().strftime("%H:%M:%S")
    log_msg_actual = f"[{current_time}] - [{log_lvl.upper()}] - {log_msg}"

    # Log the message
    if(LOG_TO_FILE):
        # Logging to file, open the log file and write the message
        with open(LOGPATH, "a",encoding="UTF-8") as log_file:
            log_file.write(log_msg_actual + "\n")
    else:
        # Logging to console, print the message
        print(log_msg_actual)

def panic(panic_msg):
    log("Failure occurred: " + str(panic_msg), log_lvl="error")
    log("Sending panic message to alert webhook")
    panic_url = CONFIG.get("panic_url")
    log("Sending panic message to Discord, URL: %s" % panic_url)
    panic_data = {
        "content": "Failure occurred: \n" + str(panic_msg),
        "username": "webhook-alerts"
    }
    log("Panic message data: %s" % panic_data)
    panic_res = requests.post(panic_url, json=panic_data, timeout=100)
    log("Panic message sent")

    if panic_res.status_code != 204:
        log("Error sending panic message. Status Code: %s, Message: %s" % (panic_res.status_code, panic_res.text), log_lvl="error")
    elif panic_res.status_code == 200:
        log("Panic message maybe sent successfully")
    elif panic_res.status_code == 204:
        log("Panic message sent successfully")
    exit(0)

# Read the args, if any
if(len(sys.argv) > 1):
    if(sys.argv[1] == "--test"):
        TEST = True
    else:
        log("Unknown argument: %s" % sys.argv[1], log_lvl="error")

# Log startup, and if we're logging to a file
if(TEST):
    log("Startup *Test mode*")
else:
    log("Startup...")

if(LOG_TO_FILE):
    log("Logging to file")
else:
    log("Logging to console")

# Read config
log("Reading config")
# Check that the config file exists
if not os.path.exists(CFG_PATH):
    log("Config file does not exist, creating a new one", log_lvl="error")
    with open(CFG_PATH, "w", encoding="UTF-8") as f:
        f.write(json.dumps(default_config, indent=4))

# Read the config file
with open(CFG_PATH, "r", encoding="UTF-8") as f:
    CONFIG = json.load(f)

# If we're logging to a file, delete log files older than 30 days
if LOG_TO_FILE:
    log("Deleting log files older than 30 days")
    for file in os.listdir("logs"):
        file_path = os.path.join("logs", file)
        file_name = os.path.basename(file_path)
        if (datetime.datetime.now() - datetime.datetime.strptime(file_name, "%Y-%m-%d.txt")).days > CONFIG.get("log_file_retention_days", 30):
            log("Deleting old log file: %s" % file_path)
            os.remove(file_path)

# From https://shallowsky.com/blog/programming/cpu-hogs-in-python.html,
# we need to run the process twice, with a delay in between, to get accurate CPU usage
# read the delay from the config, default to 5 seconds

log("First CPU usage check")
for proc in psutil.process_iter():
    proc.cpu_percent(None)

# Get the delay from the config, default to 5 seconds
delay = CONFIG.get("delay_secs", 5)
log("Sleeping for %s seconds" % delay)
time.sleep(delay)

# Get a list of all processes, for realsies this time
log("Getting processes")
processes = []
for process in psutil.process_iter():
    try:
        # Get process information
        process_info = process.as_dict(attrs=['pid', 'cpu_percent', 'name', 'username', 'status', 'memory_percent', 'exe'])

        # Check if the process is just a system idle process, and skip it if it is
        if process_info.get('name') == "System Idle Process":
            continue

        # Add the process information to the list
        processes.append(process_info)
    except psutil.NoSuchProcess:
        pass

log("Got %s processes" % len(processes))

# Filter this to only include processes that are using lots of CPU
threshold = CONFIG.get("cpu_threshold", 80.0)
heavy_processes = []
for proc in processes:
    if proc.get('cpu_percent') > threshold:
        heavy_processes.append(proc)

log("Found %s heavy processes" % len(heavy_processes))

# If there are no heavy processes, we don't need to do anything
if len(heavy_processes) == 0:
    log("No heavy processes found, exiting...")
    exit()

log("Heavy processes found!", log_lvl="warning")

# Heavy processes found, send a notification
log("Sending notification", log_lvl="info")

# Create the message

#   # Message format:
#   Heavy processes found!
#   
#   #[Process Name]
#   exe: [Executable]
#   *CPU Usage: [CPU Usage]*%
#   Memory Usage: [Memory Usage]
#   pid: [PID]
#   status: [Status]
#   username: [Username]
#   
#   (This part then loops for each heavy process)

message = "Heavy processes found!\n\n"
log("List of heavy processes:", log_lvl="warning")
for proc in heavy_processes:
    message += "# " + proc.get('name') + "\n"
    message += "*CPU Usage: " + str(proc.get('cpu_percent')) + "*%\n"
    message += "exe: " + str(proc.get('exe')) + "\n"
    message += "Memory Usage: " + str(proc.get('memory_percent')) + "\n"
    message += "pid: " + str(proc.get('pid')) + "\n"
    message += "status: " + str(proc.get('status')) + "\n"
    message += "username: " + str(proc.get('username')) + "\n\n"

    # Also log the process, but just dump the dictionary
    log(proc, log_lvl="warning")

# Send the message
log("Sending message to Discord", log_lvl="info")

# Read the webhook URL and username from the config
webhook_url = CONFIG.get("webhook_url")
webhook_username = CONFIG.get("webhook_name")

# Create the data to send
data = {
    "username": webhook_username,
    "content": message
}

# Send the message
log("Preparing to send message with data: %s and webhook URL: %s" % (data, webhook_url), log_lvl="info")
if(TEST):
    log("Test mode, not sending message", log_lvl="info")
    res = requests.Response()
    res.status_code = 204
else:
    log("Sending message...", log_lvl="info")
    res = requests.post(webhook_url, json=data, timeout=100)
log("Message sent", log_lvl="info")

if(res.status_code != 204):
    # Log the error and send a panic message. Hopefully the panic message will be sent successfully
    log("Error sending message. Status Code: %s, Message: %s" % (res.status_code, res.text), log_lvl="error")
    panic("Error sending message. Status Code: " + str(res.status_code) + ", Message: " + str(res.text))
elif(res.status_code == 200):
    log("Message maybe sent successfully", log_lvl="info")
elif(res.status_code == 204):
    log("Message sent successfully", log_lvl="info")

# Log shutdown
log("Shutdown", log_lvl="info")