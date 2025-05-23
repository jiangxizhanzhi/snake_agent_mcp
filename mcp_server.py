import asyncio
import json
from enum import Enum
import time
from mcp.server.fastmcp import FastMCP
from typing import Annotated
from pydantic import Field
import websockets
from websockets import ServerConnection
import threading
import logging
import sys


# 自定义类：将标准输出重定向到 logging
class StreamToLogger:
    def __init__(self, logger, level):
        self.logger = logger
        self.level = level
        # 保留原始 stdout/stderr 的 buffer 属性
        self.buffer = sys.__stdout__.buffer  # 或者 sys.__stderr__.buffer

    def write(self, message):
        if message.strip():
            self.logger.log(self.level, message.strip())

    def flush(self):
        pass

    # 防止其他属性访问报错（如 encoding 等）
    def __getattr__(self, attr):
        return getattr(sys.__stdout__, attr)


# 配置日志（同时输出到文件和屏幕）
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("my_app.log"),
        logging.StreamHandler()
    ]
)

# 获取根日志器
logger = logging.getLogger()

# 重定向标准输出和错误输出到日志
sys.stdout = StreamToLogger(logger, logging.INFO)  # 将 print 输出重定向为 INFO 级别
sys.stderr = StreamToLogger(logger, logging.ERROR)  # 将错误输出重定向为 ERROR 级别


# 捕获未处理的异常并记录到日志
def handle_exception(exc_type, exc_value, exc_traceback):
    logger.error("未捕获的异常:", exc_info=(exc_type, exc_value, exc_traceback))


sys.excepthook = handle_exception


class Position:
    def __init__(self, x: int, y: int):
        self.x = x
        self.y = y


class Direction(Enum):
    UP = 'up'
    DOWN = 'down'
    LEFT = 'left'
    RIGHT = 'right'


class GameState:
    def __init__(self):
        self.game_started = False
        self.auto_path_find = False
        self.direction = Direction.RIGHT
        self.score = 0
        self.food = Position(10, 10)
        self.snake = [Position(5, 5), Position(4, 5), Position(3, 5)]

    def to_dict(self) -> dict:
        return {
            "game_started": self.game_started,
            "auto_path_find": self.auto_path_find,
            "direction": self.direction.name,
            "score": self.score,
            "food": "x:  " + str(self.food.x) + " y: " + str(self.food.y),
            "snake": "x:  " + str(self.snake[0].x) + " y: " + str(self.snake[0].y),
            "grid_size": 20,
            "canvas_size": 400

        }


def check_collision(new_head: Position, snake_positions: list[Position], canvas_size: int):
    return (new_head.x < 0 or new_head.x >= canvas_size or new_head.y < 0 or new_head.y >= canvas_size or
            any(element.x == new_head.x and element.y == new_head.y for element in snake_positions))


class SnakeServer:
    def __init__(self):
        self.game_state = GameState()
        self.uri = "ws://localhost:8068"

    async def send_message(self, message: str):
        for client in connected:
            await client.send(message)

    def calculate_direction(self) -> Direction:
        head = self.game_state.snake[0]
        food = self.game_state.food
        grid_size = 20
        canvas_size = 400

        current_direction = self.game_state.direction
        possible_directions = list()

        if current_direction is Direction.RIGHT:
            possible_directions.append(Direction.RIGHT)
            possible_directions.append(Direction.UP)
            possible_directions.append(Direction.DOWN)
        elif current_direction is Direction.LEFT:
            possible_directions.append(Direction.LEFT)
            possible_directions.append(Direction.UP)
            possible_directions.append(Direction.DOWN)
        elif current_direction is Direction.UP:
            possible_directions.append(Direction.UP)
            possible_directions.append(Direction.LEFT)
            possible_directions.append(Direction.RIGHT)
        elif current_direction is Direction.DOWN:
            possible_directions.append(Direction.DOWN)
            possible_directions.append(Direction.LEFT)
            possible_directions.append(Direction.RIGHT)

        def dangerous_direction(direction: Direction) -> bool:
            possible_head = self.move_head(head, direction, grid_size)
            return check_collision(possible_head, self.game_state.snake, canvas_size)

        safe_directions = [direction for direction in possible_directions if not dangerous_direction(direction)]

        target_direction = possible_directions[0] if not safe_directions \
            else self.find_best_direction(head, food, safe_directions, grid_size)
        return target_direction if target_direction else possible_directions[0]

    def move_head(self, head: Position, direction: Direction, grid_size: int) -> Position:
        if direction is Direction.LEFT:
            return Position(head.x - grid_size, head.y)
        elif direction is Direction.RIGHT:
            return Position(head.x + grid_size, head.y)
        elif direction is Direction.UP:
            return Position(head.x, head.y - grid_size)
        else:
            return Position(head.x, head.y + grid_size)

    def find_best_direction(self, head: Position, food: Position, directions: list, grid_size: int) -> Direction:
        best_dir = directions[0]
        min_distance = 4000 * 4000

        for direction in directions:
            new_head = self.move_head(head, direction, grid_size)
            if not new_head:
                continue
            else:
                dy = food.x - new_head.x
                dx = food.y - new_head.y
                current_distance = dy * dy + dx * dx
                if current_distance < min_distance:
                    min_distance = current_distance
                    best_dir = direction
        return best_dir


