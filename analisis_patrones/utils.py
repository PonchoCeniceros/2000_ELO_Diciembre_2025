import re
import io
import chess
import base64
import chess.svg
import chess.pgn
import pandas as pd
import ipywidgets as widgets
from datetime import datetime
import matplotlib.pyplot as plt
from stockfish import Stockfish
from IPython.display import display, HTML, SVG, clear_output


#
#
#
def generate_df(filename):
    with open(filename, "r", encoding="utf-8") as f:
        raw_data = f.read()

        # Separar partidas por "[Event \"Live Chess\"]"
        raw_games = raw_data.split('[Event "Live Chess"]')
        raw_games = [g.strip() for g in raw_games if g.strip()]

        data = []

        for game in raw_games:
            full_game = '[Event "Live Chess"]\n' + game  # reconstruir cabecera
            headers = dict(re.findall(r'\[(\w+)\s+"([^"]+)"\]', full_game))

            # Extraer sección de jugadas
            moves_text = "\n".join(
                [
                    line
                    for line in full_game.splitlines()
                    if not line.startswith("[") and line.strip()
                ]
            )
            moves_flat = re.sub(r"\s+", " ", moves_text).strip()

            # Separar usando "1." hasta justo antes de "8."
            match_opening = re.search(r"1\..*?(?=\s8\.)", moves_flat)
            opening = match_opening.group(0).strip() if match_opening else ""

            # Resto de las jugadas desde "8." en adelante
            match_mid_end = re.search(r"\s8\..*", moves_flat)
            mid_end = match_mid_end.group(0).strip() if match_mid_end else ""

            # Determinar color de PonchoCeniceros
            # Determinar rival
            if headers.get("White") == "PonchoCeniceros":
                pieces = "white"
                against = headers.get("Black")
            elif headers.get("Black") == "PonchoCeniceros":
                pieces = "black"
                against = headers.get("White")
            else:
                pieces = "unknown"
                against = "unknown"

            data.append(
                {
                    "date": datetime.strptime(
                        headers.get("Date", ""), "%Y.%m.%d"
                    ).date(),
                    "pieces": pieces,
                    "result": headers.get("Result", ""),
                    "against": against,
                    "opening": opening,
                    "midgame + endgame": mid_end,
                }
            )

        # Crear DataFrame
        return pd.DataFrame(data)


#
#
#
def count_moves(moves, base=7):
    # Buscar el último número de jugada con regex
    match = re.search(r"(\d+)\.\s*\S+(?:\s+\S+)?\s+(1-0|0-1|1/2-1/2)", moves.strip())
    if match:
        num = int(match.group(1))
        final_moves = match.group(0).strip().split()
        # Si hay 3 elementos (ej. "19. Rxd8+ 1-0") → sólo jugada de blancas
        # Si hay 4 o más (ej. "18. Qh3 d6 0-1") → blancas y negras
        if len(final_moves) >= 4:
            return num
        else:
            return num - 1 + 0.5
    return base


