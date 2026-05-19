export interface GeoJSONPolygon {
  type: 'Polygon';
  coordinates: number[][][];
}

export interface QueryRequest {
  question: string;
  polygon: GeoJSONPolygon;
  top_k?: number;
  similarity_threshold?: number;
  vector_weight?: number;
  bm25_weight?: number;
}

export interface ChunkResult {
  id: string;
  content: string;
  similarity_score: number;
  vector_score: number;
  bm25_score: number;
  hybrid_score: number;
  rerank_score: number | null;
  retrieval_rank: number;
  final_rank: number;
  location: {
    type: string;
    coordinates: [number, number];
  };
  metadata: Record<string, unknown>;
  source: string | null;
}

export interface QueryStats {
  chunks_in_polygon: number;
  chunks_returned: number;
  latency_ms: number;
}

export interface TraceInfo {
  embedding_ms: number;
  hybrid_query_ms: number;
  reranking_ms: number;
  llm_synthesis_ms: number;
  total_ms: number;
}

export interface QueryResponse {
  answer: string;
  chunks: ChunkResult[];
  query_stats: QueryStats;
  trace: TraceInfo;
  hyde_used: boolean;
  query_variations: string[];
}

export interface Document {
  id: string;
  title: string;
  source: string;
  created_at: string;
  chunk_count: number;
}

export interface JobStatus {
  job_id: string;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  filename: string;
  total_chunks: number | null;
  processed_chunks: number;
  progress: number;
  error_message: string | null;
  started_at: string;
  completed_at: string | null;
}

export interface EvalQueryResult {
  question: string;
  hit: boolean;
  rank_of_first_hit: number | null;
  retrieved_ids: string[];
}

export interface EvalRunResponse {
  hit_rate: number;
  mrr: number;
  results: EvalQueryResult[];
}
