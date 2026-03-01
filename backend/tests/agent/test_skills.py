"""Tests for the Skills-as-Markdown loading system."""

import tempfile
import textwrap
from pathlib import Path

from app.agent.skills import SkillFile, format_skills_for_prompt, load_skills


def test_load_skills_from_directory():
    with tempfile.TemporaryDirectory() as d:
        Path(d, "test_skill.md").write_text(
            textwrap.dedent("""\
                ---
                name: test-skill
                description: A test skill for unit testing
                triggers:
                  - run tests
                  - execute tests
                ---
                # Test Skill
                When asked to run tests, execute: `pytest tests/ -v`
            """)
        )
        skills = load_skills(d)
    assert len(skills) == 1
    assert skills[0].name == "test-skill"
    assert "A test skill" in skills[0].description
    assert "run tests" in skills[0].triggers


def test_load_skills_empty_directory():
    with tempfile.TemporaryDirectory() as d:
        skills = load_skills(d)
    assert skills == []


def test_load_skills_missing_directory():
    skills = load_skills("/nonexistent/path/skills")
    assert skills == []


def test_load_skills_ignores_files_without_frontmatter():
    with tempfile.TemporaryDirectory() as d:
        Path(d, "no_frontmatter.md").write_text(
            "# Just a regular markdown file\nNo YAML here."
        )
        skills = load_skills(d)
    assert skills == []


def test_load_skills_handles_invalid_yaml():
    with tempfile.TemporaryDirectory() as d:
        Path(d, "bad_yaml.md").write_text("---\nname: [invalid: yaml: {\n---\nContent")
        skills = load_skills(d)
    assert skills == []


def test_skill_content_excludes_frontmatter():
    """content should contain only the body after frontmatter, not --- delimiters."""
    with tempfile.TemporaryDirectory() as d:
        Path(d, "skill.md").write_text(
            textwrap.dedent("""\
                ---
                name: my-skill
                description: Test frontmatter stripping
                triggers:
                  - do it
                ---
                # Instructions
                Run this command: `echo hello`
            """)
        )
        skills = load_skills(d)
    assert len(skills) == 1
    assert "---" not in skills[0].content
    assert "# Instructions" in skills[0].content
    assert "echo hello" in skills[0].content


def test_format_skills_for_prompt():
    skills = [
        SkillFile(
            name="git-helper",
            description="Help with git commands",
            triggers=["commit", "push"],
        ),
        SkillFile(
            name="code-review",
            description="Review code quality",
            triggers=["review"],
        ),
    ]
    result = format_skills_for_prompt(skills)
    assert "git-helper" in result
    assert "code-review" in result
    assert "commit" in result
    assert "## Available Skills" in result


def test_format_skills_for_prompt_includes_body():
    """format_skills_for_prompt must include skill body so LLM receives instructions."""
    skills = [
        SkillFile(
            name="deploy-skill",
            description="Deploy the app",
            triggers=["deploy"],
            content="Run `make deploy` to deploy.\nCheck logs after.",
        )
    ]
    result = format_skills_for_prompt(skills)
    assert "Run `make deploy`" in result
    assert "Check logs after" in result


def test_format_skills_for_prompt_empty():
    result = format_skills_for_prompt([])
    assert result == ""


def test_format_skills_no_triggers():
    skills = [SkillFile(name="generic", description="A generic skill", triggers=[])]
    result = format_skills_for_prompt(skills)
    assert "generic" in result
    assert "any relevant request" in result
