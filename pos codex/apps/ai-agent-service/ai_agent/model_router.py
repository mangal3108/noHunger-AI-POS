class ModelRouter:
    def __init__(self, local_model: str, remote_model: str, complexity_threshold: int = 2) -> None:
        self.local_model = local_model
        self.remote_model = remote_model
        self.complexity_threshold = complexity_threshold

    def choose_model(self, message: str, tool_failed: bool = False) -> str:
        complexity = self._estimate_complexity(message)
        if tool_failed or complexity >= self.complexity_threshold:
            return self.remote_model
        return self.local_model

    @staticmethod
    def _estimate_complexity(message: str) -> int:
        text = message.lower()
        score = 0
        if any(token in text for token in ("compare", "optimize", "best for", "multi-step", "budget")):
            score += 1
        if len(text.split()) > 18:
            score += 1
        if "and" in text and "then" in text:
            score += 1
        return score
