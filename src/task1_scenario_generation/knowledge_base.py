import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from src.utils.llm_cost_tracker import get_tracker

load_dotenv()


def get_llm(callbacks: list | None = None):
    tracker = get_tracker()
    if callbacks is None:
        callbacks = [tracker]
    elif tracker not in callbacks:
        callbacks = list(callbacks) + [tracker]
    return ChatOpenAI(
        openai_api_key=os.getenv("DEEPSEEK_API"),
        openai_api_base=os.getenv("DEEPSEEK_URL_OPENAI") + "/v1",
        model=os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash"),
        temperature=0.1,
        callbacks=callbacks,
    )



