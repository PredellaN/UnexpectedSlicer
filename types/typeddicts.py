from typing import TypedDict, Optional
class PrinterConf(TypedDict):
    name: str
    host_type: str
    ip: str
    port: int
    username: str
    password: str

class PrinterData(TypedDict):
    progress: float
    state: str
    job_name: Optional[str]
    job_id: Optional[str]

class PrinterResponse(PrinterConf, PrinterData):
    pass