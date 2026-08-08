## 🛠️ How You Launch This Ecosystem Local-Style
- To watch this enterprise setup work across independent memory threads right on your own machine without container overhead, fire up these commands:
1. Fire Up the Broker: Ensure your Redis instance is running locally listening on standard port 6379.
2. Make `runner.sh` executable and install requirements
  - `pip install -r requirements.txt`
  - `chmod +x runner.py`
3. Start runner
  - `./runner.sh`
