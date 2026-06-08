import { Chunk } from "../types";

interface ChunkListProps {
  chunks: Chunk[];
}

/** Retrieved source chunks, in the descending-relevance order from the API. */
export function ChunkList({ chunks }: ChunkListProps) {
  if (chunks.length === 0) {
    return null;
  }
  return (
    <section className="chunks" aria-label="Sources">
      <h2>Sources</h2>
      <ol>
        {chunks.map((chunk, index) => (
          <li key={`${chunk.source_doc}-${index}`}>
            <a href={chunk.link} target="_blank" rel="noreferrer">
              {chunk.source_doc}
            </a>
            <span className="distance"> (cosine distance: {chunk.cosine_distance.toFixed(3)})</span>
          </li>
        ))}
      </ol>
    </section>
  );
}