mcp = FastMCP("snake-server")
snake_server = SnakeServer()


@mcp.tool()
def calculate_bmi(weight_kg: float, height_m: float) -> float:
    """Calculate BMI given weight in kg and height in meters"""
    return weight_kg / (height_m ** 2)


@mcp.tool()
async def move_step(
        direction: Annotated[str, Field(description="移动方向", enum=["up", "down", "left", "right"])]) -> str:
    """
    将贪吃蛇往指定方向移动一步
    :param direction:移动方向，取值为up、down、left、right
    :return: 贪吃蛇向指定方向移动后的状态，包括最新的贪吃蛇坐标、食物的坐标、游戏是否开始、游戏得分等。
    """
    target_direction = Direction(direction)
    snake_server.game_state.direction = target_direction
    await snake_server.send_message(json.dumps({
        "type": "direction",
        "direction": target_direction.value,
        "timestamp": time.time()
    }))
    return "方向已更新,当前状态为" + json.dumps(snake_server.game_state.to_dict())


@mcp.tool()
def get_state() -> str:
    """
    获取当前贪吃蛇游戏的状态，包括贪吃蛇坐标、食物坐标、游戏是否开始、游戏得分等。
    :return: 贪吃蛇游戏的状态，包括贪吃蛇坐标、食物坐标、游戏是否开始、游戏得分等。
    """
    return json.dumps(snake_server.game_state.to_dict())


@mcp.tool()
async def auto_path_find() -> str:
    """
    开启当前贪吃蛇游戏的自动寻路功能，开启后，贪吃蛇会自动移动寻找食物。
    :return:自动移动是否激活成功，并返回当前贪吃蛇游戏的状态，包括贪吃蛇坐标，食物坐标，游戏是否开始，游戏得分等。
    """
    snake_server.game_state.auto_path_find = True
    await snake_server.send_message(json.dumps({
        "type": "get_state",
        "timestamp": time.time()
    }))
    return "自动移动已激活，当前状态为" + json.dumps(snake_server.game_state.to_dict())


@mcp.tool()
async def start_game() -> str:
    """
    启动当前贪吃蛇游戏
    :return: 返回是否成功启动当前贪吃蛇游戏，并返回启动后，当前贪吃蛇游戏的状态，包括贪吃蛇坐标、食物坐标、游戏是否开始、游戏得分等。
    """
    snake_server.game_state.game_started = True
    await snake_server.send_message(json.dumps({
        "type": "start"
    }))
    await asyncio.sleep(1)
    return "游戏已开始，当前状态为" + json.dumps(snake_server.game_state.to_dict())


@mcp.tool()
async def end_game() -> str:
    snake_server.game_state.game_started = False
    snake_server.game_state.auto_path_find = False

    await snake_server.send_message(json.dumps({
        "type": "end"
    }))
    return "游戏已结束，当前状态为" + json.dumps(snake_server.game_state.to_dict())


connected: set[ServerConnection] = set()


async def handler(websocket: ServerConnection):
    global connected
    connected.add(websocket)
    try:
        async for message in websocket:
            print(f"rev from snake ：{message}")
            data = json.loads(message)
            if data["type"] == 'state':
                snake_server.game_state.snake = [Position(int(snake_node["x"]), int(snake_node["y"])) for snake_node in
                                                 data["snake"]]
                snake_server.game_state.food = Position(int(data["food"]["x"]), int(data["food"]["y"]))
                snake_server.game_state.score = int(data["score"])
                if data["direction"]["dx"] > 0:
                    snake_server.game_state.direction = Direction.RIGHT
                elif data["direction"]["dx"] < 0:
                    snake_server.game_state.direction = Direction.LEFT
                elif data["direction"]["dy"] > 0:
                    snake_server.game_state.direction = Direction.DOWN
                else:
                    snake_server.game_state.direction = Direction.UP
            if snake_server.game_state.auto_path_find:
                target_direction = snake_server.calculate_direction()
                await asyncio.sleep(0.5)

                tasks = []
                for client in connected:
                    tasks.append(client.send(json.dumps({
                        'type': 'direction',
                        'direction': target_direction.value,
                        'timestamp': time.time()
                    })))
                await asyncio.gather(*tasks, return_exceptions=True)

    finally:
        connected.discard(websocket)  # 更安全的移除方式


def run_mcp():
    mcp.run()


async def start_websocket():
    threading.Thread(target=run_mcp).start()
    start_server = await websockets.serve(handler, "localhost", 8766)

    await start_server.serve_forever()


asyncio.run(start_websocket())
