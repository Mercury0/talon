"""UI constants and help text."""

ROOT_HELP_DISCONNECTED = (
    "Available commands (type help <topic>):\n"
    "========================================\n"
    "exit  help  keys  connect  detail  db"
)

ROOT_HELP_CONNECTED = (
    "Available commands (type help <topic>):\n"
    "========================================\n"
    "exit  help  keys  config  run  stats  detail  db"
)

KEYS_HELP = (
    "Available commands (type help <topic>):\n"
    "========================================\n"
    "back  create  help  list  remove"
)

CONFIG_HELP = (
    "Available commands (type help <topic>):\n"
    "========================================\n"
    "back  help  polling  filter  lookback"
)

# Add a new help constant for the db submenu:
DB_HELP = (
    "Available commands (type help <topic>):\n"
    "========================================\n"
    "back  help  detections  purge  export"
)

HELP_TOPICS = {
    "create": "create a new Falcon API connection",
    "list": "list saved Falcon API connection profiles",
    "remove": "delete existing Falcon API connection profile",
    "detail": "query stored alerts from database for detailed information (usage: detail or detail <alert_id>)",
    "stats": "display alert statistics and volume metrics",
    "run": "start monitoring alerts without re-authenticating",
    "config": "configure settings like polling interval and filters",
    "keys": "set up initial connection to Falcon API or use saved profile",
    "connect": "connect to Falcon API",
    "db": "database management for stored alerts and detections",
    "detections": "view stored detections from database",
    "purge": "clear all stored detections from database",
    "export": "export stored detections to CSV or JSON format",
    "polling": "set polling interval for incoming detections in seconds",
    "filter": "configure alert filtering by severity, product, hostname, etc.",
    "lookback": "set lookback range for prior alerts (default: 10 minutes)",
}
