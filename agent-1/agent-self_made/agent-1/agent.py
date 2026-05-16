

from pyexpat.errors import messages

from .memory import MessageLoader 
class AgentSelfMade:

    def __init__(self) -> None:
        self._memory = MessageLoader()

