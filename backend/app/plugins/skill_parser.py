"""SKILL.md (OpenClaw style) parser for lightweight agent skills."""

import re
from typing import Any

import structlog
from langchain_core.tools import StructuredTool
from pydantic import create_model

from app.sandbox.manager import SandboxManager

logger = structlog.get_logger(__name__)


class SkillParser:
    """Parse lightweight SKILL.md files into LangGraph tools."""

    def __init__(self, sandbox_manager: SandboxManager | None = None):
        from app.sandbox.manager import SandboxManager

        self.sandbox_manager = sandbox_manager or SandboxManager()

    def parse_markdown(self, md_content: str, filename: str) -> dict[str, Any]:
        """Extract metadata and sections from a SKILL.md file."""
        # Normalize line endings
        md_content = md_content.replace("\r\n", "\n")

        # Split by ## sections
        sections = re.split(r"^## ", md_content, flags=re.MULTILINE)

        # Header section (Title & Description)
        header = sections[0].strip()
        title_match = re.search(r"^# (.*)$", header, re.MULTILINE)
        title = (
            title_match.group(1).strip() if title_match else filename.replace(".md", "")
        )

        # Split header by newlines to find lines
        lines = [line.strip() for line in header.split("\n") if line.strip()]
        # First line might be the title
        if lines and lines[0].startswith("#"):
            description = lines[1] if len(lines) > 1 else f"Skill {title}"
        else:
            description = lines[0] if lines else f"Skill {title}"

        # Other sections
        params: dict[str, str] = {}
        impl_type = None
        impl_code = None

        for s in sections[1:]:
            s = s.strip()
            if s.startswith("Parameters"):
                # Use MULTILINE here to match each param line
                param_matches = re.finditer(r"^\s*-\s*`(\w+)`:\s*(.*)", s, re.MULTILINE)
                for m in param_matches:
                    params[m.group(1)] = m.group(2).strip()
            elif s.startswith("Implementation"):
                impl_match = re.search(r"```(\w+)\n(.*?)\n```", s, re.DOTALL)
                if impl_match:
                    impl_type = impl_match.group(1)
                    impl_code = impl_match.group(2).strip()

        return {
            "name": title,
            "description": description,
            "parameters": params,
            "implementation_type": impl_type,
            "implementation_code": impl_code,
        }

    def create_tool(self, skill_data: dict[str, Any]) -> StructuredTool:
        """Create a LangChain StructuredTool from parsed skill data."""
        name = skill_data["name"].lower().replace(" ", "_").replace("-", "_")
        description = skill_data["description"]
        impl_type = skill_data["implementation_type"]
        impl_code = skill_data["implementation_code"]
        params = skill_data["parameters"]

        # Create Pydantic model for arguments
        # All params are strings for simplicity in template substitution
        fields: dict[str, Any] = {p_name: (str, ...) for p_name in params.keys()}
        args_schema = create_model(f"{name}_args", **fields)

        async def _run(**kwargs: Any) -> str:
            if impl_type == "bash" or impl_type == "sh":
                return await self._execute_bash(impl_code, **kwargs)
            elif impl_type == "python":
                return await self._execute_python(impl_code, **kwargs)
            else:
                return f"Unsupported implementation type: {impl_type}"

        return StructuredTool(
            name=name,
            description=description,
            coroutine=_run,
            args_schema=args_schema,
            func=lambda **kwargs: "Async execution required",  # Fallback for sync
        )

    async def _execute_bash(self, code: str, **kwargs: Any) -> str:
        """Run bash code in the sandbox with parameter substitution."""
        # Simple template substitution: {{param}}
        command = code
        for k, v in kwargs.items():
            command = command.replace(f"{{{{{k}}}}}", str(v))

        container_id = None
        try:
            container_id = await self.sandbox_manager.create_sandbox(
                user_id="skill_agent", session_id="skill_exec"
            )
            output = await self.sandbox_manager.exec_in_sandbox(container_id, command)
            return output
        except Exception as e:
            logger.error("skill_bash_execution_failed", error=str(e))
            return f"Error executing bash skill: {e}"
        finally:
            if container_id:
                await self.sandbox_manager.destroy_sandbox(container_id)

    async def _execute_python(self, code: str, **kwargs: Any) -> str:
        """Run python code in the sandbox with parameter substitution."""
        # For python, we can wrap the code in a script or pass args via ENV/stdin
        # Simplest: substitute and run as a script
        script = code
        for k, v in kwargs.items():
            # Basic escaping for single-quoted strings in python
            escaped_v = str(v).replace("'", "\\'")
            script = script.replace(f"{{{{{k}}}}}", escaped_v)

        container_id = None
        try:
            container_id = await self.sandbox_manager.create_sandbox(
                user_id="skill_agent", session_id="skill_exec"
            )
            # Write script to file inside container and run it
            # Using sh -c to echo into a file
            # We need to escape the script for shell echo
            escaped_script = script.replace("'", "'\\''")
            setup_cmd = f"printf '%s' '{escaped_script}' > /tmp/skill.py"
            await self.sandbox_manager.exec_in_sandbox(container_id, setup_cmd)

            output = await self.sandbox_manager.exec_in_sandbox(
                container_id, "python3 /tmp/skill.py"
            )
            return output
        except Exception as e:
            logger.error("skill_python_execution_failed", error=str(e))
            return f"Error executing python skill: {e}"
        finally:
            if container_id:
                await self.sandbox_manager.destroy_sandbox(container_id)
