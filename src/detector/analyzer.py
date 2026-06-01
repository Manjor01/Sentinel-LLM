import math
import time
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Interaction:
    """Одно взаимодействие с LLM — запрос + ответ."""
    prompt: str
    response: str
    timestamp: float = field(default_factory=time.time)


@dataclass
class AnalysisResult:
    """Результат анализа одного взаимодействия."""
    is_anomaly: bool
    risk_score: float          # 0.0 — норма, 1.0 — точно атака
    triggered_rules: list[str]
    features: dict
    prompt: str
    response: str
    timestamp: float


class PromptInjectionAnalyzer:
    """
    Поведенческий анализатор prompt injection атак.
    
    Логика: смотрим не на входящий запрос, а на поведение модели.
    Если модель отвечает аномально — значит её скомпрометировали.
    """

    # Паттерны которые часто встречаются в prompt injection атаках
    INJECTION_PATTERNS = [
        "ignore previous instructions",
        "ignore all previous",
        "disregard your instructions",
        "forget your instructions",
        "you are now",
        "act as",
        "pretend you are",
        "your new instructions",
        "system prompt",
        "jailbreak",
        "dan mode",
        "do anything now",
        "ignore the above",
        "новые инструкции",
        "игнорируй предыдущие",
        "ты теперь",
        "притворись что ты",
    ]

    # Паттерны в ответах которые говорят что модель "сломалась"
    COMPROMISED_RESPONSE_PATTERNS = [
        "i am now",
        "i will now ignore",
        "as dan",
        "i have no restrictions",
        "i can do anything",
        "sure, here is how to",
        "of course, i'll help you",
        "as you wish, i will",
    ]

    def __init__(self, anomaly_threshold: float = 0.6):
        self.anomaly_threshold = anomaly_threshold
        self.history: list[Interaction] = []
        self.baseline_response_length: Optional[float] = None

    def _compute_entropy(self, text: str) -> float:
        """
        Энтропия текста — мера непредсказуемости.
        
        Нормальные ответы имеют среднюю энтропию.
        Аномальные (например инструкции, код, данные) — другую.
        """
        if not text:
            return 0.0
        freq = {}
        for char in text:
            freq[char] = freq.get(char, 0) + 1
        total = len(text)
        entropy = 0.0
        for count in freq.values():
            p = count / total
            if p > 0:
                entropy -= p * math.log2(p)
        return round(entropy, 4)

    def _response_length_deviation(self, response: str) -> float:
        """
        Насколько длина ответа отличается от нормальной.
        
        Если модель вдруг начала отвечать в 5 раз длиннее —
        это подозрительно. Возможно она выполняет другую инструкцию.
        """
        length = len(response)
        if self.baseline_response_length is None:
            return 0.0
        if self.baseline_response_length == 0:
            return 0.0
        deviation = abs(length - self.baseline_response_length)
        relative = deviation / self.baseline_response_length
        return round(min(relative, 1.0), 4)

    def _update_baseline(self, response: str):
        """Обновляем среднюю длину ответа по истории."""
        if not self.history:
            self.baseline_response_length = len(response)
        else:
            lengths = [len(i.response) for i in self.history[-10:]]
            self.baseline_response_length = sum(lengths) / len(lengths)

    def _check_injection_patterns(self, text: str) -> list[str]:
        """Ищем известные паттерны атак в тексте."""
        text_lower = text.lower()
        found = []
        for pattern in self.INJECTION_PATTERNS:
            if pattern in text_lower:
                found.append(pattern)
        return found

    def _check_compromised_patterns(self, text: str) -> list[str]:
        """Ищем признаки что модель уже скомпрометирована."""
        text_lower = text.lower()
        found = []
        for pattern in self.COMPROMISED_RESPONSE_PATTERNS:
            if pattern in text_lower:
                found.append(pattern)
        return found

    def _compute_risk_score(self, features: dict) -> float:
        """
        Вычисляем итоговый риск-скор от 0.0 до 1.0.
        
        Каждый признак вносит свой вклад с весом.
        """
        score = 0.0

        # Паттерны атак в промпте — сильный сигнал
        if features["injection_patterns_count"] > 0:
            score += 0.4

        # Паттерны компрометации в ответе — очень сильный сигнал
        if features["compromised_patterns_count"] > 0:
            score += 0.4

        # Аномальная длина ответа
        score += features["length_deviation"] * 0.1

        # Аномальная энтропия ответа
        # Нормальная энтропия текста: 3.5 - 4.5 бит
        entropy = features["response_entropy"]
        if entropy < 2.5 or entropy > 5.5:
            score += 0.1

        return round(min(score, 1.0), 4)

    def analyze(self, prompt: str, response: str) -> AnalysisResult:
        """
        Главный метод — анализируем одно взаимодействие.
        
        Возвращает AnalysisResult с риск-скором и деталями.
        """
        self._update_baseline(response)

        # Собираем фичи
        injection_patterns = self._check_injection_patterns(prompt)
        compromised_patterns = self._check_compromised_patterns(response)
        length_deviation = self._response_length_deviation(response)
        response_entropy = self._compute_entropy(response)
        prompt_entropy = self._compute_entropy(prompt)

        features = {
            "prompt_length": len(prompt),
            "response_length": len(response),
            "prompt_entropy": prompt_entropy,
            "response_entropy": response_entropy,
            "length_deviation": length_deviation,
            "injection_patterns_count": len(injection_patterns),
            "compromised_patterns_count": len(compromised_patterns),
        }

        # Считаем риск
        risk_score = self._compute_risk_score(features)
        is_anomaly = risk_score >= self.anomaly_threshold

        # Собираем сработавшие правила для объяснения
        triggered_rules = []
        if injection_patterns:
            triggered_rules.append(f"Injection patterns in prompt: {injection_patterns}")
        if compromised_patterns:
            triggered_rules.append(f"Compromised patterns in response: {compromised_patterns}")
        if length_deviation > 0.5:
            triggered_rules.append(f"Abnormal response length deviation: {length_deviation}")
        if response_entropy < 2.5 or response_entropy > 5.5:
            triggered_rules.append(f"Abnormal response entropy: {response_entropy}")

        # Сохраняем в историю
        self.history.append(Interaction(
            prompt=prompt,
            response=response
        ))

        return AnalysisResult(
            is_anomaly=is_anomaly,
            risk_score=risk_score,
            triggered_rules=triggered_rules,
            features=features,
            prompt=prompt,
            response=response,
            timestamp=time.time()
        )