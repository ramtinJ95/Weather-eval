from typing import Literal

from pydantic import BaseModel

type HelloSource = Literal["firestore", "default", "error"]


class HelloResponse(BaseModel):
    message: str
    source: HelloSource
