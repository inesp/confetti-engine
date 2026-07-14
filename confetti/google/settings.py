from dataclasses import dataclass

from confetti.constants import GOOGLE_CREDENTIALS_FILE
from confetti.constants import GOOGLE_TOKEN_FILE


@dataclass
class GoogleSettings:
    @property
    def CREDENTIALS_FILE_NAME(self) -> str:
        return str(GOOGLE_CREDENTIALS_FILE)

    @property
    def TOKEN_FILE_NAME(self) -> str:
        return str(GOOGLE_TOKEN_FILE)

    @property
    def HAS_CREDENTIALS(self) -> bool:
        return GOOGLE_CREDENTIALS_FILE.exists()

    @property
    def HAS_TOKEN(self) -> bool:
        return GOOGLE_TOKEN_FILE.exists()
