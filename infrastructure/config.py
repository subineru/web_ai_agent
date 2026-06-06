"""集中設定：以環境變數驅動，支援雙 LLM 後端切換（Anthropic / OpenAI-compatible）。

屬於最外層 Infrastructure；Domain/Application 不得 import 本模組。
"""
from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)

LLMBackend = Literal["anthropic", "openai_compat"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_prefix="", extra="ignore", case_sensitive=False
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        # 讓 .env 優先於 OS 環境變數：避免外部設成空字串的環境變數
        # 蓋掉 .env 裡的真實金鑰（dev 直覺：.env 應該贏）。
        return (init_settings, dotenv_settings, env_settings, file_secret_settings)

    # 後端選擇
    llm_backend: LLMBackend = Field(default="anthropic", alias="WAGENT_LLM_BACKEND")

    # Anthropic
    anthropic_api_key: str = Field(default="", alias="ANTHROPIC_API_KEY")
    anthropic_model: str = Field(default="claude-opus-4-8", alias="WAGENT_ANTHROPIC_MODEL")

    # OpenAI-compatible
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    openai_base_url: str = Field(default="https://api.openai.com/v1", alias="OPENAI_BASE_URL")
    openai_model: str = Field(default="gpt-4o", alias="WAGENT_OPENAI_MODEL")

    # 瀏覽器 agent 行為
    max_steps: int = Field(default=40, alias="WAGENT_MAX_STEPS")
    # browser-use 每步連續失敗容忍次數（含 LLM 偶發產出格式錯誤的重試）。
    # 與 captcha_ai_attempts 是不同概念，故獨立設定。調高可吸收間歇性壞輸出。
    max_failures: int = Field(default=5, alias="WAGENT_MAX_FAILURES")
    captcha_ai_attempts: int = Field(default=2, alias="WAGENT_CAPTCHA_AI_ATTEMPTS")
    headless: bool = Field(default=False, alias="WAGENT_HEADLESS")

    # 接棒策略：human_first / ai_then_human / ai_only
    handoff_policy: str = Field(default="ai_then_human", alias="WAGENT_HANDOFF_POLICY")

    # 合規與安全
    respect_robots: bool = Field(default=True, alias="WAGENT_RESPECT_ROBOTS")
    compliance_denylist: str = Field(default="", alias="WAGENT_COMPLIANCE_DENYLIST")  # 逗號分隔
    min_domain_interval_sec: float = Field(default=2.0, alias="WAGENT_MIN_DOMAIN_INTERVAL_SEC")
    user_agent: str = Field(default="wagent-bot", alias="WAGENT_USER_AGENT")

    def denylist_items(self) -> list[str]:
        return [d.strip() for d in self.compliance_denylist.split(",") if d.strip()]

    def active_backend(self) -> LLMBackend:
        """若選定後端缺 key，但另一後端有 key，則自動採用有 key 的後端。"""
        if self.llm_backend == "anthropic" and not self.anthropic_api_key and self.openai_api_key:
            return "openai_compat"
        if self.llm_backend == "openai_compat" and not self.openai_api_key and self.anthropic_api_key:
            return "anthropic"
        return self.llm_backend


@lru_cache
def get_settings() -> Settings:
    return Settings()
