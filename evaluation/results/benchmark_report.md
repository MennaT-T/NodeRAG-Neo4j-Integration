# Benchmark Results - Job Application Q&A System
**Generated:** 2026-03-18 08:01:37  
**Test User:** 36

---

## System Configuration

| Component | Specification |
|-----------|---------------|
| Python Version | 3.11.15 |
| NodeRAG Framework | Graph-based RAG with Multi-User Support |
| Knowledge Graph Backend | Neo4j (user_id filtered) |
| Vector Search | HNSW Index (user-specific) |
| **Test User ID** | **36** |
| User Data Folder | POC_Data/documents/users/user_36 |

---

## Dataset Statistics

| Metric | Value |
|--------|-------|
| Total Graph Nodes | 208 |
| Total Graph Edges | 1186 |
| Q&A HNSW Index | Not Available |

---

## Table 1: Overall Query Latency Results

| Metric | Value |
|--------|-------|
| **Average Latency** | **27516.85 ms** |
| Standard Deviation | 2076.28 ms |
| Median Latency | 27939.87 ms |
| Minimum Latency | 17927.47 ms |
| Maximum Latency | 29552.50 ms |
| **Success Rate** | **100.0%** |
| Successful Queries | 24/24 |
| Throughput | 2.18 queries/min |

---

## Table 2: Performance by Query Category

| Category | Count | Successful | Success Rate | Avg Latency (ms) | Std Dev (ms) |
|----------|-------|------------|--------------|------------------|--------------|
| education | 3 | 3 | 100.0% | 27788.21 | 287.15 |
| experience | 6 | 6 | 100.0% | 28163.25 | 825.39 |
| motivation | 3 | 3 | 100.0% | 24719.13 | 4802.55 |
| soft_skills | 6 | 6 | 100.0% | 27782.24 | 600.89 |
| technical_skills | 6 | 6 | 100.0% | 27868.26 | 256.39 |

---

## Table 3: Retrieval Statistics

| Metric | Value |
|--------|-------|
| Average Nodes Retrieved | 20.2 |
| Average Answer Length (chars) | 1668 |
| Total Graph Nodes Available | 208 |

---

## Files Generated

- `benchmark_results_raw.json` - Raw results data
- `benchmark_report.md` - This report

## Reproducibility

```bash
python evaluation/quick_benchmark.py 36
```
