WIDTH = 800
HEIGHT = 480
COLS = 4
ROWS = 2
RAMP_H = 48
RAMP_STEPS = 13
CELL_W = WIDTH // COLS
CELL_H = (HEIGHT - RAMP_H) // ROWS

CHARTS = {
    "A": [0, 1, 2, 3, 4, 5, 6, 7],
    "B": [7, 6, 5, 4, 3, 2, 1, 0],
}

PEN_NAMES = ["black", "white", "green", "blue", "red", "yellow", "orange", "clean"]

# Neutral grey levels shown in the ramp strip (area coverage of white over
# black when fs-dithered); index 0 is solid black, last is solid white.
RAMP_LEVELS = [round(i * 255 / (RAMP_STEPS - 1)) for i in range(RAMP_STEPS)]


def cell_rect(slot):
    row = slot // COLS
    col = slot % COLS
    return (col * CELL_W, row * CELL_H, CELL_W, CELL_H)


def cell_centre(slot):
    x, y, w, h = cell_rect(slot)
    return (x + w // 2, y + h // 2)


def ramp_step_rect(step):
    w = WIDTH / RAMP_STEPS
    return (round(step * w), HEIGHT - RAMP_H, max(1, round(w)), RAMP_H)


def ramp_step_centre(step):
    x, y, w, h = ramp_step_rect(step)
    return (x + w // 2, y + h // 2)
