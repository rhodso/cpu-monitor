# Imports (standard library)
import os
import sys
import json
import logging
import time
import datetime

# Imports (non-standard library)
import psutil
import requests

LOG_TO_FILE = True
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

# Set up logging
if(LOG_TO_FILE):
    # Ensure the logs directory exists
    if not os.path.exists("logs"):
        os.makedirs("logs")

    # Get the current date  
    current_date = datetime.datetime.now().strftime("%Y-%m-%d")
    logging.basicConfig(filename=os.path.join("logs", str(current_date + ".txt")), level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")
else:
    logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")

def panic(panic_msg):
    logging.error("Failure occurred: %s", panic_msg)
    logging.info("Sending panic message to alert webhook")
    panic_url = CONFIG.get("panic_url")
    logging.info("Sending panic message to Discord, URL: %s", panic_url)
    data = {
        "content": "Failure occurred: \n" + str(panic_msg),
        "username": "webhook-alerts"
    }
    logging.info("Panic message data: %s", data)
    res = requests.post(panic_url, json=data)
    logging.info("Panic message sent")

    if(res.status_code != 204):
        logging.error("Error sending panic message. Status Code: %s, Message: %s", res.status_code, res.text)
    elif(res.status_code == 200):
        logging.info("Panic message maybe sent successfully")
    elif(res.status_code == 204):
        logging.info("Panic message sent successfully")
    
    exit(0)

# Read the args, if any
if(len(sys.argv) > 1):
    if(sys.argv[1] == "--test"):
        TEST = True
    else:
        logging.error("Unknown argument: %s", sys.argv[1])

# Log startup, and if we're logging to a file
if(TEST):
    logging.info("Startup *Test mode*")
else:
    logging.info("Startup...")

if(LOG_TO_FILE):
    logging.info("Logging to file")
else:
    logging.info("Logging to console")

# Read config
logging.info("Reading config")

# Check that the config file exists
if not os.path.exists(CFG_PATH):
    logging.error("Config file does not exist, creating a new one")
    with open(CFG_PATH, "w") as f:
        f.write(json.dumps(default_config, indent=4))

# Read the config file
with open(CFG_PATH, "r") as f:
    CONFIG = json.load(f)

# If we're logging to a file, delete log files older than 30 days
if(LOG_TO_FILE):
    logging.info("Deleting log files older than 30 days")
    for file in os.listdir("logs"):
        file_path = os.path.join("logs", file)
        file_name = os.path.basename(file_path)
        if (datetime.datetime.now() - datetime.datetime.strptime(file_name, "%Y-%m-%d.txt")).days > CONFIG.get("log_file_retention_days", 30):
            logging.info("Deleting old log file: %s", file_path)
            os.remove(file_path)

# From https://shallowsky.com/blog/programming/cpu-hogs-in-python.html, 
# we need to run the process twice, with a delay in between, to get accurate CPU usage
# read the delay from the config, default to 5 seconds

logging.info("First CPU usage check")
for proc in psutil.process_iter():
    proc.cpu_percent(None)

# Get the delay from the config, default to 5 seconds
delay = CONFIG.get("delay_secs", 5)
logging.info("Sleeping for %s seconds", delay)
time.sleep(delay)

# Get a list of all processes, for realsies this time
logging.info("Getting processes")
processes = []

for process in psutil.process_iter():
    try:
        # Get process information
        process_info = process.as_dict(attrs=['pid', 'cpu_percent','name', 'username', 'status', 'memory_percent', 'exe'])

        # Check if the process is just a system idle process, and skip it if it is
        if(process_info.get('name') == "System Idle Process"):
            continue

        # Add the process information to the list
        processes.append(process_info)
    except psutil.NoSuchProcess:
        pass

logging.info("Got " + str(len(processes)) + " processes")

# Filter this to only include processes that are using lots of CPU
threshold = CONFIG.get("cpu_threshold", 80.0)
heavy_processes = []
for proc in processes:
    if proc.get('cpu_percent') > threshold:
        heavy_processes.append(proc)

logging.info("Found " + str(len(heavy_processes)) + " heavy processes")

# If there are no heavy processes, we don't need to do anything
if len(heavy_processes) == 0:
    logging.info("No heavy processes found, exiting...")
    exit()

logging.warning("Heavy processes found!")

# Heavy processes found, send a notification
logging.info("Sending notification")

# Create the message
"""
# Message format:
Heavy processes found!

#[Process Name]
exe: [Executable]
*CPU Usage: [CPU Usage]*%
Memory Usage: [Memory Usage]
pid: [PID]
status: [Status]
username: [Username]
"""

message = "Heavy processes found!\n\n"

logging.warning("List of heavy processes:")
for proc in heavy_processes:
    message += "# " + proc.get('name') + "\n"
    message += "*CPU Usage: " + str(proc.get('cpu_percent')) + "*%\n"
    message += "exe: " + str(proc.get('exe')) + "\n"
    message += "Memory Usage: " + str(proc.get('memory_percent')) + "\n"
    message += "pid: " + str(proc.get('pid')) + "\n"
    message += "status: " + str(proc.get('status')) + "\n"
    message += "username: " + str(proc.get('username')) + "\n\n"

    # Also log the process, but just dump the dictionary
    logging.warning(proc)

# Send the message
logging.info("Sending message to Discord")

# Read the webhook URL and username from the config
webhook_url = CONFIG.get("webhook_url")
webhook_username = CONFIG.get("webhook_name")

# Create the data to send
data = {
    "content": message,
    "username": webhook_username
}

# Send the message
logging.info("Sending message to Discord, URL: %s", webhook_url)
if(TEST):
    logging.info("Test mode, not sending message")
    res = requests.Response()
    res.status_code = 204
else:
    logging.info("Sending message...")
    res = requests.post(webhook_url, json=data)
logging.info("Message sent")

if(res.status_code != 204):
    # Log the error and send a panic message. Hopefully the panic message will be sent successfully
    logging.error("Error sending message. Status Code: %s, Message: %s", res.status_code, res.text)
    panic("Error sending message. Status Code: " + str(res.status_code) + ", Message: " + str(res.text))
elif(res.status_code == 200):
    logging.info("Message maybe sent successfully")
elif(res.status_code == 204):
    logging.info("Message sent successfully")

# Log shutdown
logging.info("Shutdown")

# Get the current date, get the log file name, and print a newline to the log file, to separate logs
current_date = datetime.datetime.now().strftime("%Y-%m-%d")
with open(os.path.join("logs", str(current_date + ".txt")), "a") as f:
    f.write("\n")