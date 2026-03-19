import json
import logging
from anthropic import Anthropic
from conversation import ConversationManager
from docker_executor import DockerExecutor

logger = logging.getLogger(__name__)

TOOLS = [
    {
        "name": "run_command",
        "description": "Execute a shell command in the Docker sandbox. Use for running code, installing packages, compiling, etc.",
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The shell command to execute",
                }
            },
            "required": ["command"],
        },
    },
    {
        "name": "read_file",
        "description": "Read the contents of a file in the workspace.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "File path relative to /workspace",
                }
            },
            "required": ["path"],
        },
    },
    {
        "name": "write_file",
        "description": "Write content to a file in the workspace. Creates parent directories if needed.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "File path relative to /workspace",
                },
                "content": {
                    "type": "string",
                    "description": "The content to write",
                },
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "list_files",
        "description": "List files and directories in the given path.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Directory path to list, defaults to /workspace",
                }
            },
            "required": [],
        },
    },
]

SYSTEM_PROMPT = """You are a helpful coding assistant running inside a Telegram bot.
You have access to a sandboxed Docker environment where you can execute commands and manage files.
The workspace directory is /workspace — all files you create or read are inside it.

Guidelines:
- Use run_command to execute shell commands
- Use read_file/write_file for file operations
- Use list_files to explore the workspace
- Be concise in your responses (Telegram has message length limits)
- When writing code, save it to a file and then run it
- Always explain what you're doing before and after running commands
"""


class ClaudeAgent:
    def __init__(
        self,
        api_key: str,
        model: str,
        docker_executor: DockerExecutor,
        conversation: ConversationManager,
    ):
        self._client = Anthropic(api_key=api_key)
        self._model = model
        self._executor = docker_executor
        self._conversation = conversation

    async def process_message(self, user_message: str) -> str:
        """Process a user message and return the final response."""
        self._conversation.add_user_message(user_message)

        # Check if compression is needed
        if self._conversation.needs_compression():
            await self._compress_conversation()

        # Build system prompt
        system = SYSTEM_PROMPT
        summary_addition = self._conversation.get_system_prompt_addition()
        if summary_addition:
            system += f"\n\n{summary_addition}"

        # Agentic loop
        while True:
            response = self._client.messages.create(
                model=self._model,
                max_tokens=4096,
                system=system,
                tools=TOOLS,
                messages=self._conversation.get_messages(),
            )

            # Update token count
            self._conversation.update_token_count(response.usage.input_tokens)

            # Check if response has tool use
            if response.stop_reason == "tool_use":
                # Add assistant message with tool_use blocks
                self._conversation.add_raw_message({
                    "role": "assistant",
                    "content": response.content,
                })

                # Process each tool use
                tool_results = []
                for block in response.content:
                    if block.type == "tool_use":
                        result = self._execute_tool(block.name, block.input)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": result,
                        })

                # Add tool results
                self._conversation.add_raw_message({
                    "role": "user",
                    "content": tool_results,
                })
            else:
                # Final text response
                text_parts = []
                for block in response.content:
                    if hasattr(block, "text"):
                        text_parts.append(block.text)
                final_text = "\n".join(text_parts)
                self._conversation.add_assistant_message(final_text)
                return final_text

    def _execute_tool(self, tool_name: str, tool_input: dict) -> str:
        """Execute a tool and return the result as a string."""
        logger.info("Executing tool: %s with input: %s", tool_name, tool_input)
        try:
            if tool_name == "run_command":
                result = self._executor.run_command(tool_input["command"])
                return f"Exit code: {result['exit_code']}\n{result['output']}"

            elif tool_name == "read_file":
                path = tool_input["path"]
                if not path.startswith("/workspace"):
                    path = f"/workspace/{path}"
                content = self._executor.read_file(path)
                return content

            elif tool_name == "write_file":
                path = tool_input["path"]
                if not path.startswith("/workspace"):
                    path = f"/workspace/{path}"
                self._executor.write_file(path, tool_input["content"])
                return f"File written: {path}"

            elif tool_name == "list_files":
                path = tool_input.get("path", "/workspace")
                if not path.startswith("/workspace"):
                    path = f"/workspace/{path}"
                return self._executor.list_files(path)

            else:
                return f"Unknown tool: {tool_name}"

        except FileNotFoundError as e:
            return f"File not found: {e}"
        except ValueError as e:
            return f"Blocked: {e}"
        except Exception as e:
            logger.error("Tool execution error: %s", e)
            return f"Error: {e}"

    async def _compress_conversation(self) -> None:
        """Compress the conversation history using Claude."""
        messages_to_compress = self._conversation.get_messages_for_compression()
        if not messages_to_compress:
            return

        logger.info("Compressing %d messages", len(messages_to_compress))

        # Format messages for summarization
        formatted = []
        for msg in messages_to_compress:
            role = msg["role"]
            content = msg["content"] if isinstance(msg["content"], str) else "[tool interaction]"
            formatted.append(f"{role}: {content}")
        conversation_text = "\n".join(formatted)

        # Ask Claude to summarize
        response = self._client.messages.create(
            model=self._model,
            max_tokens=1024,
            system="You are a conversation summarizer. Create a concise summary of the conversation that preserves key context, decisions, and information needed for continuity. Focus on facts and outcomes, not pleasantries.",
            messages=[
                {
                    "role": "user",
                    "content": f"Summarize this conversation:\n\n{conversation_text}",
                }
            ],
        )

        summary = response.content[0].text
        self._conversation.apply_compression(summary)
        logger.info("Conversation compressed successfully")
