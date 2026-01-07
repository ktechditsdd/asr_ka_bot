from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import SecretStr
from typing import List

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="forbid")

    bot_token: SecretStr
    group_chat_id: int 

    database_url: SecretStr  

    admin_ids: str = ""  # "1,2,3"

    def admin_id_list(self) -> List[int]:
        if not self.admin_ids.strip():
            return []
        return [int(x.strip()) for x in self.admin_ids.split(",") if x.strip()]

settings = Settings()
