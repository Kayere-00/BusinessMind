import { Fragment, useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Bar, BarChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  Bot, FileText, Plus, SendHorizonal, Trash2, User as UserIcon,
} from "lucide-react";
import api, { errMsg, fetchWithAuth, getAccessToken } from "../lib/api";
import type {
  AssistantAction, AssistantContext, AssistantConversation, AssistantConversationDetail,
  AssistantMessage, AssistantMessageMetadata, Dataset, Report,
} from "../lib/types";
import { useAuth } from "../lib/auth";
import { ErrorBanner, fmt, PageHeader, Spinner } from "../components/ui";

type ChatMessage = AssistantMessage & { transient?: boolean };

const SUGGESTIONS = [
  "What is the total revenue?",
  "Top 5 products by revenue",
  "Monthly revenue trend",
  "Forecast next 6 months",
  "Any anomalies in revenue?",
];

function SafeMarkdown({ content }: { content: string }) {
  return (
    <div className="break-words text-sm [&_p]:my-1 [&_h1]:my-2 [&_h1]:text-lg [&_h1]:font-bold [&_h2]:my-2 [&_h2]:text-base [&_h2]:font-bold [&_h3]:my-2 [&_h3]:font-bold [&_ul]:my-2 [&_ul]:list-disc [&_ul]:pl-5 [&_ol]:my-2 [&_ol]:list-decimal [&_ol]:pl-5 [&_li]:my-0.5 [&_blockquote]:my-2 [&_blockquote]:border-l-2 [&_blockquote]:border-slate-400 [&_blockquote]:pl-3 [&_pre]:my-2 [&_pre]:overflow-x-auto [&_pre]:rounded-lg [&_pre]:bg-slate-200/70 [&_pre]:p-3 dark:[&_pre]:bg-slate-950 [&_code]:rounded [&_code]:bg-slate-200/70 [&_code]:px-1 [&_code]:py-0.5 dark:[&_code]:bg-slate-700 [&_a]:text-brand-600 [&_a]:underline dark:[&_a]:text-brand-400 [&_table]:my-2 [&_table]:w-full [&_table]:text-xs [&_th]:border-b [&_th]:px-2 [&_th]:py-1.5 [&_td]:border-b [&_td]:px-2 [&_td]:py-1.5">
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
    </div>
  );
}

function metadataActions(metadata: AssistantMessageMetadata | null): AssistantAction[] {
  const raw = metadata?.actions;
  const values = Array.isArray(raw) ? raw : raw ? [raw] : [];
  return values.map((value) => typeof value === "string" ? { type: value } : value as AssistantAction);
}

function isReportAction(action: AssistantAction) {
  return /report/i.test([action.type, action.kind, action.action].join(" "));
}

function chartData(chart: AssistantMessageMetadata["chart"]) {
  if (!chart) return null;
  if (chart.type === "bar" && Array.isArray(chart.items)) return chart.items;
  if (chart.type === "line" && Array.isArray(chart.points)) return chart.points;
  return null;
}

