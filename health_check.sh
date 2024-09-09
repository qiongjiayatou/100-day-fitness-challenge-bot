#!/bin/bash

# Email for alerts
ALERT_EMAIL="qiongjiayatou@gmail.com"

# Get unhealthy containers
UNHEALTHY=$(docker ps --filter "health=unhealthy" --format "{{.Names}}")

# If there are unhealthy containers, send an alert
if [ ! -z "$UNHEALTHY" ]; then
    echo "Unhealthy Containers Found: $UNHEALTHY" | mail -s "Docker Health Alert" "$ALERT_EMAIL"
fi

# Log the health check result
echo "Health Check Report - $(date)" >> /var/log/docker_health_report.log
docker ps --filter "health=unhealthy" --format "Container: {{.Names}} Status: {{.Status}}" >> /var/log/docker_health_report.log
echo "----------------------------------------" >> /var/log/docker_health_report.log
