
class MessageLoader: 

    def __init__(self) -> None:
        self._messages: list[dict[str, any]] = []


    def add_user(self, content: str | list) -> None:
        self._messages.append({"role": "user", "content": content})


    def add_assistant(self, content: str | list) -> None:
        self._messages.append({"role": "assistant", "content": content})


    def all(self) -> list[dict[str,any]]:
        return list(self._messages)
    

    def __len__(self) -> int:
        return len(self._messages)
    s