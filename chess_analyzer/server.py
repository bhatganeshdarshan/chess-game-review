from flask import Flask, request, jsonify
import chess
import chess.pgn
import chess.engine
import io
import math
import os
from flask_cors import CORS

# --- Configuration ---
STOCKFISH_PATH = os.environ.get("STOCKFISH_PATH", "/usr/local/bin/stockfish")
ANALYSIS_TIME_LIMIT_PER_MOVE = 0.3
MAX_PV_DEPTH_FOR_EXPLANATION = 3 # How many moves deep to show in explanations
MAX_CENTIPAWN_LOSS_PER_MOVE = 700

BRILLIANT_MOVE_MAX_DROP = 5
GREAT_MOVE_MAX_DROP = 20
BEST_MOVE_MAX_DROP = 10
GOOD_MOVE_MAX_DROP = 40
INACCURACY_THRESHOLD_MIN_DROP = 41
MISTAKE_THRESHOLD_MIN_DROP = 90
BLUNDER_THRESHOLD_MIN_DROP = 200

app = Flask(__name__)
CORS(app)
engine = None

# --- Engine Initialization ---
def initialize_engine():
    global engine
    if engine is None:
        try:
            engine = chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH)
            app.logger.info(f"Stockfish engine initialized from: {STOCKFISH_PATH}")
        except FileNotFoundError:
            app.logger.error(f"CRITICAL: Stockfish engine not found at {STOCKFISH_PATH}. Please set STOCKFISH_PATH.")
            engine = None
        except Exception as e:
            app.logger.error(f"CRITICAL: Error initializing Stockfish: {e}")
            engine = None
    return engine

# --- Helper Functions ---
def get_material_value(piece_symbol):
    piece_symbol = piece_symbol.lower()
    if piece_symbol == 'p': return 1
    if piece_symbol == 'n': return 3
    if piece_symbol == 'b': return 3
    if piece_symbol == 'r': return 5
    if piece_symbol == 'q': return 9
    return 0

def get_board_material_balance(board_obj, for_color):
    balance = 0
    for piece_type in [chess.PAWN, chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN]:
        balance += len(board_obj.pieces(piece_type, for_color)) * get_material_value(chess.piece_symbol(piece_type))
        balance -= len(board_obj.pieces(piece_type, not for_color)) * get_material_value(chess.piece_symbol(piece_type))
    return balance



def get_piece_name(piece_type_or_symbol):
    if isinstance(piece_type_or_symbol, str):
        symbol = piece_type_or_symbol.lower()
        if symbol == 'p': return "pawn"
        if symbol == 'n': return "knight"
        if symbol == 'b': return "bishop"
        if symbol == 'r': return "rook"
        if symbol == 'q': return "queen"
        if symbol == 'k': return "king"
    elif isinstance(piece_type_or_symbol, int): # chess.PieceType
        if piece_type_or_symbol == chess.PAWN: return "pawn"
        if piece_type_or_symbol == chess.KNIGHT: return "knight"
        if piece_type_or_symbol == chess.BISHOP: return "bishop"
        if piece_type_or_symbol == chess.ROOK: return "rook"
        if piece_type_or_symbol == chess.QUEEN: return "queen"
        if piece_type_or_symbol == chess.KING: return "king"
    return "piece"

def format_score(cp_score, pov_color_is_white): # pov_color can be True for white, False for black
    # (Keep your existing implementation or use this)
    if cp_score is None: return "N/A"
    # Mate scores from engine are typically very large (e.g. +/- (10000 - N))
    # pov_color_is_white is True if the cp_score is from White's perspective
    # If cp_score itself is already POV, then pov_color_is_white is not strictly needed here.
    # Assuming cp_score is absolute (positive good for white, negative good for black)
    # and current_player_to_move determines POV.

    # Let's assume cp_score is already POV (positive good for current player)
    if abs(cp_score) > 9000: # Heuristic for mate
        mate_in = 10000 - abs(cp_score) + 1
        prefix = "#"
        if cp_score < 0: # Mate against POV player
            return f"{prefix}-{mate_in}"
        else: # Mate for POV player
            return f"{prefix}{mate_in}"
    return f"{cp_score / 100.0:+.2f}" # Add + for positive scores

