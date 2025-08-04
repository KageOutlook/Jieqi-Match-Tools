import pygame
import os
import random
import sys
import subprocess
import threading
import time
from pygame.locals import *

# 初始化pygame
pygame.init()
FONT_NAME = "simhei"  

# 常量定义
BOARD_SIZE = (600, 650)
PIECE_SIZE = 52
GRID_SIZE = BOARD_SIZE[0] // 9
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
        
        # UCI引擎相关
        self.engine = None
        self.engine_path = os.path.join('resource', 'engine', 'test1_2023.exe')
        self.engine_thinking = False
        self.last_engine_move_time = 0
        self.move_notations = []  # 存储所有走法记录
        self.engine_side = 'b'  # 引擎控制黑方
        self.engine_thread = None
        
        # 添加自动判决相关变量
        self.consecutive_low_eval = 0  # 连续低评分计数
        self.last_engine_eval = 0     # 上次引擎评分
        self.last_eval_depth = 0      # 上次评估深度
        
        # 添加游戏轮次相关变量
        self.round_count = 0          # 当前轮次
        self.game_count = 1           # 当前轮次中的游戏局数 (1 或 2)
        self.hidden_fen = None        # 当前轮次使用的隐藏FEN
        self.next_game_time = 0       # 下一局开始时间
        self.next_round_time = 0      # 下一轮开始时间
        self.max_rounds = 2          # 最大轮次限制
        self.finished = False         # 标记是否已完成所有轮次
        self.exit_time = None         # 退出时间
        
        # 初始化字体
        self.init_fonts()
        
        # 初始化棋盘状态
        self.reset_game(new_round=True)
        
        # 创建窗口
        self.create_window()
        
        # 加载图片
        self.load_images()
        
        # 初始化引擎
        self.init_engine()
    
    def init_engine(self):
        """初始化UCI引擎"""
        try:
            # 启动引擎进程
            self.engine = subprocess.Popen(
                self.engine_path,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                bufsize=1
            )
            
            # 发送初始化命令
            self.send_engine_command("uci")
            self.send_engine_command("isready")
            
            # 等待引擎准备好
            while True:
                output = self.engine.stdout.readline().strip()
                print(f"Engine: {output}")
                if output == "readyok":
                    print("Engine is ready")
                    break
        except Exception as e:
            print(f"Error initializing engine: {e}")
            self.engine = None
    
    def send_engine_command(self, command):
        """向引擎发送命令"""
        if self.engine and self.engine.stdin:
            print(f"To Engine: {command}")
            self.engine.stdin.write(command + "\n")
            self.engine.stdin.flush()
    
    def read_engine_output(self):
        """读取引擎输出"""
        if self.engine and self.engine.stdout:
            return self.engine.stdout.readline().strip()
        return ""
    
    def convert_to_uci_move(self, from_row, from_col, to_row, to_col, piece):
        """将棋盘坐标转换为UCI格式的走法（翻转行坐标）"""
        col_chars = "abcdefghi"
        from_char = col_chars[from_col]
        from_row_flipped = 9 - from_row  # 翻转行坐标
        to_char = col_chars[to_col]
        to_row_flipped = 9 - to_row    # 翻转行坐标
        
        # 暗子移动需要添加棋子类型后缀
        if piece[1] == 'X':
            # 获取隐藏棋盘中的实际棋子类型
            actual_piece = self.hidden_board[to_row][to_col]
            if actual_piece:
                piece_type = actual_piece[1]
                # 如果实际棋子是黑方棋子，使用小写字母表示
                if actual_piece[0] == 'b':
                    piece_type = piece_type.lower()
                return f"{from_char}{from_row_flipped}{to_char}{to_row_flipped}{piece_type}"
        
        # 明子移动只有四个字符
        return f"{from_char}{from_row_flipped}{to_char}{to_row_flipped}"
    
    def convert_from_uci_move(self, move_str):
        """将UCI格式的走法转换为棋盘坐标（翻转行坐标）"""
        if len(move_str) < 4:
            return None
        
        col_chars = "abcdefghi"
        from_col = col_chars.index(move_str[0])
        from_row_flipped = int(move_str[1])
        to_col = col_chars.index(move_str[2])
        to_row_flipped = int(move_str[3])
        
        # 翻转行坐标
        from_row = 9 - from_row_flipped
        to_row = 9 - to_row_flipped
        
        return (from_row, from_col, to_row, to_col)
    
    def get_position_command(self):
        """生成position命令"""
        if not self.move_notations:
            return "position startpos"
        
        moves_str = " ".join(self.move_notations)
        return f"position startpos moves {moves_str}"
    
    def engine_move(self):
        """让引擎计算并执行一步棋"""
        if not self.engine or self.game_over:
            return
        
        # 生成position命令
        position_cmd = self.get_position_command()
        self.send_engine_command(position_cmd)
        
        # 发送go命令
        self.send_engine_command("go movetime 3000")  # 3秒思考时间
        
        # 读取引擎输出
        bestmove = None
        current_depth = 0
        current_eval = 0
        start_time = time.time()
        while time.time() - start_time < 5:  # 最多等待5秒
            output = self.read_engine_output()
            if not output:
                time.sleep(0.01)
                continue
                
            print(f"Engine: {output}")
            
            # 解析引擎深度和评分
            if output.startswith("info"):
                parts = output.split()
                try:
                    if "depth" in parts:
                        depth_index = parts.index("depth") + 1
                        current_depth = int(parts[depth_index])
                    if "score" in parts and "cp" in parts:
                        score_index = parts.index("cp") + 1
                        current_eval = int(parts[score_index])
                    # 添加对杀棋(mate)分数的解析
                    elif "score" in parts and "mate" in parts:
                        mate_index = parts.index("mate") + 1
                        mate_value = int(parts[mate_index])
                        # 正数表示引擎执方将死对手，负数表示对手将死引擎执方
                        current_eval = 10000 if mate_value > 0 else -10000
                except (ValueError, IndexError):
                    pass
                
            if output.startswith("bestmove"):
                parts = output.split()
                if len(parts) > 1:
                    bestmove = parts[1]
                    break
        
        if bestmove:
            print(f"Engine bestmove: {bestmove}")
            # 解析引擎走法
            move_coords = self.convert_from_uci_move(bestmove)
            if move_coords:
                from_row, from_col, to_row, to_col = move_coords
                # 执行移动
                self.do_move(from_row, from_col, to_row, to_col)
        
        # 自动判决逻辑
        if current_depth > 15:
            # 1. 如果评分绝对值超过1000，自动判胜
            if abs(current_eval) > 1000:
                self.game_over = True
                # 根据当前引擎执方判断获胜方
                # 注意：引擎评分是从自身视角出发的
                if current_eval > 0:
                    # 正分表示引擎执方优势
                    self.winner = self.engine_side
                else:
                    # 负分表示对手优势
                    self.winner = 'r' if self.engine_side == 'b' else 'b'
                print(f"Game over! Winner: {'Red' if self.winner == 'r' else 'Black'} due to high evaluation ({current_eval}) at depth {current_depth}")
            
            # 2. 记录评估值用于连续判断
            self.last_engine_eval = current_eval
            self.last_eval_depth = current_depth
            
            # 3. 检查是否满足连续三回合评分小于20的条件
            if abs(current_eval) < 20:
                self.consecutive_low_eval += 1
                print(f"Consecutive low evaluations: {self.consecutive_low_eval}")
            else:
                # 如果评分大于20，重置连续计数
                self.consecutive_low_eval = 0
            
            # 如果连续三（3评估引擎回合＋3另外一方回合）回合评分绝对值小于20，判和棋
            if self.consecutive_low_eval >= 6:
                self.game_over = True
                self.winner = None  # None表示和棋
                print(f"Game over! Draw due to three consecutive low evaluations ({current_eval}) at depth {current_depth}")
        
        self.engine_thinking = False
    
    def start_engine_thread(self):
        """启动引擎线程"""
        if self.engine_thinking or not self.engine:
            return
        
        self.engine_thinking = True
        self.engine_thread = threading.Thread(target=self.engine_move)
        self.engine_thread.daemon = True
        self.engine_thread.start()
    
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
                    # 如果加载失败，打印错误信息
                    print(f"棋子图片加载失败: {color}{piece}.bmp")
                    # 不再创建默认棋子，因为我们假设图片一定存在
    
    def reset_game(self, new_round=False):
        """重置游戏状态"""
        if new_round:
            # 新的一轮，生成新的隐藏棋盘（实际棋子布局）
            self.round_count += 1
            self.game_count = 1
            self.engine_side = 'b'  # 引擎执黑
            
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
            
            # 保存初始隐藏棋盘状态
            self.initial_hidden_board = [row[:] for row in self.hidden_board]
        
        # 初始化表面棋盘（显示给玩家的布局）
        if new_round:
            # 新轮次使用新生成的隐藏棋盘
            self.surface_board = [row[:] for row in self.hidden_board]  # 复制隐藏棋盘
        else:
            # 同一轮的第二局，使用初始隐藏棋盘状态
            self.hidden_board = [row[:] for row in self.initial_hidden_board]
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
        self.move_notations = []  # 重置走法记录
        
        # 重置自动判决相关变量
        self.consecutive_low_eval = 0
        self.last_engine_eval = 0
        self.last_eval_depth = 0
        
        # 记录隐藏FEN
        self.hidden_fen = self.generate_hidden_fen()
        print(f"新游戏开始! 轮次: {self.round_count}, 局数: {self.game_count}")
    
    def start_next_game(self):
        """开始同一轮中的第二局游戏"""
        self.game_count = 2
        self.engine_side = 'r'  # 第二局引擎执红
        
        # 重置游戏状态但不生成新的隐藏棋盘
        self.hidden_board = [row[:] for row in self.initial_hidden_board]  # 使用初始隐藏棋盘
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
        self.move_notations = []  # 重置走法记录
        
        # 重置自动判决相关变量
        self.consecutive_low_eval = 0
        self.last_engine_eval = 0
        self.last_eval_depth = 0
        
        print(f"开始第{self.round_count}轮第{self.game_count}局游戏")
    
    def start_new_round(self):
        """开始新的一轮游戏（包含两局）"""
        # 检查是否已完成所有轮次
        if self.round_count >= self.max_rounds:
            print(f"已完成{self.max_rounds}轮游戏，程序将退出。")
            self.finished = True
            self.exit_time = time.time() + 5  # 5秒后退出
            return
        
        self.reset_game(new_round=True)
        print(f"开始第{self.round_count}轮游戏")
    
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
        """获取有效移动位置 - 所有棋子都使用暗子移动规则"""
        moves = []
        piece = self.get_piece_at(row, col)
        if not piece:
            return moves
        
        # 所有棋子都按照暗子的移动规则：可以移动到任何没有己方棋子的位置
        for r in range(10):
            for c in range(9):
                target = self.get_piece_at(r, c)
                # 如果目标位置没有棋子，或者是对方棋子，则可以移动（不能移动到己方棋子位置）
                if not target or target[0] != piece[0]:
                    moves.append((r, c))
        
        return moves
    
    def do_move(self, from_row, from_col, to_row, to_col):
        """执行移动的核心方法"""
        piece = self.board[from_row][from_col]
        if not piece:
            return False
        
        # 检查目标位置是否有效
        if (to_row, to_col) not in self.get_valid_moves(from_row, from_col):
            return False
        
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
        
        # 生成UCI格式的走法记录
        move_notation = self.convert_to_uci_move(from_row, from_col, to_row, to_col, piece)
        self.move_notations.append(move_notation)
        print(f"Recorded move: {move_notation}")
        
        # 检查是否将死对方将帅
        self.check_game_over()
        
        # 切换玩家
        self.current_player = 'b' if self.current_player == 'r' else 'r'
        self.selected_piece = None
        self.valid_moves = []
        
        # 记录最后移动时间
        self.last_engine_move_time = time.time()
        return True
    
    def move_piece(self, to_row, to_col):
        """移动棋子"""
        if not self.selected_piece:
            return False
        
        from_row, from_col = self.selected_piece
        return self.do_move(from_row, from_col, to_row, to_col)
    
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
        
        # 如果游戏结束，设置下一局开始时间
        if self.game_over:
            if self.game_count == 1:
                # 第一局结束，2秒后开始第二局
                self.next_game_time = time.time() + 2
            elif self.game_count == 2:
                # 第二局结束，3秒后开始新的一轮
                self.next_round_time = time.time() + 3
    
    def draw_board(self):
        """绘制棋盘和棋子（翻转行坐标）"""
        # 缩放棋盘
        scaled_board = pygame.transform.scale(self.board_img, self.scaled_board_size)
        self.screen.blit(scaled_board, (0, 0))
        
        # 绘制棋子（翻转行坐标）
        for row in range(10):
            for col in range(9):
                piece = self.board[row][col]
                if piece:
                    # 计算缩放后的位置（翻转行坐标）
                    flipped_row = 9 - row  # 翻转行坐标
                    x = int(self.offset[0] * self.scale_factor + col * GRID_SIZE * self.scale_factor)
                    y = int(self.offset[1] * self.scale_factor + flipped_row * GRID_SIZE * self.scale_factor)
                    
                    # 缩放棋子
                    piece_img = self.piece_images.get(piece)
                    if piece_img:
                        scaled_piece = pygame.transform.scale(piece_img, 
                                                             (self.scaled_piece_size, 
                                                              self.scaled_piece_size))
                        
                        # 绘制棋子
                        piece_rect = scaled_piece.get_rect(center=(x + GRID_SIZE * self.scale_factor // 2, 
                                                              y + GRID_SIZE * self.scale_factor // 2))
                        self.screen.blit(scaled_piece, piece_rect)
        
        # 绘制选中的棋子高亮（翻转行坐标）
        if self.selected_piece:
            row, col = self.selected_piece
            flipped_row = 9 - row  # 翻转行坐标
            x = int(self.offset[0] * self.scale_factor + col * GRID_SIZE * self.scale_factor)
            y = int(self.offset[1] * self.scale_factor + flipped_row * GRID_SIZE * self.scale_factor)
            
            highlight = pygame.Surface((GRID_SIZE * self.scale_factor, GRID_SIZE * self.scale_factor), pygame.SRCALPHA)
            highlight.fill(HIGHLIGHT)
            self.screen.blit(highlight, (x, y))
            
            # 绘制有效移动位置（翻转行坐标）
            for move in self.valid_moves:
                r, c = move
                flipped_r = 9 - r  # 翻转行坐标
                x = int(self.offset[0] * self.scale_factor + c * GRID_SIZE * self.scale_factor)
                y = int(self.offset[1] * self.scale_factor + flipped_r * GRID_SIZE * self.scale_factor)
                
                hint = pygame.Surface((GRID_SIZE * self.scale_factor, GRID_SIZE * self.scale_factor), pygame.SRCALPHA)
                hint.fill(MOVE_HINT)
                self.screen.blit(hint, (x, y))
        
        # 绘制当前玩家提示
        player_text = "红方回合" if self.current_player == 'r' else "黑方回合"
        text_color = RED if self.current_player == 'r' else BLACK
        text = self.font.render(player_text, True, text_color)
        self.screen.blit(text, (10, 10))
        
        # 绘制引擎状态
        if self.engine:
            engine_text = "引擎: 已加载"
            if self.engine_thinking:
                engine_text = "引擎: 思考中..."
            text = self.font.render(engine_text, True, (0, 100, 0))
            self.screen.blit(text, (self.scaled_board_size[0] - 150, 10))
        
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
        
        # 绘制最后评估信息
        if self.last_eval_depth > 0:
            eval_text = f"深度: {self.last_eval_depth} 评分: {self.last_engine_eval}"
            text = self.font.render(eval_text, True, (0, 100, 0))
            self.screen.blit(text, (self.scaled_board_size[0] - 250, 40))
        
        # 绘制连续低评分计数
        eval_text = f"连续低评分: {self.consecutive_low_eval}"
        text = self.font.render(eval_text, True, (0, 100, 0))
        self.screen.blit(text, (self.scaled_board_size[0] - 200, 70))
        
        # 绘制轮次和局数信息
        round_text = f"轮次: {self.round_count}/{self.max_rounds} 局数: {self.game_count}/2"
        text = self.font.render(round_text, True, (150, 0, 150))
        self.screen.blit(text, (self.scaled_board_size[0] - 200, self.scaled_board_size[1] - 30))
        
        # 绘制隐藏FEN
        if self.hidden_fen:
            hidden_text = f"隐藏FEN: {self.hidden_fen[:40]}..."  # 只显示部分
            text = self.small_font.render(hidden_text, True, (100, 0, 100))
            self.screen.blit(text, (10, self.scaled_board_size[1] - 30))
        
        # 如果游戏结束，显示获胜信息
        if self.game_over:
            if self.winner is None:
                winner_text = "和棋!"
                text_color = (100, 100, 100)  # 灰色表示和棋
            else:
                winner_text = "红方获胜!" if self.winner == 'r' else "黑方获胜!"
                text_color = RED if self.winner == 'r' else BLACK
            
            # 创建半透明背景
            overlay = pygame.Surface(self.scaled_board_size, pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 150))
            self.screen.blit(overlay, (0, 0))
            
            # 显示获胜文本
            text = self.large_font.render(winner_text, True, text_color)
            text_rect = text.get_rect(center=(self.scaled_board_size[0]//2, self.scaled_board_size[1]//2))
            self.screen.blit(text, text_rect)
            
            # 显示重新开始提示
            if self.game_count == 1:
                restart_text = self.medium_font.render("2秒后开始第二局...", True, (255, 255, 255))
                restart_rect = restart_text.get_rect(center=(self.scaled_board_size[0]//2, self.scaled_board_size[1]//2 + 60))
                self.screen.blit(restart_text, restart_rect)
            else:
                restart_text = self.medium_font.render(f"3秒后开始第{self.round_count + 1}轮游戏...", True, (255, 255, 255))
                restart_rect = restart_text.get_rect(center=(self.scaled_board_size[0]//2, self.scaled_board_size[1]//2 + 60))
                self.screen.blit(restart_text, restart_rect)
            
            # 如果已完成所有轮次，显示结束信息
            if self.finished:
                final_text = self.medium_font.render(f"已完成{self.max_rounds}轮游戏，程序即将退出...", True, (255, 255, 0))
                final_rect = final_text.get_rect(center=(self.scaled_board_size[0]//2, self.scaled_board_size[1]//2 + 120))
                self.screen.blit(final_text, final_rect)
    
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
        """处理鼠标点击事件（翻转行坐标）"""
        if self.game_over or self.engine_thinking or self.finished:
            return
        
        # 计算点击的棋盘位置（翻转行坐标）
        x, y = pos
        col = int((x - self.offset[0]) / (GRID_SIZE * self.scale_factor))
        screen_row = int((y - self.offset[1]) / (GRID_SIZE * self.scale_factor))
        
        # 翻转行坐标：屏幕行号 -> 内部行号
        row = 9 - screen_row
        
        # 确保位置在棋盘范围内
        if 0 <= row < 10 and 0 <= col < 9:
            if self.selected_piece:
                # 尝试移动棋子
                if self.move_piece(row, col):
                    # 玩家移动后检查是否满足连续三回合条件
                    if self.last_eval_depth > 8 and abs(self.last_engine_eval) < 20:
                        self.consecutive_low_eval += 1
                        print(f"玩家移动后连续低评分计数: {self.consecutive_low_eval}")
                    else:
                        self.consecutive_low_eval = 0
                    
                    # 检查是否满足判和条件
                    if self.consecutive_low_eval >= 6:
                        self.game_over = True
                        self.winner = None
                        print(f"游戏结束! 和棋! 连续三回合评分小于20")
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
            current_time = time.time()
            
            # 检查是否需要退出程序
            if self.exit_time and current_time >= self.exit_time:
                if self.engine:
                    self.send_engine_command("quit")
                    self.engine.terminate()
                pygame.quit()
                sys.exit()
            
            # 检查是否需要自动开始第二局
            if self.game_over and self.game_count == 1 and current_time >= self.next_game_time:
                self.start_next_game()
            
            # 检查是否需要自动开始新的一轮
            if self.game_over and self.game_count == 2 and current_time >= self.next_round_time:
                self.start_new_round()
            
            # 检查是否需要引擎走棋
            if (self.engine and 
                self.current_player == self.engine_side and 
                not self.game_over and 
                not self.engine_thinking and 
                not self.finished and 
                current_time - self.last_engine_move_time > 3):
                self.start_engine_thread()
            
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    # 退出前关闭引擎
                    if self.engine:
                        self.send_engine_command("quit")
                        self.engine.terminate()
                    pygame.quit()
                    sys.exit()
                
                elif event.type == pygame.VIDEORESIZE:
                    self.handle_resize(event)
                
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    if event.button == 1:  # 左键点击
                        self.handle_click(event.pos)
                
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_r:  # 按R键重置游戏
                        self.start_new_round()
                    elif event.key == pygame.K_f:  # 按F键打印FEN
                        print("隐藏FEN:", self.generate_hidden_fen())
                        print("表面FEN:", self.generate_surface_fen())
                    elif event.key == pygame.K_ESCAPE:  # 按ESC键退出
                        if self.engine:
                            self.send_engine_command("quit")
                            self.engine.terminate()
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