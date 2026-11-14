import type { BatchResponse, DocumentSummaryView } from "../types";

export type Connection = "sse" | "polling" | "closed";

export interface BatchState {
  batch: Omit<BatchResponse, "documents"> | null;
  documents: Record<string, DocumentSummaryView>;
  order: string[];
  connection: Connection;
}

export type BatchAction =
  | { type: "snapshot"; batch: BatchResponse }
  | { type: "document"; document: DocumentSummaryView }
  | { type: "connection"; connection: Connection }
  | { type: "done" };

export const initialBatchState: BatchState = { batch: null, documents: {}, order: [], connection: "sse" };

const isNewer = (incoming: DocumentSummaryView, stored: DocumentSummaryView | undefined): boolean =>
  !stored || Date.parse(incoming.updated_at) >= Date.parse(stored.updated_at);

export function batchReducer(state: BatchState, action: BatchAction): BatchState {
  switch (action.type) {
    case "snapshot": {
      const { documents, ...batch } = action.batch;
      const merged: Record<string, DocumentSummaryView> = {};
      for (const doc of documents) {
        const stored = state.documents[doc.id];
        merged[doc.id] = stored && !isNewer(doc, stored) ? stored : doc;
      }
      return { ...state, batch, documents: merged, order: documents.map((d) => d.id) };
    }
    case "document": {
      const { document } = action;
      const stored = state.documents[document.id];
      if (!isNewer(document, stored)) return state;
      return {
        ...state,
        documents: { ...state.documents, [document.id]: document },
        order: stored ? state.order : [...state.order, document.id],
      };
    }
    case "connection":
      return state.connection === action.connection ? state : { ...state, connection: action.connection };
    case "done":
      return { ...state, connection: "closed" };
  }
}

export function allTerminal(state: BatchState): boolean {
  const docs = Object.values(state.documents);
  return docs.length > 0 && docs.every((d) => d.status === "completed" || d.status === "failed");
}

export const orderedDocuments = (state: BatchState): DocumentSummaryView[] =>
  state.order.flatMap((id) => state.documents[id] ?? []);