def describe_line(board_start_fen, moves_pv, limit=MAX_PV_DEPTH_FOR_EXPLANATION, include_move_numbers=False):
    if not moves_pv: return ""
    line_parts = []
    temp_board = chess.Board(board_start_fen)
    current_move_number = temp_board.fullmove_number
    is_black_to_move_start = temp_board.turn == chess.BLACK

    try:
        for i, move in enumerate(moves_pv[:limit]):
            if not move: break
            move_str = ""
            if include_move_numbers:
                if temp_board.turn == chess.WHITE:
                    move_str += f"{current_move_number}. "
                elif i == 0 and is_black_to_move_start: # First move in PV is Black's
                     move_str += f"{current_move_number}... "


            try:
                san_move = temp_board.san(move)
                move_str += san_move
                line_parts.append(move_str)
                temp_board.push(move)
                if temp_board.turn == chess.WHITE and not (i == 0 and is_black_to_move_start):
                    current_move_number +=1
            except ValueError:
                line_parts.append(str(move)) # Fallback to UCI
                try: temp_board.push(move)
                except: break
            except Exception as e_san:
                app.logger.warning(f"Error generating SAN in describe_line for {move} on {temp_board.fen()}: {e_san}")
                break # Stop if SAN fails badly
        return " ".join(line_parts)
    except Exception as e_desc:
        app.logger.error(f"Error in describe_line: {e_desc} with FEN {board_start_fen} and PV {moves_pv}")
        return "..."

def get_square_name(square_index):
    return chess.square_name(square_index)

def check_hanging_piece_after_opponent_reply(board_after_player_move_obj, opponent_reply_move_obj):
    """
    Checks if the opponent's reply captures a piece that was "hanging" or poorly defended.
    Returns a string explanation part or None.
    """
    if not board_after_player_move_obj.is_capture(opponent_reply_move_obj):
        return None

    captured_square = opponent_reply_move_obj.to_square
    # Piece that was on `captured_square` BEFORE opponent's reply (it belonged to the player)
    piece_at_target_before_opp_reply = board_after_player_move_obj.piece_at(captured_square)

    if not piece_at_target_before_opp_reply: # e.g. en-passant
        if board_after_player_move_obj.is_en_passant(opponent_reply_move_obj):
            return f"an en-passant capture losing your pawn"
        return None # Should not happen for normal captures

    lost_piece_type = get_piece_name(piece_at_target_before_opp_reply.piece_type)
    lost_piece_value = get_material_value(piece_at_target_before_opp_reply.symbol())

    # Create a board state just before the player made their blunderous move
    # This is complex as we don't have that FEN directly here.
    # Instead, let's analyze the state *after* player's move but *before* opponent's reply.
    attackers_on_target = board_after_player_move_obj.attackers(not board_after_player_move_obj.turn, captured_square)
    defenders_on_target = board_after_player_move_obj.attackers(board_after_player_move_obj.turn, captured_square)

    # Simplistic check: if lost piece value is high and it had few defenders vs attackers
    if lost_piece_value >= 3: # Knight/Bishop or more
        if not defenders_on_target:
            return f"your undefended {lost_piece_type} on {get_square_name(captured_square)}"
        elif len(attackers_on_target) > len(defenders_on_target):
             return f"your insufficiently defended {lost_piece_type} on {get_square_name(captured_square)}"
    elif lost_piece_value >= 1 and not defenders_on_target: # Hanging pawn
        return f"your undefended pawn on {get_square_name(captured_square)}"
    return f"your {lost_piece_type} on {get_square_name(captured_square)}" # Generic loss

