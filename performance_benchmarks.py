import time
import logging
from typing import List, Dict, Any, Callable
from vector_db_manager import VectorDBManager
from search_optimization import SearchOptimizer
import numpy as np

logger = logging.getLogger(__name__)


class PerformanceBenchmarks:
    """Benchmarking tools for vector database and search optimization performance."""

    def __init__(self, db_manager: VectorDBManager, search_optimizer: SearchOptimizer):
        self.db_manager = db_manager
        self.search_optimizer = search_optimizer

    def benchmark_embedding_speed(self, texts: List[str], num_runs: int = 10) -> Dict[str, float]:
        """Benchmark embedding generation speed."""
        times = []
        for _ in range(num_runs):
            start_time = time.time()
            self.db_manager._embed_texts(texts)
            end_time = time.time()
            times.append(end_time - start_time)

        avg_time = np.mean(times)
        std_time = np.std(times)
        return {
            "avg_embedding_time": avg_time,
            "std_embedding_time": std_time,
            "texts_per_second": len(texts) / avg_time if avg_time > 0 else 0
        }

    def benchmark_search_speed(self, queries: List[str], top_k: int = 3, num_runs: int = 10) -> Dict[str, float]:
        """Benchmark search query speed."""
        times = []
        for query in queries:
            for _ in range(num_runs):
                start_time = time.time()
                self.db_manager.read_records(query, top_k=top_k)
                end_time = time.time()
                times.append(end_time - start_time)

        avg_time = np.mean(times)
        std_time = np.std(times)
        return {
            "avg_search_time": avg_time,
            "std_search_time": std_time,
            "queries_per_second": len(queries) * num_runs / (avg_time * num_runs) if avg_time > 0 else 0
        }

    def benchmark_hybrid_search_speed(self, query: str, documents: List[str], top_k: int = 10, num_runs: int = 10) -> Dict[str, float]:
        """Benchmark hybrid search speed."""
        times = []
        for _ in range(num_runs):
            start_time = time.time()
            self.search_optimizer.hybrid_search(query, documents, top_k=top_k)
            end_time = time.time()
            times.append(end_time - start_time)

        avg_time = np.mean(times)
        std_time = np.std(times)
        return {
            "avg_hybrid_search_time": avg_time,
            "std_hybrid_search_time": std_time
        }

    def calculate_search_accuracy(
        self,
        queries: List[str],
        ground_truth: List[List[str]],  # For each query, list of relevant doc IDs
        search_function: Callable[[str, int], List[Dict[str, Any]]],
        top_k: int = 3
    ) -> Dict[str, float]:
        """
        Calculate precision, recall, and F1 for search results.

        search_function should return list of dicts with 'req_id' key.
        """
        precisions = []
        recalls = []
        f1s = []

        for query, gt_ids in zip(queries, ground_truth):
            results = search_function(query, top_k)
            retrieved_ids = [r.get("req_id") for r in results if r.get("req_id")]

            # Calculate metrics
            relevant_retrieved = len(set(retrieved_ids) & set(gt_ids))
            retrieved_count = len(retrieved_ids)
            relevant_count = len(gt_ids)

            precision = relevant_retrieved / retrieved_count if retrieved_count > 0 else 0
            recall = relevant_retrieved / relevant_count if relevant_count > 0 else 0
            f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0

            precisions.append(precision)
            recalls.append(recall)
            f1s.append(f1)

        return {
            "avg_precision": np.mean(precisions),
            "avg_recall": np.mean(recalls),
            "avg_f1": np.mean(f1s)
        }

    def run_full_benchmark(
        self,
        sample_texts: List[str],
        sample_queries: List[str],
        ground_truth: List[List[str]] = None
    ) -> Dict[str, Any]:
        """Run comprehensive performance benchmarks."""
        results = {}

        # Speed benchmarks
        results["embedding_speed"] = self.benchmark_embedding_speed(sample_texts)
        results["search_speed"] = self.benchmark_search_speed(sample_queries)

        # Sample documents for hybrid search
        sample_docs = sample_texts[:50] if len(sample_texts) > 50 else sample_texts
        results["hybrid_search_speed"] = self.benchmark_hybrid_search_speed(
            sample_queries[0] if sample_queries else "test query",
            sample_docs
        )

        # Accuracy benchmarks (if ground truth provided)
        if ground_truth:
            results["search_accuracy"] = self.calculate_search_accuracy(
                sample_queries, ground_truth, self.db_manager.read_records
            )

        return results

    def log_benchmark_results(self, results: Dict[str, Any]) -> None:
        """Log benchmark results."""
        logger.info("Performance Benchmark Results:")
        for category, metrics in results.items():
            logger.info(f"  {category}:")
            for metric, value in metrics.items():
                logger.info(f"    {metric}: {value:.4f}")


# Example usage
if __name__ == "__main__":
    # This would require actual instances
    # db = VectorDBManager()
    # optimizer = SearchOptimizer()
    # benchmarks = PerformanceBenchmarks(db, optimizer)
    # results = benchmarks.run_full_benchmark([...])
    # benchmarks.log_benchmark_results(results)
    print("PerformanceBenchmarks class ready for use.")