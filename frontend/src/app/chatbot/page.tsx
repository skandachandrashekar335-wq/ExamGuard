"use client";

import { useState, useEffect, useRef, useTransition } from "react";
import Link from "next/link";
import {
  ChatMessage,
  ChatCategory,
  sendChatQuery,
  getChatCategories,
  getChatSuggestions,
} from "@/lib/chatbot-api";

const INITIAL_GREETING: ChatMessage = {
  id: "msg-welcome",
  sender: "bot",
  text: "Hello! I am your ExamGuard Campus & Admission Guide. Ask me anything about degree courses, admission procedures, eligibility criteria, fees, required documents, exam entry rules, timetables, or campus facilities.",
  timestamp: new Date(),
  suggestions: [
    "What engineering courses and degrees are offered?",
    "What is the admission procedure for B.Tech?",
    "What documents are required for admission?",
    "How does ExamGuard face verification work on exam day?",
  ],
  isVerified: true,
};

export default function ChatbotPage() {
  const [messages, setMessages] = useState<ChatMessage[]>([INITIAL_GREETING]);
  const [inputQuery, setInputQuery] = useState("");
  const [categories, setCategories] = useState<ChatCategory[]>([]);
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sessionId] = useState(() => "sess_" + Math.random().toString(36).substring(2, 10));
  const msgCounterRef = useRef(0);
  const [, startTransition] = useTransition();

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Initialize categories & suggestions
  useEffect(() => {
    let isMounted = true;

    const initData = async () => {
      try {
        const [catData, sugData] = await Promise.all([
          getChatCategories(),
          getChatSuggestions(),
        ]);
        if (isMounted) {
          setCategories(catData.categories);
          setSuggestions(sugData.suggestions);
        }
      } catch {
        // Fallback silently if offline or initial fetch fails
      }
    };

    initData();
    return () => {
      isMounted = false;
    };
  }, []);

  // Auto-scroll on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  const handleSend = async (queryText?: string) => {
    const textToSend = (queryText || inputQuery).trim();
    if (!textToSend || loading) return;

    setError(null);
    setInputQuery("");

    msgCounterRef.current += 1;
    const currentId = msgCounterRef.current;
    const currentTimestamp = new Date();

    const userMsg: ChatMessage = {
      id: `usr-${currentId}`,
      sender: "user",
      text: textToSend,
      timestamp: currentTimestamp,
    };

    // Add user message immediately
    setMessages((prev) => [...prev, userMsg]);
    setLoading(true);

    try {
      const res = await sendChatQuery(textToSend, sessionId);
      msgCounterRef.current += 1;
      const botMsg: ChatMessage = {
        id: `bot-${msgCounterRef.current}`,
        sender: "bot",
        text: res.answer,
        timestamp: new Date(),
        category: res.category,
        suggestions: res.suggestions,
        requiresAdminConfirmation: res.requires_admin_confirmation,
        isVerified: res.is_verified,
        isFallback: !res.matched,
      };

      startTransition(() => {
        setMessages((prev) => [...prev, botMsg]);
      });
    } catch {
      setError("Unable to connect to the admission service. Please try again or visit the administrative block.");
      msgCounterRef.current += 1;
      const errorMsg: ChatMessage = {
        id: `bot-err-${msgCounterRef.current}`,
        sender: "bot",
        text: "I am having trouble reaching the campus knowledge service. Please check your network connection or contact the admissions desk at admissions@college.edu.",
        timestamp: new Date(),
        isFallback: true,
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setLoading(false);
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  };

  const handleClearHistory = () => {
    setMessages([INITIAL_GREETING]);
    setError(null);
    setSelectedCategory(null);
    inputRef.current?.focus();
  };

  const handleCategoryClick = (categoryName: string) => {
    if (selectedCategory === categoryName) {
      setSelectedCategory(null);
      return;
    }
    setSelectedCategory(categoryName);
    const cat = categories.find((c) => c.name === categoryName);
    if (cat && cat.sample_questions && cat.sample_questions.length > 0) {
      handleSend(cat.sample_questions[0]);
    }
  };

  return (
    <div className="flex flex-col h-[calc(100vh-4rem)] max-w-5xl mx-auto p-4 sm:p-6">
      {/* Top Header Card */}
      <div className="glass rounded-xl p-4 sm:p-5 mb-4 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 border border-[var(--border-subtle)]">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center text-emerald-400 font-bold text-lg">
            AI
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-lg font-semibold text-[var(--text-primary)]">
                Admission & Campus Guidance
              </h1>
              <span className="text-xs px-2 py-0.5 rounded-full bg-emerald-500/15 text-emerald-400 border border-emerald-500/30 font-medium">
                Live Knowledge Base
              </span>
            </div>
            <p className="text-xs text-[var(--text-secondary)]">
              Grounded information for prospective students, applicants, and examinees
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2 self-end sm:self-auto">
          <button
            onClick={handleClearHistory}
            className="px-3 py-1.5 text-xs text-[var(--text-secondary)] hover:text-[var(--text-primary)] bg-[var(--bg-surface)] hover:bg-[var(--bg-surface-hover)] border border-[var(--border-subtle)] rounded-lg transition-colors"
            title="Reset conversation"
          >
            Clear Chat
          </button>
          <Link
            href="/"
            className="px-3 py-1.5 text-xs text-sky-400 hover:text-sky-300 bg-sky-500/10 hover:bg-sky-500/20 border border-sky-500/30 rounded-lg transition-colors"
          >
            Back to Home
          </Link>
        </div>
      </div>

      {/* Category Pills Bar */}
      <div className="flex items-center gap-2 overflow-x-auto pb-2 mb-3 no-scrollbar text-xs">
        <span className="text-[var(--text-secondary)] whitespace-nowrap pl-1 font-medium">
          Explore Topics:
        </span>
        {categories.map((cat) => (
          <button
            key={cat.name}
            onClick={() => handleCategoryClick(cat.name)}
            className={`px-3 py-1 rounded-full whitespace-nowrap transition-all border ${
              selectedCategory === cat.name
                ? "bg-sky-500 text-white border-sky-400 shadow-sm"
                : "bg-[var(--bg-surface)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] border-[var(--border-subtle)] hover:border-[var(--border-base)]"
            }`}
          >
            {cat.title}
          </button>
        ))}
      </div>

      {/* Main Chat Scroll Container */}
      <div className="flex-1 overflow-y-auto glass rounded-xl p-4 sm:p-6 mb-4 space-y-4 border border-[var(--border-subtle)] flex flex-col">
        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`flex flex-col ${
              msg.sender === "user" ? "items-end" : "items-start"
            }`}
          >
            <div
              className={`max-w-[85%] sm:max-w-[75%] rounded-2xl px-4 py-3 text-sm leading-relaxed ${
                msg.sender === "user"
                  ? "bg-[var(--tech-blue)] text-white rounded-br-sm shadow-md"
                  : "bg-[var(--bg-surface)] text-[var(--text-primary)] border border-[var(--border-subtle)] rounded-bl-sm"
              }`}
            >
              {/* Category & Status Badges */}
              {msg.sender === "bot" && (msg.category || msg.requiresAdminConfirmation) && (
                <div className="flex flex-wrap items-center gap-1.5 mb-2 pb-2 border-b border-[var(--border-subtle)] text-[10px] uppercase font-semibold tracking-wider">
                  {msg.category && (
                    <span className="px-2 py-0.5 rounded bg-sky-500/15 text-sky-400 border border-sky-500/30">
                      {msg.category}
                    </span>
                  )}
                  {msg.isVerified && (
                    <span className="px-2 py-0.5 rounded bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">
                      Verified Policy
                    </span>
                  )}
                  {msg.requiresAdminConfirmation && (
                    <span className="px-2 py-0.5 rounded bg-amber-500/15 text-amber-300 border border-amber-500/30">
                      Confirm with Admin
                    </span>
                  )}
                </div>
              )}

              {/* Message text */}
              <div className="whitespace-pre-wrap">{msg.text}</div>

              {/* Timestamp */}
              <div
                suppressHydrationWarning
                className={`text-[10px] mt-2 text-right ${
                  msg.sender === "user" ? "text-sky-200" : "text-[var(--text-secondary)]"
                }`}
              >
                {new Date(msg.timestamp).toLocaleTimeString([], {
                  hour: "2-digit",
                  minute: "2-digit",
                })}
              </div>
            </div>

            {/* Contextual Suggestion Pills underneath Bot response */}
            {msg.sender === "bot" && msg.suggestions && msg.suggestions.length > 0 && (
              <div className="mt-2.5 flex flex-wrap gap-1.5 max-w-[85%] sm:max-w-[75%]">
                <span className="text-[11px] text-[var(--text-secondary)] w-full font-medium">
                  Related Questions:
                </span>
                {msg.suggestions.map((sug, i) => (
                  <button
                    key={i}
                    onClick={() => handleSend(sug)}
                    className="text-xs px-2.5 py-1 rounded-md bg-[var(--bg-surface)] hover:bg-sky-500/15 text-sky-300 border border-[var(--border-subtle)] hover:border-sky-500/40 text-left transition-all"
                  >
                    ↳ {sug}
                  </button>
                ))}
              </div>
            )}
          </div>
        ))}

        {/* Loading Indicator */}
        {loading && (
          <div className="flex items-start">
            <div className="bg-[var(--bg-surface)] border border-[var(--border-subtle)] rounded-2xl rounded-bl-sm px-4 py-3 flex items-center gap-2 text-xs text-[var(--text-secondary)]">
              <span className="inline-block w-2 h-2 rounded-full bg-sky-400 animate-ping" />
              <span>Retrieving verified campus information...</span>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Error alert if any */}
      {error && (
        <div className="mb-2 px-3 py-2 rounded-lg bg-rose-500/15 border border-rose-500/30 text-rose-300 text-xs flex items-center justify-between">
          <span>{error}</span>
          <button onClick={() => setError(null)} className="underline ml-2">
            Dismiss
          </button>
        </div>
      )}

      {/* Suggested Quick Starters (if no messages or just welcome) */}
      {messages.length <= 1 && suggestions.length > 0 && (
        <div className="mb-3">
          <div className="text-xs font-medium text-[var(--text-secondary)] mb-1.5">
            Popular Inquiries:
          </div>
          <div className="flex flex-wrap gap-1.5">
            {suggestions.slice(0, 4).map((sug, idx) => (
              <button
                key={idx}
                onClick={() => handleSend(sug)}
                className="text-xs px-3 py-1 rounded-lg bg-[var(--bg-surface)] hover:bg-[var(--bg-surface-hover)] text-[var(--text-primary)] border border-[var(--border-subtle)] hover:border-sky-500/50 transition-colors"
              >
                {sug}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Input Form Bar */}
      <form
        onSubmit={(e) => {
          e.preventDefault();
          handleSend();
        }}
        className="flex items-center gap-2"
      >
        <div className="relative flex-1">
          <input
            ref={inputRef}
            type="text"
            value={inputQuery}
            onChange={(e) => setInputQuery(e.target.value)}
            placeholder="Ask about admissions, courses, fees, documents, exam rules, timetables..."
            className="w-full px-4 py-3 rounded-xl bg-[var(--bg-surface)] border border-[var(--border-subtle)] focus:border-sky-500 focus:outline-none text-sm text-[var(--text-primary)] placeholder-[var(--text-secondary)] shadow-sm"
            disabled={loading}
          />
        </div>

        <button
          type="submit"
          disabled={loading || !inputQuery.trim()}
          className="px-5 py-3 rounded-xl bg-[var(--accent-gold)] hover:bg-[var(--accent-hover)] disabled:opacity-40 text-[#08080D] font-semibold text-sm flex items-center gap-2 transition-all shadow-md shrink-0 cursor-pointer disabled:cursor-not-allowed"
        >
          <span>Send</span>
          <svg
            className="w-4 h-4"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M14 5l7 7m0 0l-7 7m7-7H3"
            />
          </svg>
        </button>
      </form>
    </div>
  );
}