# --- THE DETAILED EXPLANATION FUNCTION ---
def get_detailed_explanation(
    original_board_fen, player_actual_move_obj, player_actual_move_san,
    engine_best_move_obj, engine_best_move_san,
    info_for_original_position, info_after_player_actual_move,
    engine_instance, current_player_to_move, classification # current_player_to_move is chess.WHITE or chess.BLACK
):
    explanation_parts = []
    board_before_player_move = chess.Board(original_board_fen)
    player_color_str = "White" if current_player_to_move == chess.WHITE else "Black"
    opponent_color_str = "Black" if current_player_to_move == chess.WHITE else "White"

    # --- Scores from player's POV ---
    score_info_best_raw = info_for_original_position.get("score")
    score_if_best_played_pov = score_info_best_raw.pov(current_player_to_move) if score_info_best_raw else None
    cp_if_best_played = score_if_best_played_pov.score(mate_score=10000) if score_if_best_played_pov else 0

    score_info_actual_raw = info_after_player_actual_move.get("score")
    score_after_player_move_pov = score_info_actual_raw.pov(current_player_to_move) if score_info_actual_raw else None
    cp_after_player_move = score_after_player_move_pov.score(mate_score=10000) if score_after_player_move_pov else 0

    eval_drop_cp = cp_if_best_played - cp_after_player_move if cp_if_best_played is not None and cp_after_player_move is not None else 0

    best_alternative_pv = info_for_original_position.get("pv", [])
    punishment_pv = info_after_player_actual_move.get("pv", [])

    # --- I. CRITICAL ISSUES (Mates) ---
    if score_if_best_played_pov and score_if_best_played_pov.is_mate() and score_if_best_played_pov.mate() > 0:
        mate_in_n = score_if_best_played_pov.mate()
        line_str = describe_line(original_board_fen, best_alternative_pv, limit=mate_in_n*2, include_move_numbers=True)
        explanation_parts.append(
            f"A critical oversight! You missed a forced checkmate in {mate_in_n} moves. "
            f"The winning sequence starts with {engine_best_move_san}: {line_str}."
        )
        if classification in ["Blunder", "Mistake"]: return " ".join(explanation_parts)

    if score_after_player_move_pov and score_after_player_move_pov.is_mate() and score_after_player_move_pov.mate() < 0:
        mate_in_n = abs(score_after_player_move_pov.mate())
        board_after_player_move_temp = board_before_player_move.copy()
        board_after_player_move_temp.push(player_actual_move_obj)
        # Get opponent's first reply for the explanation
        opp_reply_san = "a forced sequence"
        if punishment_pv and punishment_pv[0]:
            try: opp_reply_san = board_after_player_move_temp.san(punishment_pv[0])
            except: pass # Keep default if SAN fails
        line_str = describe_line(board_after_player_move_temp.fen(), punishment_pv, limit=mate_in_n*2, include_move_numbers=True)

        explanation_parts.append(
            f"A disastrous move! {player_actual_move_san} allows {opponent_color_str} to force checkmate in {mate_in_n} moves, "
            f"beginning with {opp_reply_san}. The unavoidable line is: {line_str}."
        )
        return " ".join(explanation_parts)

    # --- II. BLUNDERS & MISTAKES ---
    if classification in ["Blunder", "Mistake"]:
        prefix = f"{classification}! {player_actual_move_san} is a serious error. "
        reason_found = False

        # A. Losing Material
        board_after_player_move = board_before_player_move.copy()
        board_after_player_move.push(player_actual_move_obj) # Player's actual move is made

        if punishment_pv and punishment_pv[0]: # If there's a clear punishing reply from engine
            opponent_reply_move_obj = punishment_pv[0]
            try:
                opponent_reply_san = board_after_player_move.san(opponent_reply_move_obj)
            except Exception:
                opponent_reply_san = str(opponent_reply_move_obj) # Fallback to UCI

            # Check if opponent's reply captures material
            if board_after_player_move.is_capture(opponent_reply_move_obj):
                hanged_piece_desc = check_hanging_piece_after_opponent_reply(board_after_player_move, opponent_reply_move_obj)
                if hanged_piece_desc:
                    explanation_parts.append(
                        f"{prefix}It allows {opponent_reply_san}, capturing {hanged_piece_desc}."
                    )
                    # Further elaborate on the consequences
                    temp_board_after_opp_reply = board_after_player_move.copy()
                    temp_board_after_opp_reply.push(opponent_reply_move_obj)
                    info_after_opp_reply = engine_instance.analyse(temp_board_after_opp_reply, chess.engine.Limit(depth=10)) # Quick check
                    score_after_opp_reply_pov = info_after_opp_reply.get("score").pov(current_player_to_move) if info_after_opp_reply.get("score") else None
                    if score_after_opp_reply_pov:
                        explanation_parts.append(
                            f"The position significantly deteriorates to an evaluation of {format_score(score_after_opp_reply_pov.score(mate_score=10000), current_player_to_move == chess.WHITE)}."
                        )
                    reason_found = True

            # B. Allowing a Fork/Discovered Attack (simplified check based on opponent's reply)
            # This is hard to detect perfectly without deeper tactical search.
            # We can look at the nature of opponent_reply_move_obj if it's not a direct capture.
            # For instance, if opponent_reply_move_obj creates a double attack.
            if not reason_found and not board_after_player_move.is_capture(opponent_reply_move_obj):
                # Check if opponent's move leads to a capture on the *next* move in punishment_pv
                if len(punishment_pv) > 1:
                    board_after_opp_first_reply = board_after_player_move.copy()
                    board_after_opp_first_reply.push(opponent_reply_move_obj) # Opponent's first reply
                    if not board_after_opp_first_reply.is_game_over(): # Ensure game continues
                        player_forced_reply_obj = punishment_pv[1] # Player's expected reply from PV
                        try:
                            board_after_opp_first_reply.push(player_forced_reply_obj) # Player's forced reply
                            if not board_after_opp_first_reply.is_game_over() and len(punishment_pv) > 2:
                                opponent_second_reply_obj = punishment_pv[2] # Opponent's second reply
                                if board_after_opp_first_reply.is_capture(opponent_second_reply_obj):
                                    captured_piece_after_sequence = board_after_opp_first_reply.piece_at(opponent_second_reply_obj.to_square)
                                    if captured_piece_after_sequence:
                                        explanation_parts.append(
                                            f"{prefix}It leads to a tactical sequence starting with {opponent_reply_san}, "
                                            f"where you ultimately lose your {get_piece_name(captured_piece_after_sequence.piece_type)} "
                                            f"after {describe_line(board_after_player_move.fen(), punishment_pv, limit=3)}."
                                        )
                                        reason_found = True
                        except Exception: pass # Sequence might be invalid or game ends

        # C. General Worsening compared to Best Move
        if not reason_found and engine_best_move_san != player_actual_move_san:
            explanation_parts.append(prefix)
            best_line_str = describe_line(original_board_fen, best_alternative_pv, limit=3, include_move_numbers=True)
            eval_best_formatted = format_score(cp_if_best_played, current_player_to_move == chess.WHITE)
            explanation_parts.append(
                f"The best move was {engine_best_move_san}, which aimed for an evaluation of {eval_best_formatted} "
                f"with the line: {best_line_str}."
            )

            eval_actual_formatted = format_score(cp_after_player_move, current_player_to_move == chess.WHITE)
            explanation_parts.append(
                f"Your move {player_actual_move_san} changes the evaluation to {eval_actual_formatted}."
            )
            if punishment_pv and punishment_pv[0]:
                board_after_player_actual_move_fen = board_before_player_move.copy()
                board_after_player_actual_move_fen.push(player_actual_move_obj) # Player's actual move
                punishing_line_str = describe_line(board_after_player_actual_move_fen.fen(), punishment_pv, limit=3, include_move_numbers=True)
                explanation_parts.append(
                    f"The opponent can exploit this with: {punishing_line_str}."
                )
            else:
                explanation_parts.append("This significantly weakens your position without immediate tactical loss shown in the top line.")
        elif not reason_found: # Should not happen if it's a blunder/mistake not caught by above
            explanation_parts.append(f"{prefix} This move significantly worsens the position from {format_score(cp_if_best_played, current_player_to_move == chess.WHITE)} to {format_score(cp_after_player_move, current_player_to_move == chess.WHITE)}.")


    # --- III. INACCURACIES ---
    elif classification == "Inaccuracy":
        explanation_parts.append(f"Inaccuracy. {player_actual_move_san} is a suboptimal choice.")
        if engine_best_move_san != player_actual_move_san:
            eval_drop_abs = abs(eval_drop_cp)
            if eval_drop_abs > 70: # More significant inaccuracy
                explanation_parts.append(f"This move concedes about {eval_drop_abs/100.0:.2f} pawns in evaluation compared to the best option.")
            else:
                explanation_parts.append("While not a major error, there was a stronger continuation.")

            best_line_str = describe_line(original_board_fen, best_alternative_pv, limit=2)
            explanation_parts.append(
                f"Consider {engine_best_move_san} instead. "
                f"It might have offered {('better attacking chances.' if cp_if_best_played > cp_after_player_move + 30 else 'a more solid defensive setup.' if cp_if_best_played < cp_after_player_move - 30 else 'a slightly more favorable middlegame structure.')} "
                f"A possible line: {best_line_str}."
            )
            if punishment_pv and punishment_pv[0] and (cp_if_best_played - cp_after_player_move > 50):
                board_after_player_actual_move_fen = board_before_player_move.copy()
                board_after_player_actual_move_fen.push(player_actual_move_obj)
                punishing_line_str = describe_line(board_after_player_actual_move_fen.fen(), punishment_pv, limit=1)
                explanation_parts.append(f"Your move allows the opponent to improve their position with {punishing_line_str}.")


    # --- IV. POSITIVE MOVES (Brilliant, Great, Best, Good, Book) ---
    elif classification == "Brilliant":
        explanation_parts.append(f"Brilliant move ({player_actual_move_san})! This is an exceptional find by {player_color_str}.")
        temp_board_brilliant = board_before_player_move.copy()
        is_sacrifice = False # Re-evaluate sacrifice for explanation context
        # (Simplified sacrifice check - can be enhanced based on classify_move)
        if not temp_board_brilliant.is_capture(player_actual_move_obj):
            mat_before = get_board_material_balance(temp_board_brilliant, current_player_to_move)
            temp_board_brilliant.push(player_actual_move_obj)
            mat_after = get_board_material_balance(temp_board_brilliant, not temp_board_brilliant.turn) # Perspective of player who moved
            if mat_after < mat_before - 0.5: is_sacrifice = True

        if is_sacrifice:
            explanation_parts.append(
                "It involves a daring sacrifice that the engine deems best, creating significant complications or a strong attack."
            )
        else:
            explanation_parts.append(
                "A very strong and perhaps surprising move that greatly improves your position or sets up a powerful threat."
            )
        # Describe the continuation
        if punishment_pv: # Here, punishment_pv is the engine's line *after* the brilliant move
            board_after_brilliant_fen = board_before_player_move.copy()
            board_after_brilliant_fen.push(player_actual_move_obj)
            brilliant_line_str = describe_line(board_after_brilliant_fen.fen(), punishment_pv, limit=3, include_move_numbers=True)
            explanation_parts.append(f"The key idea is revealed in the line: {brilliant_line_str}, leading to a clear advantage ({format_score(cp_after_player_move, current_player_to_move == chess.WHITE)}).")


    elif classification == "Great":
        explanation_parts.append(f"Great move ({player_actual_move_san})! A powerful play by {player_color_str}.")
        explanation_parts.append(
            "This move is among the top engine choices and significantly strengthens your position, "
            "perhaps by creating a threat, improving piece activity, or seizing an important square."
        )
        if punishment_pv:
            board_after_great_fen = board_before_player_move.copy()
            board_after_great_fen.push(player_actual_move_obj)
            great_line_str = describe_line(board_after_great_fen.fen(), punishment_pv, limit=2)
            explanation_parts.append(f"A likely continuation could be: {great_line_str}, consolidating your advantage ({format_score(cp_after_player_move, current_player_to_move == chess.WHITE)}).")


    elif classification == "Best Move":
        explanation_parts.append(f"Best Move. {player_actual_move_san} is the optimal continuation according to the engine.")
        if cp_after_player_move > 100: # If already in a good position
            explanation_parts.append("This accurately maintains or increases your advantage.")
        elif cp_after_player_move < -100: # If in a difficult position
            explanation_parts.append("This is the most resilient defense or the best way to create counterplay.")
        else: # Roughly equal position
            explanation_parts.append("A precise move that keeps the balance or seeks a slight edge.")
        # Optionally, show the line if it's interesting
        if punishment_pv and player_actual_move_obj == engine_best_move_obj : # if it IS the engine's top line
             best_line_str = describe_line(original_board_fen, best_alternative_pv, limit=2) # best_alternative_pv is the PV after this best move
             # This logic is a bit circular. Punishment PV is what we want.
             board_after_best_move_fen = board_before_player_move.copy(); board_after_best_move_fen.push(player_actual_move_obj)
             line_after_best = describe_line(board_after_best_move_fen.fen(), punishment_pv, limit=2)
             if line_after_best:
                explanation_parts.append(f"The main line continues: {line_after_best}.")


    elif classification == "Good":
        explanation_parts.append(f"Good move. {player_actual_move_san} is a solid and sensible choice.")
        if abs(eval_drop_cp) < 20 : # Very close to best
             explanation_parts.append("It's nearly as strong as the engine's top pick.")
        else:
             explanation_parts.append("While not the absolute best, it effectively addresses the needs of the position.")
        # Could add context like "Develops a piece to a good square" or "Improves king safety"
        # if we add more board analysis helpers.


    elif classification == "Book":
        explanation_parts.append(f"Book move. {player_actual_move_san} is a standard opening move.")
        explanation_parts.append("This move is well-known in opening theory for this position.")


    # --- V. FALLBACK (Should ideally not be reached if classification is set) ---
    if not explanation_parts:
        if player_actual_move_san == engine_best_move_san and classification not in ["Brilliant", "Great", "Book"]:
            return f"Best Move. {player_actual_move_san} is the top engine choice, maintaining the position's character."
        elif classification == "N/A":
             return f"Move {player_actual_move_san}. Engine analysis was inconclusive for this position."
        return f"{classification}. ({player_actual_move_san})" # Simple fallback for unhandled cases

    final_explanation = " ".join(part for part in explanation_parts if part and part.strip())
    return final_explanation if final_explanation.strip() else f"{classification}. ({player_actual_move_san})" # Ensure non-empty return



