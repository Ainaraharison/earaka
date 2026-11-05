#!/bin/bash
cd /var/services/homes/arthur/webapppy
export PORT=7777
while true; do
    /usr/bin/python3 webapp.py >> app.log 2>&1
    echo "$(date) - webapp.py arrêté, redémarrage dans 5s..." >> app.log
    sleep 5
done
