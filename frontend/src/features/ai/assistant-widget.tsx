"use client";

import { useMutation } from "@tanstack/react-query";
import { MessageCircleQuestion, Send, X } from "lucide-react";
import Link from "next/link";
import { useEffect, useRef, useState, type FormEvent } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useFeatures } from "@/features/meta/use-features";
import { apiFetch, type Schemas } from "@/lib/api/client";
import { errorMessage } from "@/lib/api/errors";
import { cn } from "@/lib/utils";

type Answer = Schemas["AssistantOut"];
type Turn = { role: "user"; content: string } | { role: "assistant"; content: string; answer: Answer };

const STARTERS = ["Can I cancel my flight for free?", "What happens if my flight is cancelled?", "Which promo codes can I use?"];

/** "Ask TripMind": help answers grounded in TripMind's policies and the traveller's trips. */
export function AssistantWidget() {
  const { enabled } = useFeatures();
  const [open, setOpen] = useState(false);
  const [text, setText] = useState("");
  const [turns, setTurns] = useState<Turn[]>([]);
  const end = useRef<HTMLDivElement>(null);
  const ask = useMutation({
    mutationFn: (messages: Array<{ role: "user" | "assistant"; content: string }>) =>
      apiFetch<Answer>("/ai/assistant", { method: "POST", body: { messages } }),
  });

  useEffect(() => end.current?.scrollIntoView({ behavior: "smooth" }), [turns, open]);
  if (!enabled("ai_assistant")) return null;

  function send(question: string) {
    const content = question.trim();
    if (!content || ask.isPending) return;
    const history = [...turns, { role: "user" as const, content }];
    setTurns(history);
    setText("");
    ask.mutate(
      history.slice(-6).map((t) => ({ role: t.role, content: t.content.slice(0, 1000) })),
      { onSuccess: (answer) => setTurns((current) => [...current, { role: "assistant", content: answer.answer, answer }]) },
    );
  }

  return (
    <div className="fixed right-4 bottom-4 z-50 print:hidden">
      {open ? (
        <div className="flex h-[32rem] w-[22rem] max-w-[calc(100vw-2rem)] flex-col overflow-hidden rounded-xl border bg-background shadow-xl">
          <div className="flex items-center justify-between border-b px-4 py-3">
            <div>
              <p className="text-sm font-semibold">Ask TripMind</p>
              <p className="text-xs text-muted-foreground">Answers from our help and your trips. It can&apos;t book or cancel.</p>
            </div>
            <Button size="icon" variant="ghost" aria-label="Close assistant" onClick={() => setOpen(false)}>
              <X />
            </Button>
          </div>
          <div className="flex-1 space-y-3 overflow-y-auto p-4 text-sm" aria-live="polite">
            {turns.length === 0 ? (
              <div className="grid gap-2">
                {STARTERS.map((s) => (
                  <button key={s} type="button" onClick={() => send(s)}
                    className="rounded-lg border px-3 py-2 text-left hover:bg-muted/50">
                    {s}
                  </button>
                ))}
              </div>
            ) : null}
            {turns.map((turn, i) => (
              <div key={i} className={cn("grid gap-1", turn.role === "user" && "justify-items-end")}>
                <div className={cn("max-w-[90%] rounded-lg px-3 py-2 whitespace-pre-line",
                  turn.role === "user" ? "bg-primary text-primary-foreground" : "bg-muted")}>
                  {turn.content}
                </div>
                {turn.role === "assistant" ? (
                  <div className="flex flex-wrap gap-1">
                    <Badge variant="outline" className="text-[10px]">
                      {turn.answer.source === "rules" ? "Help article (AI unavailable)" : `AI · ${turn.answer.source.slice(3)}`}
                    </Badge>
                    {turn.answer.citations.map((c) => (
                      <Badge key={c.title} variant="secondary" className="text-[10px]" title={c.source}>
                        {c.title}
                      </Badge>
                    ))}
                    {turn.answer.actions.map((a) => (
                      <Button key={a.href} asChild size="sm" variant="outline" className="h-6 px-2 text-xs">
                        <Link href={a.href} onClick={() => setOpen(false)}>{a.label}</Link>
                      </Button>
                    ))}
                  </div>
                ) : null}
              </div>
            ))}
            {ask.isPending ? <p className="text-xs text-muted-foreground">Thinking…</p> : null}
            {ask.error ? <p className="text-xs text-destructive">{errorMessage(ask.error)}</p> : null}
            <div ref={end} />
          </div>
          <form className="flex gap-2 border-t p-3" onSubmit={(e: FormEvent) => { e.preventDefault(); send(text); }}>
            <Input aria-label="Your question" placeholder="Ask about bookings, refunds…" value={text}
              maxLength={1000} onChange={(e) => setText(e.target.value)} />
            <Button type="submit" size="icon" aria-label="Send" disabled={ask.isPending || !text.trim()}>
              <Send />
            </Button>
          </form>
        </div>
      ) : (
        <Button size="lg" className="rounded-full shadow-lg" onClick={() => setOpen(true)}>
          <MessageCircleQuestion /> Ask TripMind
        </Button>
      )}
    </div>
  );
}
