#!/bin/bash

# Start cron daemon
sudo service cron start

# Activate conda environment and start the application
conda run -n forecast_service python -m app.main