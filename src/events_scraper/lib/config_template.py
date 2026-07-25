"""Default configuration template for events application."""

DEFAULT_CONFIG = """# Events Application Configuration

# Default group for the main events page (optional, first group auto-detected if unset)
# default_group: ~

# Database configuration
# database:
#   # Database URL - supports SQLite (default is in-memory)
#   # For absolute paths, use 4 slashes: sqlite:////absolute/path/to/file.db
#   # For relative paths, use 3 slashes: sqlite:///relative/path/to/file.db
#   # url: "sqlite:////home/user/.local/share/events.db"  # Absolute path
#   # url: "sqlite:///./events.db"                        # Relative path
#   # url: "/absolute/path/to/events.db"                  # Direct file path
#   # url: ":memory:"                                     # In-memory database (default)

# LLM configuration for AI scraping
# llm:
#   # provider: "claude"       # claude, openai, grok, deepseek
#   # model: "deepseek-chat"   # Optional model override
#   # api_key: "sk-..."        # API key (falls back to env vars: ANTHROPIC_API_KEY, OPENAI_API_KEY, etc.)

# Logging configuration
# logging:
#   # Log level: DEBUG, INFO, WARNING, ERROR, CRITICAL
#   level: "WARNING"
#
#   # Log file path (optional - if not set, logs go to stderr)
#   # Use absolute path or relative to current directory
#   # file: "events.log"
#
#   # Log format (optional)
#   # format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# Event filtering configuration
# filters:
#   # Category filtering
#   categories:
#     # Categories to always include (overrides exclude list)
#     include:
#       - "Music"
#       - "Sports"
#       - "Art"
#     # Categories to exclude from results
#     exclude:
#       - "Market"
#       - "VIP Only"
#
#   # Title-based filtering using regular expressions
#   titles:
#     # Exclude events whose titles match these patterns (case-insensitive)
#     exclude_patterns:
#       - "cancelled"          # Simple substring match
#       - "postponed"          # Another substring match
#       - "\\\\\\\\btest\\\\\\\\b"          # Regex: exact word match for "test"
#       - "(canceled|cancelled)" # Regex: either spelling of canceled
#
#   # Location-based filtering using regular expressions
#   locations:
#     # Exclude events whose locations match these patterns (case-insensitive)
#     exclude_patterns:
#       - "online"            # Simple substring match
#       - "world.*web"        # Regex: "world" followed by anything, then "web"
#       - "remote"            # Another substring match
#
#   # Per-group filter overrides
#   # Filters can be overridden per group. Global + group filters are merged (union).
#   by_group:
#     paris:
#       categories:
#         exclude: ["Special Event"]
#       locations:
#         exclude_patterns:
#           - "outside city"
#     lyon:
#       categories:
#         exclude: ["Local Only"]
#
#   # Per-scraper filter overrides
#   # Global + group + scraper filters are merged (union).
#   by_scraper:
#     opera_scraper:
#       locations:
#         exclude_patterns:
#           - "closed for renovation"
#     museum_scraper:
#       categories:
#         exclude: ["Drama"]

# Regex Pattern Examples:
# - "^word"           : Starts with "word"
# - "word$"           : Ends with "word"
# - "\\\\\\\\bword\\\\\\\\b"        : Exact word match (word boundaries)
# - "(word1|word2)"   : Either word1 OR word2
# - "word.*another"   : "word" followed by anything, then "another"
# - "[0-9]+"          : One or more digits
# - "\\\\\\\\d{4}"          : Exactly 4 digits (year format)
# - "(?i)CasE"        : Case-insensitive match (alternative to default)

# TUI interface configuration removed - TUI was dropped

# Notification delivery via plugins
# plugins:
#   notifiers:
#     signal:
#       host: "http://localhost"  # Signal API host (default: localhost)
#       port: 29328               # Signal API port (default: 29328)
#       sender: "+1234567890"     # Sender phone number for Signal messages

# Notes:
# - All patterns are case-insensitive by default
# - Use double backslashes (\\\\\\\\) to escape special regex characters
# - Simple substrings work without regex syntax
# - Include patterns take precedence over exclude patterns
# - CLI arguments override config file settings
"""
