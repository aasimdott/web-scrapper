## 🛠️ How You Launch This Ecosystem Local-Style
- To watch this enterprise setup work across independent memory threads right on your own machine without container overhead, fire up these commands:
1. Fire Up the Broker: Ensure your Redis instance is running locally listening on standard port 6379.
2. Start the Worker Cluster: Open a dedicated terminal shell inside the directory and initialize your cluster:
   - `celery -A pipeline_tasks worker --loglevel=info`
3. Fire the Dispatcher Trigger: Open a separate second terminal shell and unleash the pipeline data flow:
   - `python producer.py`