# --- Move Classification & Accuracy ---
def classify_move(eval_drop_cp, board_before_move, player_move, engine_best_move, eval_if_best_played_cp):
    is_sacrifice = False
    if player_move:
        temp_board = board_before_move.copy()
        # Check if player's move is not a capture OR if it captures a less valuable piece than offered
        # This is a simplified sacrifice check
        if not temp_board.is_capture(player_move) or \
           (temp_board.is_capture(player_move) and get_material_value(temp_board.piece_at(player_move.to_square).symbol()) < 2): # e.g. QxB, Q sac
            material_before = get_board_material_balance(temp_board, temp_board.turn)
            temp_board.push(player_move)
            material_after = get_board_material_balance(temp_board, not temp_board.turn) # Perspective of player who moved
            if material_after < material_before - 0.5: # Lost at least a pawn without similar immediate capture
                is_sacrifice = True

    # Ensure eval_if_best_played_cp is not None for these checks
    eval_if_best_played_cp_safe = eval_if_best_played_cp if eval_if_best_played_cp is not None else 0

    if eval_drop_cp <= BRILLIANT_MOVE_MAX_DROP and is_sacrifice and eval_if_best_played_cp_safe > 150 :
        return "Brilliant"
    if eval_drop_cp <= GREAT_MOVE_MAX_DROP and eval_if_best_played_cp_safe > 100 :
        return "Great"
    if eval_drop_cp <= BEST_MOVE_MAX_DROP:
        return "Best Move"
    if eval_drop_cp < INACCURACY_THRESHOLD_MIN_DROP :
        return "Good"
    if eval_drop_cp < MISTAKE_THRESHOLD_MIN_DROP:
        return "Inaccuracy"
    if eval_drop_cp < BLUNDER_THRESHOLD_MIN_DROP:
        return "Mistake"
    return "Blunder"

