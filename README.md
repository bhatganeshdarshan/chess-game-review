
# Chess Game Review

[![PyPI version](https://badge.fury.io/py/chess-game-review.svg)](https://badge.fury.io/py/chess-game-review)


A Flask-based web server designed for in-depth analysis of chess games using the powerful Stockfish chess engine. This tool helps players understand their games better by providing move-by-move feedback, identifying critical moments, and offering insights into tactical opportunities and errors.

## Table of Contents

1.  [Key Features](#key-features)
2.  [How it Works](#how-it-works)
3.  [Prerequisites](#prerequisites)
4.  [Installation](#installation)
5.  [Usage](#usage)
    *   [Running the Server](#running-the-server)
    *   [Configuration (Environment Variables)](#configuration-environment-variables)
6.  [API Endpoints](#api-endpoints)
    *   [`POST /analyze`](#post-analyze)
        *   [Request](#request)
        *   [Successful Response Structure](#successful-response-structure)
        *   [Sample Successful Response](#sample-successful-response)
        *   [Error Response](#error-response)
    *   [`GET /status`](#get-status)
7.  [Understanding the Analysis Output](#understanding-the-analysis-output)
    *   [Overall Game Summary](#overall-game-summary)
    *   [Move-by-Move Analysis Details](#move-by-move-analysis-details)
    *   [Move Classifications](#move-classifications)
    *   [Key Metrics Explained](#key-metrics-explained)
8.  [Programmatic Usage (Python)](#programmatic-usage-python)
9.  [Troubleshooting](#troubleshooting)
10. [Contributing](#contributing)
11. [License](#license)

## Key Features

*   **PGN Analysis:** Accepts chess games in Portable Game Notation (PGN) format.
*   **Move-by-Move Evaluation:** Utilizes Stockfish to evaluate each move played and identify the best possible continuations.
*   **Centipawn Loss Calculation:** Quantifies the suboptimality of each move.
*   **Move Classification:** Categorizes moves into intuitive classes:
    *   `Book`: Standard opening moves.
    *   `Brilliant` (!!): Excellent, often sacrificial, moves that are hard to find.
    *   `Great Move` (!): Very strong moves, close to the engine's top choice.
    *   `Best Move`: The engine's top recommended move.
    *   `Good`: Solid moves that maintain the position's quality.
    *   `Inaccuracy` (?!): Suboptimal moves that slightly worsen the position.
    *   `Mistake` (?): Significant errors that lead to a tangible disadvantage.
    *   `Blunder` (??): Very serious errors, often losing material or the game.
*   **Natural Language Explanations:** Provides human-readable insights for each move, especially for mistakes and blunders, explaining why a move was good or bad and suggesting alternatives.
*   **Accuracy Score:** Calculates an overall accuracy percentage for both White and Black.
*   **Average Centipawn Loss (ACPL):** A key metric for evaluating performance.
*   **Estimated Game Performance Rating (GPR):** Provides an estimated Elo-like rating based on ACPL.
*   **Principal Variation (PV):** Shows the engine's anticipated best line of play.
*   **FEN Before & After:** Includes the Forsyth-Edwards Notation (FEN) for the board state before and after each move.

## How it Works

The server takes a PGN string as input. For each move in the game:
1.  It sets up the board position *before* the move.
2.  It asks Stockfish to analyze this position to find the best move and its evaluation.
3.  It then plays the actual move from the PGN.
4.  It asks Stockfish to analyze the position *after* the player's move.
5.  The difference in evaluation between the best possible play (from step 2) and the actual play's outcome (from step 4) is the "centipawn loss" for that move.
6.  Based on this loss and other heuristics (like sacrifices), the move is classified.
7.  An explanation is generated, highlighting tactical reasons, missed opportunities, or consequences of the move.
8.  Aggregate statistics (accuracy, ACPL, GPR) are computed for both players.

## Prerequisites

*   **Python 3.7+**: Ensure you have a compatible Python version installed.
*   **Stockfish Chess Engine**:
    *   You must have the Stockfish executable installed on your system.
    *   Download the latest version from [stockfishchess.org/download/](https://stockfishchess.org/download/).
    *   The server needs to know the path to this executable. You can either:
        1.  Add the directory containing `stockfish` (or `stockfish.exe`) to your system's `PATH` environment variable.
        2.  Set the `STOCKFISH_PATH` environment variable directly to the executable's full path.

    **Examples for `STOCKFISH_PATH`**:
    *   Linux/macOS: `export STOCKFISH_PATH="/usr/local/bin/stockfish"` or `export STOCKFISH_PATH="/path/to/your/downloaded/stockfish"`
    *   Windows: `set STOCKFISH_PATH="C:\Program Files\Stockfish\stockfish.exe"` or `set STOCKFISH_PATH="C:\path\to\your\downloaded\stockfish.exe"`

## Installation

1.  **Install from PyPI (Recommended):**
    ```bash
    pip install chess-game-review
    ```

2.  **For Development (from source):**
    ```bash
    git clone https://github.com/bhatganeshdarshan/chess-game-review.git
    cd chess-game-review
    pip install -e .
    ```
    This installs the package in "editable" mode, so changes to the source code are immediately reflected.

## Usage

### Running the Server

After installation and ensuring Stockfish is accessible (see [Prerequisites](#prerequisites)):

```bash
chess-analyzer-server
```


The server will typically start on `http://0.0.0.0:5000`.

### Configuration (Environment Variables)

You can customize the server's behavior using these environment variables:

*   `STOCKFISH_PATH`: Full path to the Stockfish executable.
    *   Default: `/usr/local/bin/stockfish` (common on Linux/macOS if installed via package manager)
*   `FLASK_HOST`: The host interface the server binds to.
    *   Default: `0.0.0.0` (listens on all available network interfaces)
*   `FLASK_PORT`: The port the server listens on.
    *   Default: `5000`
*   `FLASK_DEBUG`: Set to `true` to enable Flask's debug mode (provides more detailed error messages, auto-reloads on code changes).
    *   Default: `false`
*   `ANALYSIS_TIME_LIMIT_PER_MOVE`: Time in seconds Stockfish spends analyzing each half-move. Higher values yield stronger analysis but take longer.
    *   Default: `0.3`
*   `MAX_PV_DEPTH_FOR_EXPLANATION`: How many moves deep the Principal Variation (PV) is shown in explanations.
    *   Default: `3`

**Example:**
```bash
export STOCKFISH_PATH="/opt/stockfish/stockfish_15_x64_avx2"
export FLASK_PORT=8080
export FLASK_DEBUG=true
chess-analyzer-server
```

## API Endpoints

### `POST /analyze`

Analyzes the provided PGN chess game.

#### Request

*   **Method:** `POST`
*   **Headers:** `Content-Type: application/json`
*   **Body (JSON):**
    ```json
    {
      "pgn": "1. e4 e5 2. Nf3 Nc6 3. Bb5 a6 4. Ba4 Nf6 5. O-O Be7 6. Re1 b5 7. Bb3 d6 8. c3 O-O 9. h3 Nb8 10. d4 Nbd7 *"
    }
    ```
    *   `pgn` (string, required): The PGN content of the chess game.

#### Successful Response Structure

*   **Status Code:** `200 OK`
*   **Body (JSON):**
    ```json
    {
        "white_summary": {
            "accuracy_percent": Number,
            "average_centipawn_loss": Number,
            "game_performance_rating_estimate": Integer,
            "move_counts": {
                "Brilliant": Integer,
                "Great": Integer,
                "Best Move": Integer,
                "Good": Integer,
                "Inaccuracy": Integer,
                "Mistake": Integer,
                "Blunder": Integer,
                "Book": Integer
            }
        },
        "black_summary": { /* Same structure as white_summary */ },
        "move_by_move_analysis": [
            {
                "ply": Integer, // Move number (half-moves)
                "fen_before_move": "String (FEN)",
                "fen_after_move": "String (FEN)",
                "move_san": "String (e.g., e4, Nf3)",
                "player": "White" | "Black",
                "classification": "String (e.g., Best Move, Blunder)",
                "eval_drop_cp": Integer, // Centipawn loss for this move
                "best_move_engine_san": "String (e.g., d4)", // Engine's best move in this position
                "explanation": "String (Natural language explanation)",
                "eval_if_best_played_cp": Integer, // Evaluation (pov) if best move was played
                "eval_after_player_move_cp": Integer // Evaluation (pov) after player's actual move
            },
            // ... more moves
        ],
        "initial_fen": "String (FEN of the starting position of the game)"
    }
    ```

#### Sample Successful Response

(Shortened for brevity)
```json
{
    "white_summary": {
        "accuracy_percent": 85.2,
        "average_centipawn_loss": 35.5,
        "game_performance_rating_estimate": 1950,
        "move_counts": {
            "Brilliant": 0,
            "Great": 1,
            "Best Move": 5,
            "Good": 3,
            "Inaccuracy": 1,
            "Mistake": 0,
            "Blunder": 0,
            "Book": 3
        }
    },
    "black_summary": {
        "accuracy_percent": 70.1,
        "average_centipawn_loss": 65.8,
        "game_performance_rating_estimate": 1600,
        "move_counts": {
            "Brilliant": 0,
            "Great": 0,
            "Best Move": 3,
            "Good": 2,
            "Inaccuracy": 1,
            "Mistake": 1,
            "Blunder": 1,
            "Book": 3
        }
    },
    "move_by_move_analysis": [
        {
            "ply": 1,
            "fen_before_move": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
            "fen_after_move": "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1",
            "move_san": "e4",
            "player": "White",
            "classification": "Book",
            "eval_drop_cp": 0,
            "best_move_engine_san": "e4",
            "explanation": "Book move. e4 is a standard opening move. This move is well-known in opening theory for this position.",
            "eval_if_best_played_cp": 30,
            "eval_after_player_move_cp": 30
        },
        {
            "ply": 2,
            "fen_before_move": "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1",
            "fen_after_move": "rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq e6 0 2",
            "move_san": "e5",
            "player": "Black",
            "classification": "Book",
            "eval_drop_cp": 0,
            "best_move_engine_san": "e5",
            "explanation": "Book move. e5 is a standard opening move. This move is well-known in opening theory for this position.",
            "eval_if_best_played_cp": -30,
            "eval_after_player_move_cp": -30
        },
        // ... more moves ...
        {
            "ply": 15,
            "fen_before_move": "r1bqk2r/pp1n1ppp/2pbpn2/3p4/2PP4/1PNBPN2/P4PPP/R1BQK2R w KQkq - 1 8",
            "fen_after_move": "r1bqk2r/pp1n1ppp/2pbpn2/3p4/2PP4/1PNBPN2/P2B1PPP/R2QK2R b KQkq - 2 8",
            "move_san": "Bd2",
            "player": "White",
            "classification": "Inaccuracy",
            "eval_drop_cp": 55,
            "best_move_engine_san": "O-O",
            "explanation": "Inaccuracy. Bd2 is a suboptimal choice. This move concedes about 0.55 pawns in evaluation compared to the best option. Consider O-O instead. It might have offered a slightly more favorable middlegame structure. A possible line: O-O Qe7. Your move allows the opponent to improve their position with e5.",
            "eval_if_best_played_cp": 45,
            "eval_after_player_move_cp": -10
        },
        {
            "ply": 16,
            "fen_before_move": "r1bqk2r/pp1n1ppp/2pbpn2/3p4/2PP4/1PNBPN2/P2B1PPP/R2QK2R b KQkq - 2 8",
            "fen_after_move": "r1bqk2r/pp1n1ppp/2pbpn2/3p2B1/2PP4/1PNBPN2/P4PPP/R2QK2R w KQkq - 3 9",
            "move_san": "Bg5",
            "player": "Black",
            "classification": "Blunder",
            "eval_drop_cp": 250,
            "best_move_engine_san": "O-O",
            "explanation": "Blunder! Bg5 is a serious error. It allows Nxe5, capturing your undefended pawn on e5. The position significantly deteriorates to an evaluation of +2.40. The best move was O-O, which aimed for an evaluation of +0.10 with the line: O-O Re8. Your move Bg5 changes the evaluation to -2.40. The opponent can exploit this with: Nxe5.",
            "eval_if_best_played_cp": 10,
            "eval_after_player_move_cp": -240
        }
    ],
    "initial_fen": "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
}
```

#### Error Response

*   **Status Code:** `400 Bad Request` (e.g., missing PGN, invalid PGN format) or `500 Internal Server Error` (e.g., engine issues).
*   **Body (JSON):**
    ```json
    {
      "error": "Descriptive error message"
    }
    ```
    Example:
    ```json
    {
      "error": "Missing 'pgn' in JSON request body"
    }
    ```
    or
    ```json
    {
      "error": "CRITICAL: Stockfish engine not found at /usr/local/bin/stockfish. Please set STOCKFISH_PATH."
    }
    ```

### `GET /status`

Checks the status of the server and the chess engine.

*   **Method:** `GET`
*   **Successful Response (JSON):**
    ```json
    {
      "status": "ok",
      "engine_status": "running",
      "engine_name": "Stockfish 15 AVX2" // Or whatever your engine reports
    }
    ```
*   **Error Response (JSON):**
    ```json
    {
      "status": "error",
      "engine_status": "not_initialized" // Or "error_pinging"
    }
    ```

## Understanding the Analysis Output

### Overall Game Summary (`white_summary`, `black_summary`)

*   `accuracy_percent`: An overall percentage score (0-100) representing how closely the player's moves matched the engine's top choices. Higher is better.
*   `average_centipawn_loss` (ACPL): The average number of centipawns (1/100th of a pawn) lost per move compared to the engine's best move. Lower is better.
*   `game_performance_rating_estimate` (GPR): An estimated Elo-like rating for the player's performance in this specific game, derived from ACPL.
*   `move_counts`: A breakdown of how many moves fell into each classification (Brilliant, Blunder, etc.).

### Move-by-Move Analysis Details (`move_by_move_analysis` array)

Each object in this array represents one half-move in the game:
*   `ply`: The number of half-moves into the game. Ply 1 is White's first move, Ply 2 is Black's first move, etc.
*   `fen_before_move`: The FEN string representing the board state *before* the current move was made.
*   `fen_after_move`: The FEN string representing the board state *after* the current move was made.
*   `move_san`: The player's move in Standard Algebraic Notation (e.g., "Nf3", "O-O", "e8=Q").
*   `player`: The color of the player who made the move ("White" or "Black").
*   `classification`: The category of the move (see [Move Classifications](#move-classifications)).
*   `eval_drop_cp`: The centipawn loss for this specific move. A positive value means the move was worse than the engine's best. 0 means it was the best or very close.
*   `best_move_engine_san`: The engine's recommended best move in the position *before* the player's move was made.
*   `explanation`: A natural language text explaining the quality of the move, potential alternatives, and consequences. This is most detailed for significant errors.
*   `eval_if_best_played_cp`: The engine's evaluation of the position (from the current player's perspective, in centipawns) if the `best_move_engine_san` had been played. Positive values favor the current player. Mate scores are represented by large numbers (e.g., +10000 for mate, -10000 for being mated).
*   `eval_after_player_move_cp`: The engine's evaluation of the position (from the current player's perspective) *after* their `move_san` was played.

### Move Classifications

*   **Book:** Standard, well-known opening moves.
*   **Brilliant (!!):** An exceptional, often sacrificial, move that is the best or nearly the best, and difficult for humans to find. Usually involves a temporary material loss for a significant positional or tactical gain.
*   **Great Move (!):** A very strong move, among the engine's top choices, that significantly improves the position.
*   **Best Move:** The move considered optimal by the engine.
*   **Good:** A solid, sensible move that maintains the quality of the position, even if not the absolute best.
*   **Inaccuracy (?!):** A move that is suboptimal and slightly weakens the position or misses a better opportunity. The centipawn loss is noticeable but not critical.
*   **Mistake (?):** A significant error that leads to a tangible disadvantage, such as loss of material, a severely compromised position, or missing a clear win.
*   **Blunder (??):** A very serious error that drastically worsens the position, often leading to immediate material loss, a lost game, or missing a forced mate.

### Key Metrics Explained

*   **Centipawn (cp):** The standard unit of chess advantage, equal to 1/100th of a pawn. An evaluation of +100 cp means White is up by the equivalent of one pawn.
*   **Average Centipawn Loss (ACPL):** The average number of centipawns a player lost per move compared to the engine's best choice. A lower ACPL indicates stronger play. GM-level play often has ACPL below 20-30.
*   **Accuracy:** A percentage (0-100%) derived from ACPL, providing a more intuitive measure of how "accurately" a player played according to the engine.
*   **Game Performance Rating (GPR):** An estimated Elo rating based on the player's ACPL for that single game. This can fluctuate significantly from game to game.

## Programmatic Usage (Python)

You can also use the core analysis functionality directly within your Python scripts.

```python
from chess_analyzer import analyze_game_pgn, initialize_engine
import os

# --- Option 1: Set STOCKFISH_PATH environment variable ---
# os.environ["STOCKFISH_PATH"] = "/path/to/your/stockfish_executable"

# --- Option 2: Ensure the path is discoverable or use the default ---
# (The initialize_engine function will use chess_analyzer.server.STOCKFISH_PATH)

# Initialize the engine (this is a global engine instance used by analyze_game_pgn)
# It's important to call this before analyze_game_pgn if not running the Flask server.
engine_instance = initialize_engine()

if not engine_instance:
    print("Failed to initialize Stockfish engine. Check STOCKFISH_PATH.")
else:
    pgn_text = "1. e4 e5 2. Nf3 Nc6 3. Bb5 a6 4. O-O Nf6 *" # Example PGN
    
    print(f"Analyzing PGN: {pgn_text}")
    analysis_report, error_message = analyze_game_pgn(pgn_text)

    if error_message:
        print(f"Analysis Error: {error_message}")
    elif analysis_report:
        print("\n--- White's Summary ---")
        print(f"Accuracy: {analysis_report['white_summary']['accuracy_percent']}%")
        print(f"ACPL: {analysis_report['white_summary']['average_centipawn_loss']}")
        print(f"GPR Estimate: {analysis_report['white_summary']['game_performance_rating_estimate']}")
        print("Move Counts:", analysis_report['white_summary']['move_counts'])

        print("\n--- First few moves analysis ---")
        for i, move_analysis in enumerate(analysis_report['move_by_move_analysis']):
            if i >= 3: # Print details for first 3 half-moves
                break
            print(f"\nPly {move_analysis['ply']}: {move_analysis['player']}'s move {move_analysis['move_san']}")
            print(f"  Classification: {move_analysis['classification']}")
            print(f"  Centipawn Loss: {move_analysis['eval_drop_cp']}")
            print(f"  Engine's Best: {move_analysis['best_move_engine_san']}")
            print(f"  Explanation: {move_analysis['explanation'][:100]}...") # Truncate long explanations
    else:
        print("Analysis returned no report and no error.")

    # When using programmatically and managing the engine instance directly,
    # you would typically quit it when done.
    # However, analyze_game_pgn uses a global engine instance which is
    # managed by initialize_engine and (if the server runs) by atexit.
    # If you are *only* using it programmatically and want to ensure cleanup:
    if engine_instance:
        try:
            print("\nQuitting engine programmatically...")
            engine_instance.quit()
        except Exception as e:
            print(f"Error quitting engine: {e}")
```
**Note on Programmatic Usage:** The `analyze_game_pgn` function relies on a global `engine` instance that `initialize_engine` sets up. If you run this script multiple times without restarting the Python process, `initialize_engine` will reuse the existing engine. The Flask server handles `engine.quit()` on exit using `atexit`. If you're *only* using it programmatically, you might want more direct control over the engine lifecycle for repeated analyses.

## Troubleshooting

*   **"Stockfish engine not found" / "Engine terminated" / "Engine not initialized":**
    *   Ensure Stockfish is installed correctly.
    *   Verify that the `STOCKFISH_PATH` environment variable is set correctly to the *full path of the Stockfish executable*, or that the executable is in your system's `PATH`.
    *   Check file permissions for the Stockfish executable. It must be runnable by the user starting the server.
*   **Slow Analysis:**
    *   The `ANALYSIS_TIME_LIMIT_PER_MOVE` (default 0.3s) dictates analysis speed. For deeper analysis, increase this value, but be aware it will significantly increase total analysis time for a game.
    *   Ensure your machine is not under heavy load from other processes.
*   **Invalid PGN:**
    *   The server expects valid PGN. Errors in PGN format can cause parsing failures. Validate your PGN using an external tool if you encounter issues.

## Contributing

Pull requests are welcome! For major changes or new features, please open an issue first to discuss what you would like to change or add.

1.  Fork the repository.
2.  Create your feature branch (`git checkout -b feature/AmazingFeature`).
3.  Commit your changes (`git commit -m 'Add some AmazingFeature'`).
4.  Push to the branch (`git push origin feature/AmazingFeature`).
5.  Open a Pull Request.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
