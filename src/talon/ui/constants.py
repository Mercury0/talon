"""UI constants and help text."""

ROOT_HELP_DISCONNECTED = (
    "Available commands (type help <topic>):\n"
    "========================================\n"
    "exit  help  keys  connect"
)

ROOT_HELP_CONNECTED = (
    "Available commands (type help <topic>):\n"
    "========================================\n"
    "exit  help  keys  config  run  stats"
)

KEYS_HELP = (
    "Available commands (type help <topic>):\n"
    "========================================\n"
    "back  create  help  list  remove"
)

CONFIG_HELP = (
    "Available commands (type help <topic>):\n"
    "========================================\n"
    "back  help  polling  output  logging  filter"
)

HELP_TOPICS = {
    "create": "create a new connection to Falcon API",
}
