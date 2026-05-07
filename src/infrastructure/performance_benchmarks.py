import time
import logging
from typing import List, Dict, Any, Callable

import numpy as np

from src.infrastructure.retrieval_service import RetrievalService
from src.infrastructure.search_optimization import SearchOptimizer

logger = logging.getLogger(__name__)


class PerformanceBenchmarks:
    """
    RetrievalService ve SearchOptimizer performansını ölçen benchmark yardımcı sınıfı.

    Ölçülenler:
    - Embedding üretim hızı
    - Vector search hızı
    - Hybrid search hızı
    - Precision / Recall / F1 metriği
    """

    def __init__(
        self,
        retrieval_service: RetrievalService,
        search_optimizer: SearchOptimizer,
    ):
        self.retrieval_service = retrieval_service
        self.search_optimizer = search_optimizer

    def benchmark_embedding_speed(
        self,
        texts: List[str],
        num_runs: int = 5,
    ) -> Dict[str, float]:
        """Embedding üretim hızını ölçer."""
        if not texts:
            return {
                "avg_embedding_time": 0.0,
                "std_embedding_time": 0.0,
                "texts_per_second": 0.0,
            }

        embeddings = self.retrieval_service.embeddings
        times = []

        for _ in range(num_runs):
            start_time = time.time()
            embeddings.embed_documents(texts)
            elapsed = time.time() - start_time
            times.append(elapsed)

        avg_time = float(np.mean(times))
        std_time = float(np.std(times))

        return {
            "avg_embedding_time": avg_time,
            "std_embedding_time": std_time,
            "texts_per_second": len(texts) / avg_time if avg_time > 0 else 0.0,
        }

    def benchmark_search_speed(
        self,
        queries: List[str],
        top_k: int = 3,
        num_runs: int = 5,
    ) -> Dict[str, float]:
        """Vector similarity search hızını ölçer."""
        if not queries:
            return {
                "avg_search_time": 0.0,
                "std_search_time": 0.0,
                "queries_per_second": 0.0,
            }

        times = []

        for query in queries:
            for _ in range(num_runs):
                start_time = time.time()
                self.retrieval_service.get_similar_requirements(
                    query=query,
                    top_k=top_k,
                )
                elapsed = time.time() - start_time
                times.append(elapsed)

        avg_time = float(np.mean(times))
        std_time = float(np.std(times))

        total_queries = len(queries) * num_runs

        return {
            "avg_search_time": avg_time,
            "std_search_time": std_time,
            "queries_per_second": total_queries / sum(times) if sum(times) > 0 else 0.0,
        }

    def benchmark_hybrid_search_speed(
        self,
        query: str,
        documents: List[str],
        top_k: int = 10,
        num_runs: int = 5,
    ) -> Dict[str, float]:
        """BM25 + Dense hybrid search hızını ölçer."""
        if not query or not documents:
            return {
                "avg_hybrid_search_time": 0.0,
                "std_hybrid_search_time": 0.0,
            }

        times = []

        for _ in range(num_runs):
            start_time = time.time()
            self.search_optimizer.hybrid_search(
                query=query,
                documents=documents,
                top_k=top_k,
            )
            elapsed = time.time() - start_time
            times.append(elapsed)

        return {
            "avg_hybrid_search_time": float(np.mean(times)),
            "std_hybrid_search_time": float(np.std(times)),
        }

    def calculate_search_accuracy(
        self,
        queries: List[str],
        ground_truth: List[List[str]],
        search_function: Callable[[str, int], List[Any]],
        top_k: int = 3,
    ) -> Dict[str, float]:
        """
        Search sonuçları için Precision, Recall ve F1 hesaplar.

        search_function:
            query ve top_k almalı.
            LangChain Document listesi veya dict listesi döndürebilir.
        """
        if not queries or not ground_truth:
            return {
                "avg_precision": 0.0,
                "avg_recall": 0.0,
                "avg_f1": 0.0,
            }

        precisions = []
        recalls = []
        f1s = []

        for query, expected_ids in zip(queries, ground_truth):
            results = search_function(query, top_k)

            retrieved_ids = []

            for result in results:
                if isinstance(result, dict):
                    req_id = result.get("req_id")
                else:
                    req_id = getattr(result, "metadata", {}).get("req_id")

                if req_id:
                    retrieved_ids.append(req_id)

            expected_set = set(expected_ids)
            retrieved_set = set(retrieved_ids)

            true_positive = len(expected_set & retrieved_set)

            precision = true_positive / len(retrieved_set) if retrieved_set else 0.0
            recall = true_positive / len(expected_set) if expected_set else 0.0
            f1 = (
                2 * precision * recall / (precision + recall)
                if (precision + recall) > 0
                else 0.0
            )

            precisions.append(precision)
            recalls.append(recall)
            f1s.append(f1)

        return {
            "avg_precision": float(np.mean(precisions)),
            "avg_recall": float(np.mean(recalls)),
            "avg_f1": float(np.mean(f1s)),
        }

    def run_full_benchmark(
        self,
        sample_texts: List[str],
        sample_queries: List[str],
        ground_truth: List[List[str]] | None = None,
    ) -> Dict[str, Any]:
        """Tüm benchmarkları çalıştırır."""
        results: Dict[str, Any] = {}

        results["embedding_speed"] = self.benchmark_embedding_speed(sample_texts)
        results["search_speed"] = self.benchmark_search_speed(sample_queries)

        sample_docs = sample_texts[:50] if len(sample_texts) > 50 else sample_texts

        results["hybrid_search_speed"] = self.benchmark_hybrid_search_speed(
            query=sample_queries[0] if sample_queries else "test query",
            documents=sample_docs,
        )

        if ground_truth:
            results["search_accuracy"] = self.calculate_search_accuracy(
                queries=sample_queries,
                ground_truth=ground_truth,
                search_function=self.retrieval_service.get_similar_requirements,
            )

        return results

    def log_benchmark_results(self, results: Dict[str, Any]) -> None:
        """Benchmark sonuçlarını loglar."""
        logger.info("Performance Benchmark Results:")

        for category, metrics in results.items():
            logger.info("  %s:", category)

            for metric, value in metrics.items():
                if isinstance(value, float):
                    logger.info("    %s: %.4f", metric, value)
                else:
                    logger.info("    %s: %s", metric, value)


if __name__ == "__main__":
    print("PerformanceBenchmarks class ready for use.")