import re
import chess
import chess.svg
import pandas as pd
import ipywidgets as widgets
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
            if headers.get("White") == "PonchoCeniceros":
                pieces = "white"
            elif headers.get("Black") == "PonchoCeniceros":
                pieces = "black"
            else:
                pieces = "unknown"

            data.append(
                {
                    "pieces": pieces,
                    "result": headers.get("Result", ""),
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
    match = re.search(r'(\d+)\.\s*\S+(?:\s+\S+)?\s+(1-0|0-1|1/2-1/2)', moves.strip())
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
    def __init__(self, games_moves_str, cols=3, flip_view=False):
        self.cols = cols
        self.games_moves_str = games_moves_str
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
        display(self.controls, self.grid_out)
        self.update_display()

    def _parse_moves_from_string(self, moves_str):
        # Elimina los números de jugadas (como "1.", "2.") y divide en movimientos
        import re
        clean_str = re.sub(r"\d+\.", "", moves_str)
        moves = clean_str.strip().split()
        return moves

    def _generate_all_board_states(self):
        all_states = []
        for moves_str in self.games_moves_str:
            moves = self._parse_moves_from_string(moves_str)
            board = chess.Board()
            states = [board.copy()]
            for move in moves:
                try:
                    board.push_san(move)
                    states.append(board.copy())
                except:
                    break  # Por si hay movimientos ilegales o mal formateados
            all_states.append(states)
        return all_states

    def _show_as_grid(self):
        html = f'''
        <div style="display: grid; grid-template-columns: repeat({self.cols}, 1fr); gap: 10px;">
        '''

        colors = {
            "square light": "#F1F8E9",  # verde pálido
            "square dark": "#C8E6C9",   # verde pastel
        }

        for states in self.all_boards_states:
            idx = min(self.current_move, len(states) - 1)
            board = states[idx]
            svg_board = chess.svg.board(
                board=board,
                colors=colors,
                style="wikipedia",
                size=256,
                flipped=self.flip_view
            )
            html += f'<div>{svg_board}</div>'

        html += '</div>'
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
