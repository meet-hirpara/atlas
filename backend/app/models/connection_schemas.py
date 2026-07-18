from typing import Any, Dict, Optional



from pydantic import BaseModel, Field





class ConnectionStatus(BaseModel):

    provider: str

    connected: bool

    label: str = ""

    connected_at: Optional[str] = None





class ConnectRequest(BaseModel):

    credentials: Dict[str, Any] = Field(default_factory=dict)



    class Config:

        extra = "allow"


