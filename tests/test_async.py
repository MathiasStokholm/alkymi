#!/usr/bin/env python
import asyncio
import threading
from typing import List

import alkymi as alk
from alkymi import AlkymiConfig


def test_async_recipe() -> None:
    """
    Test that alkymi supports evaluating async functions
    """
    AlkymiConfig.get().cache = False

    @alk.recipe()
    async def async_vals() -> List[int]:
        thread_idx = threading.current_thread().ident
        assert thread_idx is not None
        await asyncio.sleep(0.01)
        return [thread_idx] * 10

    @alk.foreach(async_vals)
    async def async_squared_vals(val: int) -> int:
        await asyncio.sleep(0.01)
        return val ** 2

    # Check that everything executed on the main thread
    main_thread_idx = threading.current_thread().ident
    assert main_thread_idx is not None
    assert all(
        squared_thread_idx == main_thread_idx ** 2
        for squared_thread_idx in async_squared_vals.brew()
    )
