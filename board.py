import pygame
import os
import random
import sys
from pygame.locals import *

# 初始化pygame
pygame.init()
FONT_NAME = "simhei"  


# 常量定义
BOARD_SIZE = (600, 650)  # 棋盘原始尺寸
PIECE_SIZE = 52  # 棋子原始尺寸
GRID_SIZE = BOARD_SIZE[0] // 9  # 网格大小
BOARD_OFFSET = (5, 0)  # 棋盘偏移量

# 颜色定义
HIGHLIGHT = (255, 255, 0, 100)
MOVE_HINT = (0, 255, 0, 100)
RED = (255, 0, 0)
BLACK = (0, 0, 0)
HINT_TEXT = (50, 50, 150)
FEN_TEXT = (30, 30, 100)

class ChessGame:
    def __init__(self):
        self.screen = None
        self.scaled_board_size = BOARD_SIZE
        self.scaled_piece_size = PIECE_SIZE
        self.scale_factor = 1.0
        self.offset = BOARD_OFFSET
        self.piece_images = {}
        self.board_img = None
        self.selected_piece = None
        self.valid_moves = []
        self.current_player = 'r'  # 'r' 红方, 'b' 黑方
        self.game_over = False
        self.winner = None
        self.history = []
        
        # 初始化字体
        self.init_fonts()
        
        # 初始化棋盘状态
        self.reset_game()
        
        # 创建窗口
        self.create_window()
        
        # 加载图片
        self.load_images()
    
    def init_fonts(self):
        """初始化字体，确保支持中文显示"""
        # 尝试加载系统支持的中文字体
        try:
            self.font = pygame.font.SysFont(FONT_NAME, 24)
            self.small_font = pygame.font.SysFont(FONT_NAME, 20)
            self.large_font = pygame.font.SysFont(FONT_NAME, 72)
            self.medium_font = pygame.font.SysFont(FONT_NAME, 36)
        except:
            # 如果系统字体加载失败，尝试使用默认字体
            try:
                self.font = pygame.font.Font(None, 24)
                self.small_font = pygame.font.Font(None, 20)
                self.large_font = pygame.font.Font(None, 72)
                self.medium_font = pygame.font.Font(None, 36)
                print(f"警告: 无法加载中文字体 '{FONT_NAME}'，使用默认字体")
            except:
                # 如果所有字体加载都失败，创建空字体对象
                self.font = pygame.font.Font(None, 24)
                self.small_font = pygame.font.Font(None, 20)
                self.large_font = pygame.font.Font(None, 72)
                self.medium_font = pygame.font.Font(None, 36)
                print("错误: 无法加载任何字体")
    
    def create_window(self):
        """创建可缩放的窗口"""
        info = pygame.display.Info()
        screen_width, screen_height = info.current_w, info.current_h
        
        # 计算初始窗口大小（屏幕高度的80%）
        init_height = int(screen_height * 0.8)
        init_width = int(init_height * BOARD_SIZE[0] / BOARD_SIZE[1])
        
        self.screen = pygame.display.set_mode((init_width, init_height), pygame.RESIZABLE)
        pygame.display.set_caption("中国象棋揭棋")
        
        # 计算缩放因子
        self.scale_factor = min(init_width / BOARD_SIZE[0], init_height / BOARD_SIZE[1])
        self.scaled_board_size = (int(BOARD_SIZE[0] * self.scale_factor), 
                                 int(BOARD_SIZE[1] * self.scale_factor))
        self.scaled_piece_size = int(PIECE_SIZE * self.scale_factor)
        self.offset = (int(BOARD_OFFSET[0] * self.scale_factor), 
                      int(BOARD_OFFSET[1] * self.scale_factor))
    
    def load_images(self):
        """加载棋盘和棋子图片"""
        # 加载棋盘图片
        try:
            board_path = os.path.join('resource', 'pieces', 'board.bmp')
            self.board_img = pygame.image.load(board_path).convert()
        except pygame.error:
            # 如果加载失败，创建默认棋盘
            self.board_img = pygame.Surface(BOARD_SIZE)
            self.board_img.fill((220, 200, 170))
            pygame.draw.rect(self.board_img, (180, 140, 80), (0, 0, BOARD_SIZE[0], BOARD_SIZE[1]), 5)
            print("棋盘图片加载失败，使用默认棋盘")
        
        # 加载棋子图片
        pieces = {
            'r': ['R', 'N', 'B', 'A', 'K', 'C', 'P', 'X'],
            'b': ['R', 'N', 'B', 'A', 'K', 'C', 'P', 'X']
        }
        
        for color in ['r', 'b']:
            for piece in pieces[color]:
                try:
                    img_path = os.path.join('resource', 'pieces', f'{color}{piece}.bmp')
                    piece_img = pygame.image.load(img_path).convert_alpha()
                    
                    # 如果图片尺寸不是52x52，则缩放
                    if piece_img.get_size() != (PIECE_SIZE, PIECE_SIZE):
                        piece_img = pygame.transform.scale(piece_img, (PIECE_SIZE, PIECE_SIZE))
                    
                    self.piece_images[f"{color}{piece}"] = piece_img
                except pygame.error:
                    # 如果加载失败，创建默认棋子
                    print(f"棋子图片加载失败: {color}{piece}.bmp")
                    self.piece_images[f"{color}{piece}"] = self.create_default_piece(f"{color}{piece}")
    
    def reset_game(self):
        """重置游戏状态"""
        # 初始化隐藏棋盘（实际棋子布局）
        self.hidden_board = [
            ['bR', 'bN', 'bB', 'bA', 'bK', 'bA', 'bB', 'bN', 'bR'],
            ['', '', '', '', '', '', '', '', ''],
            ['', 'bC', '', '', '', '', '', 'bC', ''],
            ['bP', '', 'bP', '', 'bP', '', 'bP', '', 'bP'],
            ['', '', '', '', '', '', '', '', ''],
            ['', '', '', '', '', '', '', '', ''],
            ['rP', '', 'rP', '', 'rP', '', 'rP', '', 'rP'],
            ['', 'rC', '', '', '', '', '', 'rC', ''],
            ['', '', '', '', '', '', '', '', ''],
            ['rR', 'rN', 'rB', 'rA', 'rK', 'rA', 'rB', 'rN', 'rR']
        ]
        
        # 收集除将帅外的所有棋子
        red_pieces = []
        black_pieces = []
        for row in range(10):
            for col in range(9):
                piece = self.hidden_board[row][col]
                if piece and piece[1] != 'K':  # 排除将帅
                    if piece[0] == 'r':
                        red_pieces.append(piece)
                    else:
                        black_pieces.append(piece)
        
        # 打乱棋子
        random.shuffle(red_pieces)
        random.shuffle(black_pieces)
        
        # 重新放置除将帅外的棋子
        red_index = 0
        black_index = 0
        for row in range(10):
            for col in range(9):
                piece = self.hidden_board[row][col]
                if piece and piece[1] != 'K':  # 排除将帅
                    if piece[0] == 'r':
                        self.hidden_board[row][col] = red_pieces[red_index]
                        red_index += 1
                    else:
                        self.hidden_board[row][col] = black_pieces[black_index]
                        black_index += 1
        
        # 初始化表面棋盘（显示给玩家的布局）
        self.surface_board = [row[:] for row in self.hidden_board]  # 复制隐藏棋盘
        # 将除将帅外的所有棋子转为暗子
        for row in range(10):
            for col in range(9):
                piece = self.surface_board[row][col]
                if piece and piece[1] != 'K':  # 排除将帅
                    self.surface_board[row][col] = piece[0] + 'X'
        
        # 使用表面棋盘作为游戏棋盘
        self.board = self.surface_board
        
        self.selected_piece = None
        self.valid_moves = []
        self.current_player = 'r'
        self.game_over = False
        self.winner = None
        self.history = []
    
    def generate_hidden_fen(self):
        """生成隐藏FEN字符串（实际棋子布局）"""
        fen_rows = []
        for row in self.hidden_board:
            fen_row = ""
            empty_count = 0
            for piece in row:
                if piece == '':
                    empty_count += 1
                else:
                    if empty_count > 0:
                        fen_row += str(empty_count)
                        empty_count = 0
                    # 将棋子转换为FEN表示
                    fen_piece = piece[1] if piece[0] == 'r' else piece[1].lower()
                    fen_row += fen_piece
            if empty_count > 0:
                fen_row += str(empty_count)
            fen_rows.append(fen_row)
        
        # 添加位置信息（这里简化，只返回棋盘部分）
        return "/".join(fen_rows)
    
    def generate_surface_fen(self):
        """生成表面FEN字符串（显示给玩家的布局）"""
        fen_rows = []
        for row in self.surface_board:
            fen_row = ""
            empty_count = 0
            for piece in row:
                if piece == '':
                    empty_count += 1
                else:
                    if empty_count > 0:
                        fen_row += str(empty_count)
                        empty_count = 0
                    # 将棋子转换为FEN表示
                    if piece[1] == 'X':  # 暗子
                        fen_piece = 'X' if piece[0] == 'r' else 'x'
                    else:
                        fen_piece = piece[1] if piece[0] == 'r' else piece[1].lower()
                    fen_row += fen_piece
            if empty_count > 0:
                fen_row += str(empty_count)
            fen_rows.append(fen_row)
        
        # 添加位置信息（这里简化，只返回棋盘部分）
        return "/".join(fen_rows)
    
    def get_piece_at(self, row, col):
        """获取指定位置的棋子"""
        if 0 <= row < 10 and 0 <= col < 9:
            return self.board[row][col]
        return None
    
    def select_piece(self, row, col):
        """选择棋子"""
        piece = self.get_piece_at(row, col)
        
        if piece and piece[0] == self.current_player:
            self.selected_piece = (row, col)
            self.valid_moves = self.get_valid_moves(row, col)
            return True
        return False
    
    def get_valid_moves(self, row, col):
        """获取有效移动位置"""
        moves = []
        piece = self.get_piece_at(row, col)
        if not piece:
            return moves
        
        # 如果是暗子，可以移动到任何没有己方棋子的位置
        if piece[1] == 'X':
            for r in range(10):
                for c in range(9):
                    target = self.get_piece_at(r, c)
                    # 可以移动到空位或对方棋子位置
                    if not target or target[0] != self.current_player:
                        moves.append((r, c))
            return moves
        
        # 对于明子，这里简化移动规则（实际象棋规则更复杂）
        # 这里只实现简单的移动逻辑
        piece_type = piece[1]
        
        # 车和炮的移动（简化版）
        if piece_type in ['R', 'C']:
            # 水平方向
            for c in range(9):
                if c != col:
                    target = self.get_piece_at(row, c)
                    if not target or target[0] != self.current_player:
                        moves.append((row, c))
            
            # 垂直方向
            for r in range(10):
                if r != row:
                    target = self.get_piece_at(r, col)
                    if not target or target[0] != self.current_player:
                        moves.append((r, col))
        
        # 马移动（简化版）
        elif piece_type == 'N':
            knight_moves = [
                (row-2, col-1), (row-2, col+1),
                (row-1, col-2), (row-1, col+2),
                (row+1, col-2), (row+1, col+2),
                (row+2, col-1), (row+2, col+1)
            ]
            for r, c in knight_moves:
                if 0 <= r < 10 and 0 <= c < 9:
                    target = self.get_piece_at(r, c)
                    if not target or target[0] != self.current_player:
                        moves.append((r, c))
        
        # 兵移动（简化版）
        elif piece_type == 'P':
            if piece[0] == 'r':  # 红方兵
                if row > 0: moves.append((row-1, col))  # 向上
            else:  # 黑方兵
                if row < 9: moves.append((row+1, col))  # 向下
            if col > 0: moves.append((row, col-1))  # 向左
            if col < 8: moves.append((row, col+1))  # 向右
        
        # 将移动（简化版）
        elif piece_type == 'K':
            king_moves = [
                (row-1, col), (row+1, col),
                (row, col-1), (row, col+1)
            ]
            for r, c in king_moves:
                if 0 <= r < 10 and 0 <= c < 9:
                    target = self.get_piece_at(r, c)
                    if not target or target[0] != self.current_player:
                        moves.append((r, c))
        
        return moves
    
    def move_piece(self, to_row, to_col):
        """移动棋子"""
        if not self.selected_piece or (to_row, to_col) not in self.valid_moves:
            return False
        
        from_row, from_col = self.selected_piece
        piece = self.board[from_row][from_col]
        
        # 保存移动历史
        self.history.append({
            'from': (from_row, from_col),
            'to': (to_row, to_col),
            'piece': piece,
            'captured': self.board[to_row][to_col]
        })
        
        # 移动棋子
        self.board[to_row][to_col] = piece
        self.board[from_row][from_col] = ''
        
        # 同时更新隐藏棋盘
        hidden_piece = self.hidden_board[from_row][from_col]
        self.hidden_board[to_row][to_col] = hidden_piece
        self.hidden_board[from_row][from_col] = ''
        
        # 如果是暗子，翻开棋子（转为明子）
        if piece[1] == 'X':
            # 使用隐藏棋盘中的实际棋子类型
            actual_piece = self.hidden_board[to_row][to_col]
            self.board[to_row][to_col] = actual_piece
        
        # 检查是否将死对方将帅
        self.check_game_over()
        
        # 切换玩家
        self.current_player = 'b' if self.current_player == 'r' else 'r'
        self.selected_piece = None
        self.valid_moves = []
        return True
    
    def check_game_over(self):
        """检查游戏是否结束"""
        red_king = False
        black_king = False
        
        for row in self.hidden_board:  # 使用隐藏棋盘检查将帅
            for piece in row:
                if piece == 'rK':
                    red_king = True
                elif piece == 'bK':
                    black_king = True
        
        if not red_king:
            self.game_over = True
            self.winner = 'b'
        elif not black_king:
            self.game_over = True
            self.winner = 'r'
    
    def draw_board(self):
        """绘制棋盘和棋子"""
        # 缩放棋盘
        scaled_board = pygame.transform.scale(self.board_img, self.scaled_board_size)
        self.screen.blit(scaled_board, (0, 0))
        
        # 绘制棋子
        for row in range(10):
            for col in range(9):
                piece = self.board[row][col]
                if piece:
                    # 计算缩放后的位置
                    x = int(self.offset[0] * self.scale_factor + col * GRID_SIZE * self.scale_factor)
                    y = int(self.offset[1] * self.scale_factor + row * GRID_SIZE * self.scale_factor)
                    
                    # 缩放棋子
                    piece_img = self.piece_images.get(piece)  # 使用get避免KeyError
                    if not piece_img:
                        # 如果找不到棋子图片，创建默认图片
                        piece_img = self.create_default_piece(piece)
                        self.piece_images[piece] = piece_img
                    
                    scaled_piece = pygame.transform.scale(piece_img, 
                                                         (self.scaled_piece_size, 
                                                          self.scaled_piece_size))
                    
                    # 绘制棋子
                    piece_rect = scaled_piece.get_rect(center=(x + GRID_SIZE * self.scale_factor // 2, 
                                                              y + GRID_SIZE * self.scale_factor // 2))
                    self.screen.blit(scaled_piece, piece_rect)
        
        # 绘制选中的棋子高亮
        if self.selected_piece:
            row, col = self.selected_piece
            x = int(self.offset[0] * self.scale_factor + col * GRID_SIZE * self.scale_factor)
            y = int(self.offset[1] * self.scale_factor + row * GRID_SIZE * self.scale_factor)
            
            highlight = pygame.Surface((GRID_SIZE * self.scale_factor, GRID_SIZE * self.scale_factor), pygame.SRCALPHA)
            highlight.fill(HIGHLIGHT)
            self.screen.blit(highlight, (x, y))
            
            # 绘制有效移动位置
            for move in self.valid_moves:
                r, c = move
                x = int(self.offset[0] * self.scale_factor + c * GRID_SIZE * self.scale_factor)
                y = int(self.offset[1] * self.scale_factor + r * GRID_SIZE * self.scale_factor)
                
                hint = pygame.Surface((GRID_SIZE * self.scale_factor, GRID_SIZE * self.scale_factor), pygame.SRCALPHA)
                hint.fill(MOVE_HINT)
                self.screen.blit(hint, (x, y))
        
        # 绘制当前玩家提示
        player_text = "红方回合" if self.current_player == 'r' else "黑方回合"
        text_color = RED if self.current_player == 'r' else BLACK
        text = self.font.render(player_text, True, text_color)
        self.screen.blit(text, (10, 10))
        
        
        
        # 绘制表面FEN
        surface_fen = self.generate_surface_fen()
        # 将FEN字符串分成多行显示
        fen_lines = []
        max_len = 100  
        for i in range(0, len(surface_fen), max_len):
            fen_lines.append(surface_fen[i:i+max_len])
        
        for i, line in enumerate(fen_lines):
            fen_text = self.small_font.render(f"表面FEN: {line}", True, FEN_TEXT)
            self.screen.blit(fen_text, (10, 40 + i * 20))
        
        # 如果游戏结束，显示获胜信息
        if self.game_over:
            winner_text = "红方获胜!" if self.winner == 'r' else "黑方获胜!"
            text_color = RED if self.winner == 'r' else BLACK
            
            # 创建半透明背景
            overlay = pygame.Surface(self.scaled_board_size, pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 150))
            self.screen.blit(overlay, (0, 0))
            
            # 显示获胜文本 - 修改点2：使用支持中文的字体
            text = self.large_font.render(winner_text, True, text_color)
            text_rect = text.get_rect(center=(self.scaled_board_size[0]//2, self.scaled_board_size[1]//2))
            self.screen.blit(text, text_rect)
            
            # 显示重新开始提示
            restart_text = self.medium_font.render("按 R 键重新开始游戏", True, (255, 255, 255))
            restart_rect = restart_text.get_rect(center=(self.scaled_board_size[0]//2, self.scaled_board_size[1]//2 + 60))
            self.screen.blit(restart_text, restart_rect)
    
    def create_default_piece(self, piece_code):
        """创建默认棋子图片（当找不到指定棋子时使用）"""
        color = piece_code[0]
        piece_type = piece_code[1] if len(piece_code) > 1 else '?'
        
        # 创建棋子表面
        piece_surface = pygame.Surface((PIECE_SIZE, PIECE_SIZE), pygame.SRCALPHA)
        
        # 绘制棋子背景
        bg_color = RED if color == 'r' else (50, 50, 50)
        pygame.draw.circle(piece_surface, bg_color, (PIECE_SIZE//2, PIECE_SIZE//2), PIECE_SIZE//2 - 2)
        pygame.draw.circle(piece_surface, (240, 240, 240), 
                         (PIECE_SIZE//2, PIECE_SIZE//2), PIECE_SIZE//2 - 4)
        
        # 绘制棋子文字
        piece_names = {
            'R': '车', 'N': '马', 'B': '相', 'A': '士', 
            'K': '帅', 'C': '炮', 'P': '兵', 'X': '?'
        }
        text_color = RED if color == 'r' else BLACK
        piece_text = piece_names.get(piece_type, '?')
        
        # 尝试使用系统支持的中文字体
        try:
            # 优先使用已初始化的字体
            if hasattr(self, 'font'):
                font = pygame.font.SysFont(FONT_NAME, 30)
            else:
                font = pygame.font.SysFont(FONT_NAME, 30)
        except:
            # 如果字体加载失败，使用默认字体
            font = pygame.font.Font(None, 30)
        
        text = font.render(piece_text, True, text_color)
        text_rect = text.get_rect(center=(PIECE_SIZE//2, PIECE_SIZE//2))
        piece_surface.blit(text, text_rect)
        
        return piece_surface
    
    def handle_resize(self, event):
        """处理窗口大小调整事件"""
        new_width, new_height = event.w, event.h
        
        # 计算缩放因子
        self.scale_factor = min(new_width / BOARD_SIZE[0], new_height / BOARD_SIZE[1])
        self.scaled_board_size = (int(BOARD_SIZE[0] * self.scale_factor), 
                                 int(BOARD_SIZE[1] * self.scale_factor))
        self.scaled_piece_size = int(PIECE_SIZE * self.scale_factor)
        self.offset = (int(BOARD_OFFSET[0] * self.scale_factor), 
                      int(BOARD_OFFSET[1] * self.scale_factor))
        
        # 重新创建窗口
        self.screen = pygame.display.set_mode((new_width, new_height), pygame.RESIZABLE)
    
    def handle_click(self, pos):
        """处理鼠标点击事件"""
        if self.game_over:
            return
        
        # 计算点击的棋盘位置
        x, y = pos
        col = int((x - self.offset[0]) / (GRID_SIZE * self.scale_factor))
        row = int((y - self.offset[1]) / (GRID_SIZE * self.scale_factor))
        
        # 确保位置在棋盘范围内
        if 0 <= row < 10 and 0 <= col < 9:
            if self.selected_piece:
                # 尝试移动棋子
                if self.move_piece(row, col):
                    return
                else:
                    # 如果移动失败，尝试选择新棋子
                    self.select_piece(row, col)
            else:
                # 选择棋子
                self.select_piece(row, col)
    
    def run(self):
        """运行游戏主循环"""
        clock = pygame.time.Clock()
        
        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()
                
                elif event.type == pygame.VIDEORESIZE:
                    self.handle_resize(event)
                
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    if event.button == 1:  # 左键点击
                        self.handle_click(event.pos)
                
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_r:  # 按R键重置游戏
                        self.reset_game()
                    elif event.key == pygame.K_f:  # 按F键打印FEN
                        print("隐藏FEN:", self.generate_hidden_fen())
                        print("表面FEN:", self.generate_surface_fen())
                    elif event.key == pygame.K_ESCAPE:  # 按ESC键退出
                        pygame.quit()
                        sys.exit()
            
            # 绘制游戏
            self.screen.fill((50, 50, 50))
            self.draw_board()
            pygame.display.flip()
            clock.tick(60)

if __name__ == "__main__":
    game = ChessGame()
    game.run()