def calculate_accuracy_acpl(centipawn_losses):
    if not centipawn_losses:
        return 0, 100.0
    total_loss = sum(min(loss, MAX_CENTIPAWN_LOSS_PER_MOVE) for loss in centipawn_losses)
    acpl = total_loss / len(centipawn_losses)
    accuracy = max(0, min(100, 103 * math.exp(-0.043 * acpl) - 3))
    return acpl, round(accuracy,1)

def estimate_game_performance_rating(acpl):
    if acpl <= 5: return 2700
    if acpl <= 10: return 2550
    if acpl <= 15: return 2400
    if acpl <= 20: return 2300
    if acpl <= 25: return 2200
    if acpl <= 30: return 2100
    if acpl <= 40: return 2000
    if acpl <= 50: return 1850
    if acpl <= 60: return 1700
    if acpl <= 75: return 1550
    if acpl <= 90: return 1400
    if acpl <= 110: return 1200
    if acpl <= 130: return 1000
    return 800

# --- Core Analysis Logic ---
def analyze_game_pgn(pgn_text):
    if not engine:
        return None, "Engine not initialized."
    try:
        pgn_io = io.StringIO(pgn_text)
        game = chess.pgn.read_game(pgn_io)
        if game is None:
            return None, "Invalid PGN data."
    except Exception as e:
        app.logger.error(f"PGN parsing error: {e}")
        return None, f"PGN parsing error: {e}"

    board = game.board()
    full_analysis_results = []
    white_cp_losses = []
    black_cp_losses = []
    white_move_counts = {"Brilliant":0, "Great":0, "Best Move":0, "Good":0, "Inaccuracy":0, "Mistake":0, "Blunder":0, "Book":0}
    black_move_counts = {"Brilliant":0, "Great":0, "Best Move":0, "Good":0, "Inaccuracy":0, "Mistake":0, "Blunder":0, "Book":0}
    BOOK_PLY_LIMIT = 10
    default_neutral_pov_score = chess.engine.PovScore(chess.engine.Cp(0), chess.WHITE)

    # Determine initial FEN correctly
    if game.headers.get("FEN"):
        initial_fen_for_report = game.headers.get("FEN")
        try:
            # Validate FEN slightly if present in headers before setting board
            chess.Board(initial_fen_for_report)
        except ValueError:
            app.logger.warning(f"Invalid FEN in PGN headers: {initial_fen_for_report}. Using standard starting FEN.")
            initial_fen_for_report = chess.STARTING_FEN
            board.reset() # Reset board to standard if header FEN was bad
            if game.headers.get("SetUp") == "1": # If SetUp was true, but FEN invalid, this is odd.
                 app.logger.warning("PGN has SetUp=1 but FEN is invalid or missing. Analysis might be from standard position.")

    elif game.headers.get("SetUp") == "1" and not game.headers.get("FEN"):
        app.logger.warning("PGN has SetUp=1 but no FEN tag. Assuming standard starting position for analysis, which might be incorrect for the game.")
        initial_fen_for_report = chess.STARTING_FEN # Or try to get it from the first node if possible, though board object is already set up
        board.reset()
    else:
        initial_fen_for_report = chess.STARTING_FEN

    # The `game.board()` is initialized based on headers by python-chess.
    # We use its state as the source of truth for the *actual* game start.
    # `initial_fen_for_report` is what we tell the frontend was the start.
    # If there's a discrepancy, the analysis might be off if game didn't start from standard.
    # Best practice: PGN should have FEN if not standard start.

    actual_game_starting_fen = game.board().fen(en_passant='fen')
    if initial_fen_for_report != actual_game_starting_fen:
        app.logger.info(f"Note: PGN initial FEN for report '{initial_fen_for_report}', but game object starts with '{actual_game_starting_fen}'. Analysis uses game object's start.")
        # The `board` object used for iteration is already correctly set up by `chess.pgn.read_game`
        # based on FEN/SetUp headers. So, `fen_at_decision_point` will be correct.
        # The `initial_fen` in the final report should reflect what the game *actually* started with.
        initial_fen_for_report = actual_game_starting_fen


    for node_idx, node in enumerate(game.mainline()):
        actual_move_from_pgn_obj = node.move
        current_player_to_move = board.turn
        fen_at_decision_point = board.fen(en_passant='fen')
        is_book_move = node.ply() <= BOOK_PLY_LIMIT # Use <= for ply

        try:
            info_for_original_position = engine.analyse(board, chess.engine.Limit(time=ANALYSIS_TIME_LIMIT_PER_MOVE))
        except chess.engine.EngineTerminatedError: return None, "Engine terminated."
        except Exception as e: return None, f"Engine analysis error (original pos): {e}"

        engines_best_move_obj = info_for_original_position.get("pv", [None])[0]
        try:
            san_actual_move = board.san(actual_move_from_pgn_obj)
        except ValueError: san_actual_move = str(actual_move_from_pgn_obj) # Fallback to UCI

        if engines_best_move_obj is None: # Engine found no moves (e.g., stalemate/checkmate already)
            board.push(actual_move_from_pgn_obj)
            fen_after_player_move = board.fen(en_passant='fen')
            full_analysis_results.append({
                "ply": node.ply(), "fen_before_move": fen_at_decision_point, "fen_after_move": fen_after_player_move,
                "move_san": san_actual_move, "player": "White" if current_player_to_move else "Black",
                "classification": "N/A", "eval_drop_cp": 0, "best_move_engine_san": "N/A",
                "explanation": "Game likely ended or no legal moves for engine.",
                "eval_if_best_played_cp": 0, "eval_after_player_move_cp": 0
            })
            continue

        try:
            san_engines_best_move = board.san(engines_best_move_obj)
        except ValueError: san_engines_best_move = str(engines_best_move_obj)

        score_if_best_played_raw = info_for_original_position.get("score", default_neutral_pov_score)
        score_if_best_played_pov = score_if_best_played_raw.pov(current_player_to_move)
        cp_eval_if_best_played = score_if_best_played_pov.score(mate_score=10000)

        board.push(actual_move_from_pgn_obj)
        fen_after_player_move = board.fen(en_passant='fen')

        try:
            info_after_player_actual_move = engine.analyse(board, chess.engine.Limit(time=ANALYSIS_TIME_LIMIT_PER_MOVE))
        except chess.engine.EngineTerminatedError: board.pop(); return None, "Engine terminated."
        except Exception as e: board.pop(); return None, f"Engine analysis error (player move): {e}"

        score_after_player_move_raw = info_after_player_actual_move.get("score", default_neutral_pov_score)
        score_after_player_move_pov = score_after_player_move_raw.pov(current_player_to_move)
        cp_eval_after_player_move = score_after_player_move_pov.score(mate_score=10000)

        eval_drop_cp = 0
        actual_cp_loss_for_accuracy = 0
        if cp_eval_if_best_played is not None and cp_eval_after_player_move is not None:
            eval_drop_cp = cp_eval_if_best_played - cp_eval_after_player_move
            actual_cp_loss_for_accuracy = max(0, eval_drop_cp)

        if is_book_move:
            classification = "Book"
        else:
            temp_board_before_move = chess.Board(fen_at_decision_point)
            classification = classify_move(eval_drop_cp, temp_board_before_move, actual_move_from_pgn_obj, engines_best_move_obj, cp_eval_if_best_played)
            if current_player_to_move == chess.WHITE: white_cp_losses.append(actual_cp_loss_for_accuracy)
            else: black_cp_losses.append(actual_cp_loss_for_accuracy)

        counts_dict = white_move_counts if current_player_to_move == chess.WHITE else black_move_counts
        counts_dict[classification] = counts_dict.get(classification, 0) + 1

        explanation = get_detailed_explanation(
            fen_at_decision_point, actual_move_from_pgn_obj, san_actual_move,
            engines_best_move_obj, san_engines_best_move,
            info_for_original_position, info_after_player_actual_move,
            engine, current_player_to_move, classification
        )

        full_analysis_results.append({
            "ply": node.ply(), "fen_before_move": fen_at_decision_point, "fen_after_move": fen_after_player_move,
            "move_san": san_actual_move, "player": "White" if current_player_to_move == chess.WHITE else "Black",
            "classification": classification, "eval_drop_cp": round(eval_drop_cp) if eval_drop_cp is not None else None,
            "best_move_engine_san": san_engines_best_move, "explanation": explanation,
            "eval_if_best_played_cp": cp_eval_if_best_played, "eval_after_player_move_cp": cp_eval_after_player_move
        })

    white_acpl, white_accuracy = calculate_accuracy_acpl(white_cp_losses)
    black_acpl, black_accuracy = calculate_accuracy_acpl(black_cp_losses)
    white_gpr = estimate_game_performance_rating(white_acpl)
    black_gpr = estimate_game_performance_rating(black_acpl)

    report = {
        "white_summary": {"accuracy_percent": white_accuracy, "average_centipawn_loss": round(white_acpl, 2), "game_performance_rating_estimate": white_gpr, "move_counts": white_move_counts},
        "black_summary": {"accuracy_percent": black_accuracy, "average_centipawn_loss": round(black_acpl, 2), "game_performance_rating_estimate": black_gpr, "move_counts": black_move_counts},
        "move_by_move_analysis": full_analysis_results,
        "initial_fen": initial_fen_for_report
    }
    return report, None

