import chess
from IPython.display import display, HTML, SVG


def make_board(name, fen, arrows, is_black=False):
    board = chess.Board(fen)

    colors = {
        "square light": "#F1F8E9",  # verde pálido
        "square dark": "#C8E6C9",   # verde pastel
    }
    
    highlight = {chess.parse_square("d5"): "#DE7F6D"}
    svg_board = chess.svg.board(
        board=board,
        arrows=arrows,
        fill=highlight,
        colors=colors,
        style="wikipedia",
        size=256,
        flipped=is_black
    )

    with open(f"{name}.svg", "w") as f:
        f.write(svg_board)

    return svg_board


def show_as_grid(boards, cols, gap="10px"):
    html = f'''
    <div style="display: grid; grid-template-columns: repeat({cols}, 1fr); gap: {gap};">
    '''
    
    colors = {
        "square light": "#F1F8E9",  # verde pálido
        "square dark": "#C8E6C9",   # verde pastel
    }
    
    for board, arrows, is_black in boards:
        svg_board = chess.svg.board(
            board=board,
            arrows=arrows,
            colors=colors,
            style="wikipedia",
            size=256,
            flipped=is_black
        )
        html += f'<div>{svg_board}</div>' # <p style="text-align:center;">{result}</p>

    html += '</div>'
    display(HTML(html))


