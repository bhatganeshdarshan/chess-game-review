
from .server import app, initialize_engine, analyze_game_pgn, STOCKFISH_PATH

# version
__version__ = "0.1.0"

# Optionally, to make the server runnable via `python -m chess_analyzer`
# if __name__ == "__main__":
#     from .server import main_cli
#     main_cli()