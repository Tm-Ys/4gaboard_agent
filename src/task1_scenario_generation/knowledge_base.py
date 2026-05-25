import os
from dotenv import load_dotenv
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from openai import APIConnectionError, APIStatusError, RateLimitError
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
        request_timeout=30,
        callbacks=callbacks,
    )


_llm_retry = retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((APIConnectionError, RateLimitError, APIStatusError)),
    before_sleep=lambda retry_state: None,
)


def llm_invoke(messages: list) -> str:
    llm = get_llm()
    result = _llm_retry(llm.invoke)(messages)
    return result.content