#
#
#
class ChessGamesGrid:
    def __init__(self, games_data, cols=3, flip_view=False):
        """
        games_data: lista de dicts con claves 'opening' (str) y 'result' (str)
        """
        self.cols = cols
        self.games_data = games_data
        self.all_boards_states = self._generate_all_board_states()
        self.current_move = 0
        self.flip_view = flip_view

        self.grid_out = widgets.Output()
        self.btn_prev = widgets.Button(description="◀️ Anterior")
        self.btn_next = widgets.Button(description="Siguiente ▶️")
        self.label_status = widgets.Label()

        self.btn_prev.on_click(self.on_prev)
        self.btn_next.on_click(self.on_next)

        self.controls = widgets.HBox([self.btn_prev, self.btn_next, self.label_status])
        self.controls.layout = widgets.Layout(
            padding="25px", justify_content="center", align_items="center"
        )

        display(self.controls, self.grid_out)
        self.update_display()

    def _parse_moves_from_string(self, moves_str):
        clean_str = re.sub(r"\d+\.", "", moves_str)
        moves = clean_str.strip().split()
        return moves

    def _generate_all_board_states(self):
        all_states = []
        for game in self.games_data:
            moves = self._parse_moves_from_string(game["opening"])
            board = chess.Board()
            states = [board.copy()]
            for move in moves:
                try:
                    board.push_san(move)
                    states.append(board.copy())
                except:
                    break
            all_states.append(states)
        return all_states

    def _show_as_grid(self):
        html = f"""
        <div style="display: grid; grid-template-columns: repeat({self.cols}, 1fr); gap: 10px;">
        """

        colors = {
            "square light": "#F1F8E9",
            "square dark": "#C8E6C9",
        }

        for i, states in enumerate(self.all_boards_states):
            idx = min(self.current_move, len(states) - 1)
            board = states[idx]
            svg_board = chess.svg.board(
                board=board,
                colors=colors,
                style="wikipedia",
                size=256,
                flipped=self.flip_view,
            )
            result = self.games_data[i]["result"]
            against = self.games_data[i]["against"]
            moves = self.games_data[i]["moves"]
            date = self.games_data[i]["date"]

            html += f"""
            <div>
                <p style="text-align:center;"><strong>vs {against}</strong><br>{date}</p>
                {svg_board}
                <p style="text-align:center;"><strong>{result}</strong><br>{moves} movs.</p>
            </div>"""

        html += "</div>"
        return html

    def update_display(self):
        with self.grid_out:
            clear_output(wait=True)
            html = self._show_as_grid()
            display(HTML(html))
        self.label_status.value = f"Movimiento global: {self.current_move}"

    def on_next(self, _):
        max_len = max(len(states) for states in self.all_boards_states) - 1
        if self.current_move < max_len:
            self.current_move += 1
            self.update_display()

    def on_prev(self, _):
        if self.current_move > 0:
            self.current_move -= 1
            self.update_display()


#
#
#
class ChessAnalysisGrid:
    def __init__(
        self,
        games_data,
        cols=3,
        flip_view=False,
        stockfish_path="/opt/homebrew/bin/stockfish",
    ):
        """
        games_data: lista de dicts con claves 'opening', 'result', 'against', 'moves', 'date'
        stockfish_path: ruta al ejecutable de Stockfish
        """
        self.cols = cols
        self.games_data = games_data
        self.current_move = 0
        self.flip_view = flip_view
        self.all_boards_states = self._generate_all_board_states()

        # Inicializar Stockfish
        self.stockfish = Stockfish(path=stockfish_path)

        # UI
        self.grid_out = widgets.Output()
        self.btn_prev = widgets.Button(description="◀️ Anterior")
        self.btn_next = widgets.Button(description="Siguiente ▶️")
        self.label_status = widgets.Label()

        self.btn_prev.on_click(self.on_prev)
        self.btn_next.on_click(self.on_next)

        self.controls = widgets.HBox([self.btn_prev, self.btn_next, self.label_status])
        self.controls.layout = widgets.Layout(
            padding="25px", justify_content="center", align_items="center"
        )

        display(self.controls, self.grid_out)
        self.update_display()

    def _parse_moves_from_string(self, moves_str):
        clean_str = re.sub(r"\d+\.", "", moves_str)
        moves = clean_str.strip().split()
        return moves

    def _generate_all_board_states(self):
        all_states = []
        for game in self.games_data:
            moves = self._parse_moves_from_string(
                game.get("opening", game.get("game", ""))
            )
            board = chess.Board()
            states = [board.copy()]
            for move in moves:
                try:
                    board.push_san(move)
                    states.append(board.copy())
                except:
                    break
            all_states.append(states)
        return all_states

    def _evaluate_position(self, board):
        try:
            self.stockfish.set_fen_position(board.fen())
            evaluation = self.stockfish.get_evaluation()
            if evaluation["type"] == "cp":
                return f"{evaluation['value'] / 100}"
            elif evaluation["type"] == "mate":
                return f"Mate en {evaluation['value']}"
            else:
                return "N/A"
        except:
            return "N/A"

    def _show_as_grid(self):
        html = f"""
        <div style="display: grid; grid-template-columns: repeat({self.cols}, 1fr); gap: 10px;">
        """

        colors = {
            "square light": "#F1F8E9",
            "square dark": "#C8E6C9",
        }

        for i, states in enumerate(self.all_boards_states):
            idx = min(self.current_move, len(states) - 1)
            board = states[idx]
            svg_board = chess.svg.board(
                board=board,
                colors=colors,
                style="wikipedia",
                size=256,
                flipped=self.flip_view,
            )
            result = self.games_data[i]["result"]
            against = self.games_data[i]["against"]
            moves = self.games_data[i]["moves"]
            date = self.games_data[i]["date"]
            score = self._evaluate_position(board)

            html += f"""
                <div>
                    <p style="text-align:center;"><strong>vs {against}</strong><br>{date}</p>
                    {svg_board}
                    <p style="text-align:center;">
                        <strong>{result} | <span style='color:red;'>{score}</span></strong><br>{moves} movs.
                    </p>
                </div>
            """

        html += "</div>"
        return html

    def update_display(self):
        with self.grid_out:
            clear_output(wait=True)
            html = self._show_as_grid()
            display(HTML(html))
        self.label_status.value = f"Movimiento global: {self.current_move}"

    def on_next(self, _):
        max_len = max(len(states) for states in self.all_boards_states) - 1
        if self.current_move < max_len:
            self.current_move += 1
            self.update_display()

    def on_prev(self, _):
        if self.current_move > 0:
            self.current_move -= 1
            self.update_display()


