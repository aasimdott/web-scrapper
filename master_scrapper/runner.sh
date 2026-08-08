#!/usr/bin/bash
python -m celery -A pipeline_tasks worker --loglevel=info &
CELERY_PID=$!
trap "echo 'Stoping worker...'; kill $CELERY_PID" EXIT
sleep 3
python producer.py