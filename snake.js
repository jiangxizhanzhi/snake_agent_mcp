<!DOCTYPE html>
<html>
  <head>
    <title>贪吃蛇-豪华尊享版</title>
    <style>
      canvas {
        border: 3px solid #2c3e50;
        border-radius: 10px;
        background: linear-gradient(145deg, #ecf0f1, #dfe6e9);
      }

      #score-panel {
        font-size: 24px;
        margin: 15px 0;
        color: #2c3e50;
        font-family: Arial, sans-serif;
        text-shadow: 1px 1px 2px rgba(0, 0, 0, 0.1);
      }

      body {
        display: flex;
        flex-direction: column;
        align-items: center;
        background: #bdc3c7;
        min-height: 100vh;
        margin: 0;
        padding-top: 20px;
      }
    </style>
  </head>

  <body>
    <div id="score-panel">得分: 0</div>
    <canvas id="gameCanvas" width="400" height="400"></canvas>
    <script type="module">
      // 连接 snake - server
      const socket = new WebSocket("ws://localhost:8766");
      socket.onmessage = (event) => {
        console.log("[WS Received]", event.data);
        const data = JSON.parse(event.data); // 处理方向指令
        if (data.type === "direction") {
          switch (data.direction) {
            case "left":
              if (dx !== gridSize) {
                dx = -gridSize;
                dy = 0;
              }
              break;
            case "up":
              if (dy !== gridSize) {
                dx = 0;
                dy = -gridSize;
              }
              break;
            case "right":
              if (dx !== -gridSize) {
                dx = gridSize;
                dy = 0;
              }
              break;
            case "down":
              if (dy !== -gridSize) {
                dx = 0;
                dy = gridSize;
              }
              break;
          }
          gameStep(); // 执行一步
        } // 处理游戏开始指令
        else if (data.type === "start") {
          if (!gameStarted) {
            gameStarted = true;
            initGame(); // 发送状态到服务端
            sendStateToServer();
          }
        } // 处理游戏结束指令
        else if (data.type === "end") {
          // 发送状态到服务端
          sendStateToServer();
          if (gameStarted) {
            gameOver();
          }
        } // 获取状态
        else if (data.type === "get_state") {
          // 发送状态到服务端
          sendStateToServer();
        }
      };
      const canvas = document.getElementById("gameCanvas");
      const ctx = canvas.getContext("2d");
      const gridSize = 20;
      const initialSpeed = 100;
      // 颜色配置

      const colors = {
        snakeHead: "#3498db",
        snakeBody: "#2980b9",
        food: "#e74c3c",
        foodGlow: "rgba(231, 76, 60, 0.4)",
        eye: "#FFFFFF",
      };
      let snake = [];
      let food = {};
      let dx = gridSize;
      let dy = 0;
      let score = 0;
      let gameStarted = false;
      let autoMove = false; // 新增自动移动控制开关
      let isSetting = false; // 定时器注入开关
      let gameLoop;
      function initGame() {
        isSetting = false;
        snake = [
          { x: 5 * gridSize, y: 5 * gridSize },
          { x: 4 * gridSize, y: 5 * gridSize },
          { x: 3 * gridSize, y: 5 * gridSize },
        ];
        dx = gridSize;
        dy = 0;
        score = 0;
        document.getElementById("score-panel").textContent = `得分: ${score}`;
        generateFood();
        draw();
      }
      function generateFood() {
        food = {
          x: Math.floor(Math.random() * (canvas.width / gridSize)) * gridSize,
          y: Math.floor(Math.random() * (canvas.height / gridSize)) * gridSize,
          glow: 0, // 新增发光动画状态
        };
        while (snake.some((s) => s.x === food.x && s.y === food.y))
          generateFood();
      }
      function drawSnake() {
        snake.forEach((segment, index) => {
          const isHead = index === 0;
          const radius = (gridSize / 2) * (isHead ? 0.9 : 0.8);
          // 身体渐变

          const gradient = ctx.createLinearGradient(
            segment.x,
            segment.y,
            segment.x + gridSize,
            segment.y + gridSize
          );
          gradient.addColorStop(
            0,
            isHead ? colors.snakeHead : colors.snakeBody
          );
          gradient.addColorStop(
            1,
            isHead
              ? lightenColor(colors.snakeHead, 20)
              : lightenColor(colors.snakeBody, 20)
          );
          // 绘制身体

          ctx.beginPath();
          ctx.roundRect(
            segment.x + 1,
            segment.y + 1,
            gridSize - 2,
            gridSize - 2,
            isHead ? 8 : 6
          );
          ctx.fillStyle = gradient;
          ctx.shadowColor = "rgba(0,0,0,0.2)";
          ctx.shadowBlur = 5;
          ctx.fill();
        });
      }
      function drawFood() {
        // 发光动画
        food.glow = (food.glow + 0.05) % (Math.PI * 2);
        const glowSize = Math.sin(food.glow) * 3;
        // 外发光

        ctx.beginPath();
        ctx.arc(
          food.x + gridSize / 2,
          food.y + gridSize / 2,
          gridSize / 2 + glowSize,
          0,
          Math.PI * 2
        );
        ctx.fillStyle = colors.foodGlow;
        ctx.fill();
        // 食物主体

        ctx.beginPath();
        ctx.arc(
          food.x + gridSize / 2,
          food.y + gridSize / 2,
          gridSize / 2 - 2,
          0,
          Math.PI * 2
        );
        const gradient = ctx.createRadialGradient(
          food.x + gridSize / 2,
          food.y + gridSize / 2,
          0,
          food.x + gridSize / 2,
          food.y + gridSize / 2,
          gridSize / 2
        );
        gradient.addColorStop(0, lightenColor(colors.food, 20));
        gradient.addColorStop(1, colors.food);
        ctx.fillStyle = gradient;
        ctx.fill();
      }
      function draw() {
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        // 绘制网格背景

        drawGrid();
        drawSnake();
        drawFood();
      }
      function drawGrid() {
        ctx.strokeStyle = "rgba(0,0,0,0.05)";
        ctx.lineWidth = 0.5;
        for (let x = 0; x < canvas.width; x += gridSize) {
          ctx.beginPath();
          ctx.moveTo(x, 0);
          ctx.lineTo(x, canvas.height);
          ctx.stroke();
        }
        for (let y = 0; y < canvas.height; y += gridSize) {
          ctx.beginPath();
          ctx.moveTo(0, y);
          ctx.lineTo(canvas.width, y);
          ctx.stroke();
        }
      }
      function lightenColor(hex, percent) {
        const num = parseInt(hex.replace("#", ""), 16),
          amt = Math.round(2.55 * percent),
          R = (num >> 16) + amt,
          G = ((num >> 8) & 0x00ff) + amt,
          B = (num & 0x0000ff) + amt;
        return `#${(
          (1 << 24) |
          ((R < 255 ? (R < 1 ? 0 : R) : 255) << 16) |
          ((G < 255 ? (G < 1 ? 0 : G) : 255) << 8) |
          (B < 255 ? (B < 1 ? 0 : B) : 255)
        )
          .toString(16)
          .slice(1)}`;
      }
      function gameStep() {
        const head = { x: snake[0].x + dx, y: snake[0].y + dy };
        if (
          head.x < 0 ||
          head.x >= canvas.width ||
          head.y < 0 ||
          head.y >= canvas.height ||
          snake.some((segment) => segment.x === head.x && segment.y === head.y)
        ) {
          gameOver();
          return;
        }
        snake.unshift(head);
        if (head.x === food.x && head.y === food.y) {
          score += 10;
          document.getElementById("score-panel").textContent = `得分: ${score}`;
          generateFood();
        } else {
          snake.pop();
        } // 发送状态到服务端
        sendStateToServer();
        draw();
      } // 修改后的游戏结束逻辑
      function gameOver() {
        clearInterval(gameLoop);
        gameStarted = false;
        autoMove = false;
        alert(`游戏结束！得分: ${score}`);
        initGame(); // 游戏结束后立即重置状态
      }
      function sendStateToServer() {
        // 发送状态到服务端
        const state = {
          type: "state",
          snake: snake,
          food: food,
          direction: { dx, dy },
          score: score,
        };
        if (socket.readyState === WebSocket.OPEN) {
          socket.send(JSON.stringify(state));
        }
      } // 键盘事件监听
      document.addEventListener("keydown", (e) => {
        if (!gameStarted) {
          gameStarted = true;
          initGame();
        }
        switch (e.key) {
          case "ArrowLeft":
            if (dx !== gridSize) {
              dx = -gridSize;
              dy = 0;
            }
            break;
          case "ArrowUp":
            if (dy !== gridSize) {
              dx = 0;
              dy = -gridSize;
            }
            break;
          case "ArrowRight":
            if (dx !== -gridSize) {
              dx = gridSize;
              dy = 0;
            }
            break;
          case "ArrowDown":
            if (dy !== -gridSize) {
              dx = 0;
              dy = gridSize;
            }
            break;
        }
        move();
      });
      function move() {
        // 当自动开启，且没有设置定时器时，设置定时器，并将定时器标志位置为true
        if (autoMove && !isSetting) {
          gameLoop = setInterval(gameStep, initialSpeed);
          isSetting = true;
        } else {
          gameStep();
        }
      } // 初始化首次显示
      initGame();
    </script>
  </body>
</html>
