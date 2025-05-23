import asyncio
import json
import traceback
from typing import Optional
from contextlib import AsyncExitStack
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()


class MCPClient:
    def __init__(self):
        self.session: Optional[ClientSession] = None
        self.exit_stack = AsyncExitStack()
        self.client = OpenAI(
            api_key="$API_KEY",
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
        )
        self.model = "qwen-max-latest"
        self.messages = [
            {
                "role": "system",
                "content": "You are a versatile assistant capable of answering questions, completing tasks, and intelligently invoking specialized tools to deliver optimal results."
            }
        ]
        self.available_tools = []

    @staticmethod
    def convert_custom_object(obj):
        if hasattr(obj, "__dict__"):
            return obj.__dict__
        elif isinstance(obj, (list, tuple)):
            return [MCPClient.convert_custom_object(item) for item in obj]
        elif isinstance(obj, dict):
            return {key: MCPClient.convert_custom_object(value) for key, value in obj.items()}
        else:
            return obj

    async def connect_to_server(self, server_script_path: str):
        is_python = server_script_path.endswith('.py')
        is_js = server_script_path.endswith('.js')

        if not (is_python or is_js):
            raise ValueError("Server script must be a .py or .js format")

        command = "python" if is_python else "node"
        server_params = StdioServerParameters(
            command=command,
            args=[server_script_path],
            env=None
        )
        stdio_transport = await self.exit_stack.enter_async_context(stdio_client(server_params))
        self.stdio, self.write = stdio_transport
        self.session = await self.exit_stack.enter_async_context(ClientSession(self.stdio, self.write))

        await self.session.initialize()
        response = await self.session.list_tools()
        tools = response.tools
        print("\nConnected to server with tools:", [tool.name for tool in tools])

    async def process_query(self, query: str) -> str:
        self.messages.append(
            {
                "role": "user",
                "content": query
            }
        )

        if not self.available_tools:
            response = await self.session.list_tools()
            self.available_tools = [{
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.inputSchema
                }
            } for tool in response.tools]

        current_response = self.client.chat.completions.create(
            model=self.model,
            messages=self.messages,
            tools=self.available_tools,
            stream=False
        )
        if current_response.choices[0].message.content:
            print("\n🤖 AI:", current_response.choices[0].message.content)

        while current_response.choices[0].message.tool_calls:
            for tool_call in current_response.choices[0].message.tool_calls:
                tool_name = tool_call.function.name
                try:
                    tool_args = json.loads(tool_call.function.arguments)
                except json.JSONDecodeError:
                    tool_args = {}

                print(f"\n🔧 调用工具 {tool_name}")
                print(f"📝 参数: {tool_args}")
                result = await self.session.call_tool(tool_name, tool_args)
                print(f"\n工具结果: {result}")
                self.messages.append(current_response.choices[0].message)

                self.messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(MCPClient.convert_custom_object(result.content))
                })
                current_response = self.client.chat.completions.create(
                    model=self.model,
                    messages=self.messages,
                    tools=self.available_tools,
                    stream=False
                )
        self.messages.append(current_response.choices[0].message)
        return current_response.choices[0].message.content or ""

    async def chat_loop(self):
        print("\n MCP Client Started!")
        print("Type your queries or 'quit' to exit.")

        while True:
            try:
                query = input("\n Commend: ").strip()
                if query.lower() == 'quit':
                    break
                response = await self.process_query(query)
                print("")
                print("\n🤖AI: " + response)
            except Exception as e:
                print(f"\n Error occurs: {e}")
                traceback.print_exc()

    async def cleanup(self):
        await self.exit_stack.aclose()


async def main():
    if len(sys.argv) < 2:
        print("Usage: python client.py <path_to_server_script>")
        sys.exit(1)

    client = MCPClient()
    try:
        await client.connect_to_server(sys.argv[1])
        await client.chat_loop()
    finally:
        await client.cleanup()


if __name__ == "__main__":
    import sys

    asyncio.run(main())
