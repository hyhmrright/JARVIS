from app.tools.code_exec_tool import execute_code
from app.tools.datetime_tool import get_datetime


def test_datetime_returns_string():
    result = get_datetime.invoke({})
    assert isinstance(result, str)
    assert "2" in result


async def test_code_exec_simple():
    result = await execute_code.ainvoke({"code": "print(1 + 1)"})
    assert "2" in result


async def test_code_exec_timeout():
    result = await execute_code.ainvoke({"code": "import time; time.sleep(60)"})
    assert "timeout" in result.lower()