function MessageVisuals({ metadata }: { metadata: AssistantMessageMetadata | null }) {
  const chart = metadata?.chart;
  const data = chartData(chart);
  const rows = metadata?.table?.rows;
  const suggestedActions = metadataActions(metadata).filter((action) => !isReportAction(action));
  return (
    <>
      {chart && data && chart.type === "bar" && (
        <div className="mt-3 h-48 w-full max-w-[500px]">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="label" tick={{ fontSize: 10 }} />
              <YAxis tick={{ fontSize: 10 }} />
              <Tooltip formatter={(value: unknown) => fmt(Number(value), true)} />
              <Bar dataKey="value" fill="#2563eb" radius={[6, 6, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
      {chart && data && chart.type === "line" && (
        <div className="mt-3 h-48 w-full max-w-[500px]">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={data}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="period" tick={{ fontSize: 10 }} />
              <YAxis tick={{ fontSize: 10 }} />
              <Tooltip formatter={(value: unknown) => fmt(Number(value), true)} />
              <Line type="monotone" dataKey="value" stroke="#2563eb" strokeWidth={2.5} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
      {rows?.length ? (
        <div className="mt-3 max-h-56 overflow-auto rounded-xl bg-white p-2 dark:bg-slate-900">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-slate-200 text-left dark:border-slate-700">
                {Object.keys(rows[0]).map((key) => <th key={key} className="px-2 py-1.5 font-bold">{key}</th>)}
              </tr>
            </thead>
            <tbody>
              {rows.slice(0, 20).map((row, i) => (
                <tr key={i} className="border-b border-slate-100 last:border-0 dark:border-slate-800">
                  {Object.entries(rows[0]).map(([key], j) => {
                    const value = row[key];
                    return <td key={j} className="px-2 py-1.5">{typeof value === "number" ? fmt(value) : String(value ?? "")}</td>;
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
      {metadata?.computed && Object.keys(metadata.computed).length > 0 && (
        <details className="mt-2 text-xs">
          <summary className="cursor-pointer font-semibold text-slate-500">Computed values</summary>
          <dl className="mt-1 grid grid-cols-[auto_1fr] gap-x-3 gap-y-1">
            {Object.entries(metadata.computed).map(([key, value]) => (
              <Fragment key={key}>
                <dt className="font-semibold">{key}</dt>
                <dd>{typeof value === "object" ? JSON.stringify(value) : String(value ?? "—")}</dd>
              </Fragment>
            ))}
          </dl>
        </details>
      )}
      {metadata?.tools && (
        <p className="mt-2 text-[10px] text-slate-400">Tools: {Array.isArray(metadata.tools) ? metadata.tools.map(String).join(", ") : String(metadata.tools)}</p>
      )}
      {suggestedActions.length > 0 && (
        <details className="mt-2 text-xs">
          <summary className="cursor-pointer font-semibold text-slate-500">Suggested actions</summary>
          <ul className="mt-1 list-disc pl-5">
            {suggestedActions.map((action, index) => (
              <li key={index}>{action.title || action.action || action.type || action.kind || JSON.stringify(action)}</li>
            ))}
          </ul>
        </details>
      )}
    </>
  );
}

export default function Assistant() {
  const { user } = useAuth();
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [selectedDataset, setSelectedDataset] = useState("");
  const [conversations, setConversations] = useState<AssistantConversation[]>([]);
  const [activeId, setActiveId] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [streamText, setStreamText] = useState("");
  const [statusText, setStatusText] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [llmStatus, setLlmStatus] = useState<{ enabled: boolean; reachable: boolean } | null>(null);
  const [context, setContext] = useState<AssistantContext | null>(null);
  const [contextText, setContextText] = useState("");
  const [contextLoading, setContextLoading] = useState(false);
  const [contextSaving, setContextSaving] = useState(false);
  const [contextError, setContextError] = useState("");
  const [reportBusy, setReportBusy] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);
  const streamController = useRef<AbortController | null>(null);
  const canEditContext = user?.role === "admin" || user?.role === "analyst";

  const loadConversations = useCallback(async () => {
    const response = await api.get<AssistantConversation[]>("/assistant/conversations");
    setConversations(response.data);
    return response.data;
  }, []);

  const loadConversation = useCallback(async (id: string) => {
    setError("");
    setActiveId(id);
    setMessages([]);
    try {
      const response = await api.get<AssistantConversationDetail>(`/assistant/conversations/${encodeURIComponent(id)}`);
      setMessages(response.data.messages || []);
      setSelectedDataset(response.data.dataset_id || "");
    } catch (e) {
      setError(errMsg(e));
      setActiveId("");
    }
  }, []);

  useEffect(() => {
    let active = true;
    Promise.all([
      api.get<Dataset[]>("/datasets"),
      api.get<AssistantConversation[]>("/assistant/conversations"),
      api.get("/assistant/status").catch(() => null),
    ]).then(([datasetResponse, conversationResponse, statusResponse]) => {
      if (!active) return;
      setDatasets(datasetResponse.data);
      setConversations(conversationResponse.data);
      if (datasetResponse.data.length) setSelectedDataset(datasetResponse.data[0].id);
      if (statusResponse) setLlmStatus(statusResponse.data);
      setLoading(false);
    }).catch((e) => {
      if (!active) return;
      setError(errMsg(e));
      setLoading(false);
    });
    setContextLoading(true);
    api.get<AssistantContext>("/assistant/context").then((response) => {
      if (active) {
        setContext(response.data);
        setContextText(response.data.context_text || "");
      }
    }).catch((e) => {
      if (active) setContextError(errMsg(e));
    }).finally(() => {
      if (active) setContextLoading(false);
    });
    return () => {
      active = false;
      streamController.current?.abort();
    };
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streamText, statusText]);

  const createConversation = async () => {
    setError("");
    try {
      const response = await api.post<AssistantConversation>("/assistant/conversations", {
        dataset_id: selectedDataset || null,
      });
      setConversations((items) => [response.data, ...items.filter((item) => item.id !== response.data.id)]);
      setActiveId(response.data.id);
      setMessages([]);
      setInput("");
    } catch (e) {
      setError(errMsg(e));
    }
  };

  const deleteConversation = async (id: string) => {
    if (!window.confirm("Delete this conversation? This cannot be undone.")) return;
    setError("");
    try {
      await api.delete(`/assistant/conversations/${encodeURIComponent(id)}`);
      setConversations((items) => items.filter((item) => item.id !== id));
      if (activeId === id) {
        setActiveId("");
        setMessages([]);
        setStreamText("");
      }
    } catch (e) {
      setError(errMsg(e));
    }
  };

  const ask = async (question: string) => {
    const content = question.trim();
    if (!content || busy) return;
    setError("");
    setInput("");
    let conversationId = activeId;
    if (!conversationId) {
      try {
        const response = await api.post<AssistantConversation>("/assistant/conversations", {
          dataset_id: selectedDataset || null,
        });
        conversationId = response.data.id;
        setConversations((items) => [response.data, ...items.filter((item) => item.id !== response.data.id)]);
        setActiveId(conversationId);
      } catch (e) {
        setError(errMsg(e));
        setInput(content);
        return;
      }
    }

    const userMessage: ChatMessage = {
      id: `pending-${Date.now()}`, role: "user", content, metadata: null, created_at: new Date().toISOString(),
    };
    setMessages((items) => [...items, userMessage]);
    setBusy(true);
    setStreamText("");
    setStatusText("Connecting…");
    const controller = new AbortController();
    streamController.current = controller;
    try {
      const response = await fetchWithAuth(`/api/assistant/conversations/${encodeURIComponent(conversationId)}/messages`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
        body: JSON.stringify({ content }),
        signal: controller.signal,
      });
      if (!response.ok) {
        let message = `Request failed (${response.status})`;
        try {
          const body = await response.json();
          message = body.detail || body.message || message;
        } catch { /* Response did not contain JSON. */ }
        throw new Error(message);
      }
      if (!response.body) throw new Error("Streaming is not supported by this response.");
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let completed = false;
      const processEvent = (block: string) => {
        let eventType = "message";
        const data: string[] = [];
        for (const line of block.split(/\r?\n/)) {
          if (line.startsWith("event:")) eventType = line.slice(6).trim();
          if (line.startsWith("data:")) data.push(line.slice(5).trimStart());
        }
        if (!data.length) return;
        let payload: any;
        try { payload = JSON.parse(data.join("\n")); } catch { return; }
        if (eventType === "status") setStatusText(String(payload.text || "Working…"));
        if (eventType === "delta") {
          setStatusText("");
          setStreamText((text) => text + String(payload.text || ""));
        }
        if (eventType === "complete" && payload.message) {
          completed = true;
          setMessages((items) => [...items, payload.message as AssistantMessage]);
          setStreamText("");
          setStatusText("");
        }
        if (eventType === "error") throw new Error(String(payload.message || "The assistant could not complete this request."));
      };
      while (true) {
        const { value, done } = await reader.read();
        buffer += decoder.decode(value, { stream: !done });
        const blocks = buffer.split(/\r?\n\r?\n/);
        buffer = blocks.pop() || "";
        blocks.forEach(processEvent);
        if (done) break;
      }
      if (buffer.trim()) processEvent(buffer);
      if (!completed) throw new Error("The assistant stream ended before a complete response was received.");
      await loadConversations().catch(() => undefined);
    } catch (e) {
      if (controller.signal.aborted) return;
      const message = e instanceof Error ? e.message : errMsg(e);
      setMessages((items) => [...items, {
        id: `error-${Date.now()}`, role: "assistant", content: message, metadata: null, created_at: new Date().toISOString(), transient: true,
      }]);
    } finally {
      streamController.current = null;
      setBusy(false);
      setStreamText("");
      setStatusText("");
    }
  };

  const saveContext = async () => {
    setContextSaving(true);
    setContextError("");
    try {
      const response = await api.put<AssistantContext>("/assistant/context", { context_text: contextText });
      setContext(response.data);
    } catch (e) {
      setContextError(errMsg(e));
    } finally {
      setContextSaving(false);
    }
  };

  const confirmReportAction = async (message: AssistantMessage, action: AssistantAction) => {
    const title = typeof action.title === "string" && action.title.trim()
      ? action.title.trim()
      : `${conversations.find((item) => item.id === activeId)?.title || "BusinessMind"} — Business Report`;
    const datasetId = action.dataset_id || message.metadata?.dataset_id || selectedDataset;
    if (!datasetId) {
      setError("Select a dataset before creating a report.");
      return;
    }
    if (!window.confirm(`Create the proposed report "${title}" now?`)) return;
    setReportBusy(message.id);
    setError("");
    try {
      const response = await api.post<Report>("/reports", { dataset_id: datasetId, title });
      if (response.data?.id) {
        const path = `/reports/${response.data.id}/download`;
        const token = getAccessToken();
        let file;
        try {
          file = await api.get(path, { params: { token }, responseType: "blob" });
        } catch (e) {
          const refreshedToken = getAccessToken();
          if (!refreshedToken || refreshedToken === token) throw e;
          file = await api.get(path, { params: { token: refreshedToken }, responseType: "blob" });
        }
        const url = URL.createObjectURL(file.data);
        const anchor = document.createElement("a");
        anchor.href = url;
        anchor.download = `${title}.pdf`;
        anchor.click();
        URL.revokeObjectURL(url);
      }
    } catch (e) {
      setError(errMsg(e));
    } finally {
      setReportBusy("");
    }
  };

  const datasetName = useMemo(
    () => datasets.find((dataset) => dataset.id === selectedDataset)?.name || "No dataset",
    [datasets, selectedDataset],
  );

  return (
    <div className="flex min-h-[calc(100dvh-11rem)] flex-col">
      <PageHeader title="AI Assistant" subtitle="Ask questions in plain English — answers are computed from your real data.">
        <div className="flex flex-wrap items-center gap-2">
          {llmStatus && (
            <span className={`rounded-full px-3 py-1 text-xs font-bold ${
              llmStatus.reachable
                ? "bg-emerald-50 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-400"
                : "bg-amber-50 text-amber-700 dark:bg-amber-500/10 dark:text-amber-400"
            }`}>
              {llmStatus.reachable ? "Ollama connected" : "Ollama offline — built-in engine active"}
            </span>
          )}
          <select
            className="input w-auto min-w-36 max-w-52"
            value={selectedDataset}
            disabled={busy}
            onChange={(event) => {
              setSelectedDataset(event.target.value);
              if (activeId) {
                setActiveId("");
                setMessages([]);
              }
            }}
            aria-label="Dataset for new conversation"
            title={activeId ? "Changing the dataset starts a new conversation" : "Dataset for new conversation"}
          >
            <option value="">No dataset</option>
            {datasets.map((dataset) => <option key={dataset.id} value={dataset.id}>{dataset.name}</option>)}
          </select>
        </div>
      </PageHeader>

      {error && <div className="mb-3"><ErrorBanner message={error} /></div>}

      <div className="grid min-h-[620px] flex-1 grid-cols-1 gap-4 lg:min-h-0 lg:grid-cols-[250px_minmax(0,1fr)]">
        <aside className="card flex max-h-48 min-h-0 flex-col p-3 lg:max-h-none">
          <div className="mb-2 flex items-center justify-between gap-2 px-1">
            <h2 className="text-sm font-bold">Conversations</h2>
            <button className="btn-primary !px-2.5 !py-2" onClick={createConversation} disabled={busy} aria-label="New conversation" title="New conversation">
              <Plus size={16} /><span className="text-xs">New</span>
            </button>
          </div>
          {loading ? <Spinner label="Loading conversations…" /> : conversations.length === 0 ? (
            <p className="px-2 py-3 text-xs text-slate-500">Start a conversation to see it here.</p>
          ) : (
            <div className="min-h-0 space-y-1 overflow-y-auto">
              {conversations.map((conversation) => (
                <div key={conversation.id} className={`group flex items-center gap-1 rounded-xl ${
                  activeId === conversation.id ? "bg-brand-50 dark:bg-brand-500/10" : "hover:bg-slate-100 dark:hover:bg-slate-800"
                }`}>
                  <button
                    className={`min-w-0 flex-1 px-2.5 py-2 text-left ${activeId === conversation.id ? "text-brand-700 dark:text-brand-300" : ""}`}
                    onClick={() => loadConversation(conversation.id)}
                    disabled={busy}
                  >
                    <span className="block truncate text-xs font-semibold">{conversation.title || "New conversation"}</span>
                    <span className="mt-0.5 block text-[10px] text-slate-500">{new Date(conversation.updated_at).toLocaleDateString()}</span>
                  </button>
                  <button
                    className="mr-1 rounded-lg p-2 text-slate-400 hover:bg-rose-50 hover:text-rose-600 dark:hover:bg-rose-500/10"
                    onClick={() => deleteConversation(conversation.id)}
                    disabled={busy}
                    aria-label={`Delete ${conversation.title || "conversation"}`}
                    title="Delete conversation"
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
              ))}
            </div>
          )}
        </aside>

        <section className="card flex min-h-[440px] min-w-0 flex-col p-3 sm:p-5">
          <div className="mb-3 flex items-center justify-between border-b border-slate-200 pb-3 dark:border-slate-700">
            <div className="min-w-0">
              <p className="truncate text-sm font-bold">{activeId ? conversations.find((item) => item.id === activeId)?.title || "Conversation" : "New conversation"}</p>
              <p className="truncate text-xs text-slate-500">Dataset: {datasetName}</p>
            </div>
          </div>
          <div className="min-h-0 flex-1 space-y-4 overflow-y-auto pr-1">
            {messages.length === 0 && !busy && (
              <div className="flex min-h-64 flex-col items-center justify-center text-center">
                <Bot size={36} className="mb-3 text-brand-600" />
                <p className="font-bold">Ask anything about your data</p>
                <p className="mt-1 max-w-md text-sm text-slate-500">
                  Answers are generated from your selected dataset and organization context.
                </p>
                <div className="mt-5 flex flex-wrap justify-center gap-2">
                  {SUGGESTIONS.map((suggestion) => (
                    <button key={suggestion} onClick={() => ask(suggestion)} disabled={busy}
                      className="rounded-full border border-slate-300 px-3.5 py-1.5 text-xs font-semibold text-slate-600 transition hover:border-brand-400 hover:text-brand-600 disabled:opacity-50 dark:border-slate-700 dark:text-slate-300">
                      {suggestion}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {messages.map((message) => {
              const isUser = message.role === "user";
              const actions = isUser ? [] : metadataActions(message.metadata).filter(isReportAction);
              return (
                <div key={message.id} className={`flex gap-3 ${isUser ? "justify-end" : ""}`}>
                  {!isUser && (
                    <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-brand-500 to-cyan-400 text-white">
                      <Bot size={16} />
                    </div>
                  )}
                  <div className={`min-w-0 max-w-[90%] rounded-2xl px-4 py-3 text-sm sm:max-w-[85%] ${
                    isUser ? "bg-brand-600 text-white" : "bg-slate-100 dark:bg-slate-800"
                  }`}>
                    <SafeMarkdown content={message.content} />
                    {!isUser && <MessageVisuals metadata={message.metadata} />}
                    {!isUser && (message.metadata?.source || message.metadata?.dataset_id) && (
                      <span className="mt-2 block text-[10px] font-semibold text-slate-400">
                        {message.metadata.source && `Source: ${message.metadata.source}`}
                        {message.metadata.source && message.metadata.dataset_id && " · "}
                        {message.metadata.dataset_id && `Dataset: ${datasets.find((dataset) => dataset.id === message.metadata?.dataset_id)?.name || message.metadata.dataset_id}`}
                      </span>
                    )}
                    {actions.map((action, index) => (
                      <button key={`${message.id}-${index}`} className="btn-ghost mt-3 !py-2 text-xs"
                        disabled={reportBusy === message.id}
                        onClick={() => confirmReportAction(message, action)}>
                        <FileText size={14} /> {reportBusy === message.id ? "Creating report…" : `Create proposed report${action.title ? `: ${action.title}` : ""}`}
                      </button>
                    ))}
                    {message.transient && !isUser && <span className="mt-2 block text-[10px] text-rose-600 dark:text-rose-400">This response was not saved to the conversation.</span>}
                  </div>
                  {isUser && (
                    <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-slate-200 dark:bg-slate-700">
                      <UserIcon size={16} />
                    </div>
                  )}
                </div>
              );
            })}
            {(busy || streamText) && (
              <div className="flex gap-3">
                <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-brand-500 to-cyan-400 text-white">
                  <Bot size={16} />
                </div>
                <div className="max-w-[85%] rounded-2xl bg-slate-100 px-4 py-3 text-sm dark:bg-slate-800">
                  {streamText ? <SafeMarkdown content={streamText} /> : <span className="animate-pulse font-semibold text-slate-500">{statusText || "Working…"}</span>}
                </div>
              </div>
            )}
            <div ref={bottomRef} />
          </div>

          <form className="mt-4 flex gap-2 border-t border-slate-200 pt-4 dark:border-slate-700"
            onSubmit={(event) => { event.preventDefault(); void ask(input); }}>
            <input
              className="input min-w-0"
              value={input}
              onChange={(event) => setInput(event.target.value)}
              placeholder={selectedDataset ? "e.g. Which region had the highest revenue?" : "Ask a question (choose a dataset for data analysis)…"}
              disabled={busy}
              maxLength={4000}
              aria-label="Message the assistant"
            />
            <button className="btn-primary shrink-0" disabled={busy || !input.trim()} aria-label="Send">
              <SendHorizonal size={17} />
            </button>
          </form>
        </section>
      </div>

      <details className="card mt-4">
        <summary className="cursor-pointer text-sm font-bold">Organization context</summary>
        <p className="mt-2 text-xs text-slate-500">
          Shared context used to tailor assistant responses. Only administrators and analysts can edit it.
          {context?.updated_at && ` Last updated ${new Date(context.updated_at).toLocaleString()}.`}
        </p>
        {contextLoading ? <Spinner label="Loading context…" /> : (
          <div className="mt-3">
            {contextError && <div className="mb-3"><ErrorBanner message={contextError} /></div>}
            <textarea className="input min-h-28 resize-y" value={contextText}
              onChange={(event) => setContextText(event.target.value)}
              readOnly={!canEditContext} maxLength={12000}
              aria-label="Organization context" placeholder="Add organization goals, definitions, and business rules…" />
            {canEditContext && (
              <div className="mt-2 flex items-center justify-between gap-3">
                <span className="text-xs text-slate-500">{contextText.length}/12000 characters</span>
                <button className="btn-primary" onClick={() => void saveContext()} disabled={contextSaving || contextText === (context?.context_text || "")}>
                  {contextSaving ? "Saving…" : "Save context"}
                </button>
              </div>
            )}
          </div>
        )}
      </details>
    </div>
  );
}
