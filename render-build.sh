#!/usr/bin/env bash
# exit on error
set -o errexit

pip install -r requirements.txt

# Install system dependencies for WeasyPrint
apt-get clean && apt-get update && apt-get install -y libpango-1.0-0 libpangoft2-1.0-0
