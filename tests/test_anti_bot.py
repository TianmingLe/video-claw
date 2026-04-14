import pytest
import time
import asyncio
from backend.middleware.anti_bot import AntiBotController

@pytest.mark.asyncio
async def test_random_delay_normal_mode():
    controller = AntiBotController(mode="normal")
    start_time = time.time()
    await controller.random_delay("search")
    duration = time.time() - start_time
    assert 0.3 <= duration <= 1.5 # normal 模式 search 延迟通常在 0.3 到 1.2 秒左右，给一点误差余量

@pytest.mark.asyncio
async def test_random_delay_special_forces_mode():
    controller = AntiBotController(mode="special_forces")
    start_time = time.time()
    await controller.random_delay("search")
    duration = time.time() - start_time
    assert 0.1 <= duration <= 0.6 # special_forces 模式更短