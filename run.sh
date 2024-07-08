#!/bin/bash

# Activate the virtual environment
source .venv/bin/activate

# Install the dependencies
pip install -r requirements.txt

# Run the script
python main.py

# Deactivate the virtual environment
deactivate
