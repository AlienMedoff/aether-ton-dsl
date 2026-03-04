import pytest
import asyncio
from unittest.mock import AsyncMock
from dispatcher import Dispatcher

@pytest.mark.asyncio
async def test_dispatcher_routes_task():
    # 1. Setup Mocks
    mock_store = AsyncMock()
    mock_agent = AsyncMock()

    # Имитируем задачу со статусом "PROCESSING"
    task_data = {"id": "1", "status": "PROCESSING"}

    # store вернет задачу один раз, потом None, чтобы остановить цикл
    mock_store.get_next_pending.side_effect = [task_data, None]

    agents = {"PROCESSING": mock_agent}
    dispatcher = Dispatcher(mock_store, agents)

    # 2. Run dispatcher
    task = asyncio.create_task(dispatcher.run_loop())

    # Даем время на обработку
    await asyncio.sleep(0.1)
    dispatcher.stop()
    await task

    # 3. Assert
    mock_agent.process_task.assert_called_once_with(task_data)