@app.route('/analyze', methods=['POST'])
def analyze_pgn_endpoint():
    global engine
    if not engine: initialize_engine()
    if not engine: return jsonify({"error": "Chess engine could not be initialized."}), 500
    if not request.json or 'pgn' not in request.json:
        return jsonify({"error": "Missing 'pgn' in JSON request body"}), 400
    pgn_text = request.json['pgn']
    app.logger.info(f"Received PGN for analysis (first 50 chars): {pgn_text[:50]}")
    analysis_report, error_message = analyze_game_pgn(pgn_text)
    if error_message:
        app.logger.error(f"Analysis error: {error_message}")
        return jsonify({"error": error_message}), 500
    app.logger.info("Analysis successful.")
    return jsonify(analysis_report), 200

@app.route('/status', methods=['GET'])
def status_endpoint():
    if engine:
        try:
            engine_info = engine.id.get("name", "Unknown Engine")
            return jsonify({"status": "ok", "engine_status": "running", "engine_name": engine_info}), 200
        except Exception as e:
            return jsonify({"status": "error", "engine_status": "error_pinging", "message": str(e)}), 500
    else:
        return jsonify({"status": "error", "engine_status": "not_initialized"}), 500



def main_cli():
    global engine 
    print(f"Attempting to initialize Stockfish engine from: {STOCKFISH_PATH}")
    initialize_engine() 
    if not engine:
        print("CRITICAL: Failed to initialize Stockfish. The server cannot start.")
        # Optionally, raise an exception or exit
        # raise RuntimeError("Stockfish engine could not be initialized.")
        return # Or sys.exit(1) after importing sys

    print(f"Stockfish engine initialized. Starting Flask server...")
    # Use host='0.0.0.0' to be accessible externally, port as desired.
    # debug=False is generally recommended for "production" packaged apps,
    # but True is fine for development/local use.
    app.run(debug=os.environ.get("FLASK_DEBUG", "False").lower() == "true",
            host=os.environ.get("FLASK_HOST", "0.0.0.0"),
            port=int(os.environ.get("FLASK_PORT", 5000)))