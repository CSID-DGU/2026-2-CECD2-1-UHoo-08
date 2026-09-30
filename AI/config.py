from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DASHSCOPE_API_KEY: str
    QWEN_VL_BASE_URL: str = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
    QWEN_VL_MODEL: str = "qwen3-vl-flash"
    QWEN_TEXT_BASE_URL: str = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
    QWEN_TEXT_MODEL: str = "qwen-plus"

    GEMINI_API_KEY: str
    GEMINI_MODEL: str = "gemini-2.5-flash"

    # 역할별 LLM. services.llm.get_llm(role) 이 읽는다.
    #
    # 모델 이름을 부르는 쪽에 두면 "Normalize 만 상위 모델로 올려 정확도가
    # 얼마나 오르는지" 같은 비교를 할 때마다 코드를 고쳐야 한다. 비용 대비
    # 효과가 큰 곳만 골라 올리려면 그 비교가 쉬워야 한다.
    #
    # 비워 두면 역할 기본값을 쓴다. BASE_URL·API_KEY 를 함께 바꾸면
    # 다른 제공자의 OpenAI 호환 주소로 코드 수정 없이 옮길 수 있다.
    LLM_NORMALIZE_MODEL: str = ""
    LLM_NORMALIZE_BASE_URL: str = ""
    LLM_NORMALIZE_API_KEY: str = ""

    LLM_WEIGHT_MODEL: str = ""
    LLM_WEIGHT_BASE_URL: str = ""
    LLM_WEIGHT_API_KEY: str = ""

    LLM_COMPOSE_MODEL: str = ""
    LLM_COMPOSE_BASE_URL: str = ""
    LLM_COMPOSE_API_KEY: str = ""

    LLM_VLM_MODEL: str = ""
    LLM_VLM_BASE_URL: str = ""
    LLM_VLM_API_KEY: str = ""

    # Supabase
    SUPABASE_URL: str
    SUPABASE_SERVICE_KEY: str

    # Redis
    REDIS_URL: str = "redis://localhost:6379"

    # Embedding
    EMBEDDING_MODEL: str = "BAAI/bge-m3"
    EMBEDDING_DEVICE: str = "cpu"
    EMBEDDING_USE_FP16: bool = False
    HF_HOME: str = "/app/.cache/huggingface"

    # Vector search
    VECTOR_SEARCH_EF_SEARCH: int = 40

    # Monitoring
    LANGSMITH_API_KEY: str = ""
    LANGSMITH_PROJECT: str = "capstone-ai"

    class Config:
        env_file = ".env"
        extra = "ignore"

    # IoT
    IOT_API_KEY: str = ""          # 비어 있으면 인증 생략 (개발용)
    IOT_MAX_BATCH: int = 288       # 10분 주기 × 2일치

    # 측정 세션이 열린 채로 유지되는 시간.
    # 사람이 백색 표준판을 올리고 시료로 바꿔 다시 재는 데 걸리는 시간이며,
    # 도중에 자리를 뜬 세션이 노드를 계속 붙잡고 있지 않게 하는 상한이기도 하다.
    MEASURE_SESSION_TTL_SEC: int = 300
    # 측정 노드가 "내 일감 있나"를 묻는 간격. 펌웨어와 맞춰 둔다.
    MEASURE_POLL_SEC: int = 2

    # 기상청 단기예보 (공공데이터포털)
    KMA_SERVICE_KEY: str = ""

settings = Settings()