# Chess Game Review

A Flask-based web server for analyzing chess games using the Stockfish engine.

## Features

- Analyzes PGNs move by move.
- Provides move classifications (Brilliant, Blunder, etc.).
- Calculates accuracy and estimated performance rating.
- Offers natural language explanations for moves.

## Prerequisites

- **Python 3.7+**
- **Stockfish chess engine:** You must have Stockfish installed and accessible in your system's PATH, or provide the path to the Stockfish executable via the `STOCKFISH_PATH` environment variable.
  - Download Stockfish from [stockfishchess.org](https://stockfishchess.org/download/).
  - Example:
    ```bash
    export STOCKFISH_PATH="/usr/local/bin/stockfish"
    ```
    or
    ```bash
    export STOCKFISH_PATH="C:/path/to/stockfish.exe"
    ```

## Installation

Install the package from PyPI:

```bash
pip install chess-game-review 
```

Or, for development, clone this repository and install in editable mode:

```bash
git clone https://github.com/bhatganeshdarshan/chess-game-review.git
cd chess-game-review
pip install -e .
```

## Usage

### Running the Server

Once installed, and with `STOCKFISH_PATH` set (if needed), you can start the server:

```bash
chess-analyzer-server
```

By default, it runs on [http://0.0.0.0:5000](http://0.0.0.0:5000). You can configure this with environment variables:

* `FLASK_HOST`: Host to bind to (default: `0.0.0.0`)
* `FLASK_PORT`: Port to listen on (default: `5000`)
* `FLASK_DEBUG`: Set to true for Flask debug mode (default: `false`)
* `STOCKFISH_PATH`: Path to Stockfish executable (default: `/usr/local/bin/stockfish`)

Example:

```bash
export STOCKFISH_PATH="/path/to/my/stockfish_15_x64"
export FLASK_PORT=8080
chess-analyzer-server
```

### API Endpoint

#### `POST /analyze`

* **Request Body (JSON)**:

  ```json
  {
    "pgn": "1. e4 e5 2. Nf3 ..."
  }
  ```

* **Response**: JSON analysis report.

* **Example with curl**:

  ```bash
  curl -X POST -H "Content-Type: application/json" \
  -d '{"pgn": "1. e4 e5 2. Nf3 Nc6 3. Bb5 a6"}' \
  http://localhost:5000/analyze
  ```

#### `GET /status`

* **Response**: JSON with server and engine status.

## Programmatic Usage 

You can also import and use the analysis function directly:

```python
from chess_analyzer import analyze_game_pgn, initialize_engine, STOCKFISH_PATH
import os

# Ensure STOCKFISH_PATH is set or engine is initialized appropriately
# os.environ["STOCKFISH_PATH"] = "/path/to/stockfish" # if not set globally

engine_instance = initialize_engine()
if not engine_instance:
    print("Failed to initialize engine.")
else:
    pgn_text = "1. e4 e5 2. Nf3 Nc6"
    report, error = analyze_game_pgn(pgn_text)  # analyze_game_pgn expects engine to be initialized
    if error:
        print(f"Error: {error}")
    else:
        print(report["white_summary"])
    
    # Important: If you initialize and use the engine programmatically
    # like this, you are responsible for engine.quit() if you are done with it.
    # The Flask server uses atexit for its global engine instance.
    if engine_instance:
        engine_instance.quit()
```

## Contributing

Pull requests are welcome. For major changes, please open an issue first to discuss what you would like to change.