#
#
#
class AnalysisGraphGrid:
    def __init__(self, cols=3, stockfish_path="/opt/homebrew/bin/stockfish"):
        self.stockfish = Stockfish(stockfish_path)
        self.cols = cols
        self.games = []

    def load_games(self, games):
        """games: List[Dict] - cada dict debe tener claves: game, result, against, date, moves"""
        self.games = games

    def _plot_evaluation_graph(self, evaluations, result):
        color = "green" if result == "1-0" else "red" if result == "0-1" else "gray"
        fig, ax = plt.subplots(figsize=(3, 2))  # un poco más alto

        ax.plot(evaluations, color=color, linewidth=2, marker="o", markersize=3)
        ax.axhline(0, color="gray", linestyle="--", linewidth=1)
        ax.set_ylim(-5.5, 5.5)
        ax.axis("off")

        buf = io.BytesIO()
        # 👇 Usamos pad_inches en lugar de bbox_inches para evitar recorte
        plt.savefig(buf, format="png", dpi=150, pad_inches=0.3)
        buf.seek(0)
        img_data = base64.b64encode(buf.read()).decode("utf-8")
        plt.close(fig)
        return f"<img src='data:image/png;base64,{img_data}'>"

    def _evaluate_game(self, pgn_text):
        game = chess.pgn.read_game(io.StringIO(pgn_text))
        board = game.board()
        evaluations = []

        for move in game.mainline_moves():
            board.push(move)
            self.stockfish.set_fen_position(board.fen())
            eval_data = self.stockfish.get_evaluation()
            if eval_data["type"] == "cp":
                score = eval_data["value"] / 100
            elif eval_data["type"] == "mate":
                score = 10 if eval_data["value"] > 0 else -10
            else:
                score = 0
            evaluations.append(score)

        return evaluations

    def show_as_graph_grid(self):
        html = f"""
        <div style="display: grid; grid-template-columns: repeat({self.cols}, 1fr); gap: 10px;">
        """

        for g in self.games:
            evaluations = self._evaluate_game(g["game"])
            graph_html = self._plot_evaluation_graph(evaluations, g["result"])

            final_score = evaluations[-1] if evaluations else 0
            date_str = g["date"]
            try:
                date = datetime.strptime(date_str, "%Y-%m-%d").strftime("%d/%m/%Y")
            except:
                date = date_str

            html += f"""
                <div style="text-align:center;">
                    <p><strong>vs {g["against"]}</strong><br>{date}</p>
                    {graph_html}
                    <p><strong>{g["result"]} | <span style='color:red;'>{final_score:.2f}</span></strong><br>{int(g["moves"])} movs.</p>
                </div>
            """

        html += "</div>"
        return HTML(html)
