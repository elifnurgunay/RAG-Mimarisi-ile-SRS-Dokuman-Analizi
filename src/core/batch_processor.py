# src/core/batch_processor.py

from typing import List


class BatchProcessor:
    def __init__(self, max_chars: int = 50000):
        self.max_chars = max_chars

    def create_batches(self, text: str) -> List[str]:
        lines = [line.strip() for line in text.split("\n") if line.strip()]

        batches = []
        current_batch = []
        current_length = 0

        for line in lines:
            if current_length + len(line) > self.max_chars and current_batch:
                batches.append("\n".join(current_batch))
                current_batch = []
                current_length = 0

            current_batch.append(line)
            current_length += len(line)

        if current_batch:
            batches.append("\n".join(current_batch))

        return batches