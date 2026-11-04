import tkinter as tk
from tkinter import messagebox
import random

class MinesweeperCanvas:
    def __init__(self, root, rows=16, cols=30, mines=99):
        self.root = root
        self.root.title("Minesweeper")
        self.root.geometry("1000x600")
        
        self.rows = rows
        self.cols = cols
        self.total_mines = mines
        self.game_over = False
        self.flags = 0
        self.revealed_count = 0
        
        self.base_cell_size = 30
        self.current_cell_size = self.base_cell_size
        
        self.drag_data = {"x": 0, "y": 0, "is_dragging": False, "button": None}
        
        # Top status bar
        self.status_frame = tk.Frame(root, height=20, bg="#f0f0f0")
        self.status_frame.pack(fill=tk.X, side=tk.TOP)
        
        self.mines_label = tk.Label(self.status_frame, text=f"Mines: {self.total_mines}", font=("Arial", 8), bg="#f0f0f0")
        self.mines_label.pack(side=tk.LEFT, padx=20, pady=5)
        
        self.restart_btn = tk.Button(self.status_frame, text="Restart", command=self.reset_game, font=("Arial", 7))
        self.restart_btn.pack(side=tk.RIGHT, padx=20, pady=5)
        
        # Main canvas
        self.canvas = tk.Canvas(root, bg="#ffffff", highlightthickness=0, xscrollincrement=1, yscrollincrement=1)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        # Bind mouse events 
        self.canvas.bind("<ButtonRelease-1>", self.on_left_release)
        self.canvas.bind("<Button-3>", self.on_right_click)
        self.canvas.bind("<Double-Button-1>", self.on_double_click)
        
        # Drag to pan (Middle mouse button or Shift+Left click)
        self.canvas.bind("<ButtonPress-2>", self.on_pan_start)
        self.canvas.bind("<B2-Motion>", self.on_pan_move)
        self.canvas.bind("<ButtonRelease-2>", self.on_pan_end)
        self.canvas.bind("<Shift-ButtonPress-1>", self.on_pan_start)
        self.canvas.bind("<Shift-B1-Motion>", self.on_pan_move)
        self.canvas.bind("<Shift-ButtonRelease-1>", self.on_pan_end)
        
        # Mouse wheel zoom
        self.canvas.bind("<MouseWheel>", self.on_zoom)
        self.canvas.bind("<Button-4>", self.on_zoom)
        self.canvas.bind("<Button-5>", self.on_zoom)

        self.init_game()

    def init_game(self):
        self.game_over = False
        self.flags = 0
        self.revealed_count = 0
        self.mines_label.config(text=f"Mines: {self.total_mines}")
        
        self.mines = set()
        self.revealed = set()
        self.flagged = set()
        self.mines_placed = False # Flag to track if mines are generated
        
        self.draw_board()

    def place_mines(self, safe_r, safe_c):
        # Generate mines, avoiding the first clicked cell and its neighbors
        safe_zone = set(self.get_neighbors(safe_r, safe_c))
        safe_zone.add((safe_r, safe_c))
        
        while len(self.mines) < self.total_mines:
            r = random.randint(0, self.rows - 1)
            c = random.randint(0, self.cols - 1)
            if (r, c) not in safe_zone:
                self.mines.add((r, c))
        self.mines_placed = True

    def get_neighbors(self, r, c):
        neighbors = []
        for dr in [-1, 0, 1]:
            for dc in [-1, 0, 1]:
                if dr == 0 and dc == 0:
                    continue
                nr, nc = r + dr, c + dc
                if 0 <= nr < self.rows and 0 <= nc < self.cols:
                    neighbors.append((nr, nc))
        return neighbors

    def count_adjacent_mines(self, r, c):
        return sum(1 for nr, nc in self.get_neighbors(r, c) if (nr, nc) in self.mines)

    def draw_board(self):
        self.canvas.delete("all")
        size = self.current_cell_size
        
        for r in range(self.rows):
            for c in range(self.cols):
                x1 = c * size
                y1 = r * size
                x2 = x1 + size
                y2 = y1 + size
                
                if (r, c) in self.revealed:
                    if (r, c) in self.mines:
                        fill_color = "#ff9999"
                        text = "*"
                        text_color = "black"
                    else:
                        fill_color = "#d9d9d9"
                        mine_count = self.count_adjacent_mines(r, c)
                        text = str(mine_count) if mine_count > 0 else ""
                        colors = {1: "blue", 2: "green", 3: "red", 4: "darkblue", 5: "darkred", 6: "teal", 7: "black", 8: "gray"}
                        text_color = colors.get(mine_count, "black")
                elif (r, c) in self.flagged:
                    fill_color = "#b0b0b0"
                    text = "F"
                    text_color = "red"
                else:
                    fill_color = "#b0b0b0"
                    text = ""
                    text_color = "black"
                
                self.canvas.create_rectangle(x1, y1, x2, y2, fill=fill_color, outline="#888888", tags=f"cell_{r}_{c}")
                
                if text:
                    font_size = max(8, int(size * 0.5))
                    self.canvas.create_text(x1 + size/2, y1 + size/2, text=text, fill=text_color, font=("Arial", font_size, "bold"), tags=f"text_{r}_{c}")

        total_width = self.cols * size
        total_height = self.rows * size
        margin = max(300, total_width // 2)
        self.canvas.config(scrollregion=(-margin, -margin, total_width + margin, total_height + margin))

    def refresh_cell(self, r, c):
        size = self.current_cell_size
        x1 = c * size
        y1 = r * size
        x2 = x1 + size
        y2 = y1 + size
        
        self.canvas.delete(f"cell_{r}_{c}")
        self.canvas.delete(f"text_{r}_{c}")
        
        if (r, c) in self.revealed:
            if (r, c) in self.mines:
                fill_color, text, text_color = "#ff9999", "*", "black"
            else:
                fill_color = "#d9d9d9"
                mine_count = self.count_adjacent_mines(r, c)
                text = str(mine_count) if mine_count > 0 else ""
                colors = {1: "blue", 2: "green", 3: "red", 4: "darkblue", 5: "darkred", 6: "teal", 7: "black", 8: "gray"}
                text_color = colors.get(mine_count, "black")
        elif (r, c) in self.flagged:
            fill_color, text, text_color = "#b0b0b0", "F", "red"
        else:
            fill_color, text, text_color = "#b0b0b0", "", "black"
            
        self.canvas.create_rectangle(x1, y1, x2, y2, fill=fill_color, outline="#888888", tags=f"cell_{r}_{c}")
        if text:
            font_size = max(8, int(size * 0.5))
            self.canvas.create_text(x1 + size/2, y1 + size/2, text=text, fill=text_color, font=("Arial", font_size, "bold"), tags=f"text_{r}_{c}")

    def get_cell_from_coords(self, event):
        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)
        c = int(x // self.current_cell_size)
        r = int(y // self.current_cell_size)
        if 0 <= r < self.rows and 0 <= c < self.cols:
            return r, c
        return None, None

    def process_left_click(self, event):
        r, c = self.get_cell_from_coords(event)
        
        if r is not None and not self.game_over:
            if (r, c) in self.revealed: return
            if (r, c) in self.flagged: return 
            if not self.mines_placed:
                self.place_mines(r, c)
            
            if (r, c) in self.mines:
                self.reveal_all_mines()
                self.game_over = True
                messagebox.showinfo("Game Over", "You hit a mine!")
            else:
                self.reveal_cell(r, c)
                self.check_win()

    def check_win(self):
        if self.revealed_count == (self.rows * self.cols - self.total_mines):
            self.game_over = True
            messagebox.showinfo("Win", "You cleared the board!")
            
    def on_double_click(self, event):
        if self.drag_data["is_dragging"]: return
        r, c = self.get_cell_from_coords(event)
        if r is not None and not self.game_over:
            if (r, c) in self.revealed and self.count_adjacent_mines(r, c) > 0:
                flag_count = sum(1 for nr, nc in self.get_neighbors(r, c) if (nr, nc) in self.flagged)
                if flag_count == self.count_adjacent_mines(r, c):
                    for nr, nc in self.get_neighbors(r, c):
                        if (nr, nc) not in self.flagged and (nr, nc) not in self.revealed:
                            if (nr, nc) in self.mines:
                                self.reveal_all_mines()
                                self.game_over = True
                                messagebox.showinfo("Game Over", "You hit a mine!")
                            else:
                                self.reveal_cell(nr, nc)
                    self.check_win()

    def on_left_release(self, event):
        if self.drag_data.get("is_dragging"):
            self.drag_data["is_dragging"] = False
            self.canvas.config(cursor="")
            return
        self.process_left_click(event)

    def on_right_click(self, event):
        r, c = self.get_cell_from_coords(event)
        if r is not None and not self.game_over and self.mines_placed:
            # Prevent flagging before the first click
            if (r, c) in self.revealed: return
            
            if (r, c) in self.flagged:
                self.flagged.remove((r, c))
                self.flags -= 1
            else:
                self.flagged.add((r, c))
                self.flags += 1
                
            self.mines_label.config(text=f"Mines: {self.total_mines - self.flags}")
            self.refresh_cell(r, c)

    def reveal_cell(self, r, c):
        if (r, c) in self.revealed or (r, c) in self.flagged:
            return
            
        self.revealed.add((r, c))
        self.revealed_count += 1
        self.refresh_cell(r, c)
        
        if self.count_adjacent_mines(r, c) == 0:
            for nr, nc in self.get_neighbors(r, c):
                self.reveal_cell(nr, nc)

    def reveal_all_mines(self):
        for r, c in self.mines:
            if (r, c) not in self.revealed:
                self.revealed.add((r, c))
                self.refresh_cell(r, c)

    def on_pan_start(self, event):
        self.drag_data["is_dragging"] = True
        self.canvas.config(cursor="fleur")
        self.canvas.scan_mark(event.x, event.y)

    def on_pan_move(self, event):
        if self.drag_data["is_dragging"]:
            self.canvas.scan_dragto(event.x, event.y, gain=1)

    def on_pan_end(self, event):
        self.drag_data["is_dragging"] = False
        self.canvas.config(cursor="")

    def on_zoom(self, event):
        if event.num == 5 or event.delta < 0:
            scale = 0.9
        elif event.num == 4 or event.delta > 0:
            scale = 1.1
        else:
            return

        new_size = self.current_cell_size * scale
        if new_size < 10 or new_size > 100:
            return

        mx = self.canvas.canvasx(event.x)
        my = self.canvas.canvasy(event.y)

        self.current_cell_size = new_size
        self.draw_board()

        self.canvas.update_idletasks()
        new_mx = self.canvas.canvasx(event.x)
        new_my = self.canvas.canvasy(event.y)
        self.canvas.xview_scroll(int(mx - new_mx), "units")
        self.canvas.yview_scroll(int(my - new_my), "units")

    def reset_game(self):
        self.current_cell_size = self.base_cell_size
        self.init_game()

if __name__ == "__main__":
    root = tk.Tk()
    game = MinesweeperCanvas(root, rows=16, cols=30, mines=99)
    root.mainloop()