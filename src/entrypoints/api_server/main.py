import uvicorn

from agent.bootstrap import build_agent_from_env
from api.app import create_app
from logging_config import setup_logging

_HOST = "0.0.0.0"
_PORT = 8000


def main() -> None:
    """建立 Agent、組裝 FastAPI app 並啟動 uvicorn server。"""
    setup_logging()
    agent = build_agent_from_env()
    app = create_app(agent)
    uvicorn.run(app, host=_HOST, port=_PORT)


if __name__ == "__main__":
    main()
